from pathlib import Path

import pytest

from cloudflare_qa.errors import (
    CloudflareApiError,
    ConcurrentDeploymentError,
    ConfigurationError,
    HealthCheckError,
    HealthCheckTimeout,
    RollbackError,
)
from cloudflare_qa.release import ReleaseController


class FakeClient:
    def __init__(self, active="stable"):
        self.active = active
        self.deployments = []

    def active_version(self):
        return self.active

    def create_deployment(self, version_id, message):
        self.active = version_id
        self.deployments.append((version_id, message))
        return {"id": f"deployment-{len(self.deployments)}"}


class FakeUploader:
    def __init__(self, version="candidate"):
        self.version = version

    def upload(self, fixture, worker_name, tag):
        return self.version


class FakeProbe:
    def __init__(self, error=None):
        self.error = error

    def verify(self, expected_marker, timeout):
        if self.error:
            raise self.error
        return object()


def controller(client, error=None):
    return ReleaseController(
        client,
        FakeUploader(),
        FakeProbe(error),
        sleeper=lambda _: None,
    )


def test_accepts_healthy_candidate():
    client = FakeClient()

    result = controller(client).deploy(Path("fixture"), "qa-worker", "healthy", 2)

    assert result.status == "healthy"
    assert result.rolled_back is False
    assert client.active == "candidate"


def test_rolls_back_after_health_failure():
    client = FakeClient()

    result = controller(client, HealthCheckError("HTTP 500")).deploy(
        Path("fixture"), "qa-worker", "healthy", 2
    )

    assert result.status == "failed"
    assert result.rolled_back is True
    assert result.error == "HTTP 500"
    assert client.active == "stable"
    assert [item[0] for item in client.deployments] == ["candidate", "stable"]


def test_rolls_back_after_health_timeout():
    client = FakeClient()

    result = controller(client, HealthCheckTimeout("timed out")).deploy(
        Path("fixture"), "qa-worker", "slow", 0.1
    )

    assert result.status == "failed"
    assert result.rolled_back is True
    assert client.active == "stable"


def test_reports_failure_without_rollback_when_no_baseline_exists():
    client = FakeClient(active=None)

    result = controller(client, HealthCheckError("HTTP 500")).deploy(
        Path("fixture"), "qa-worker", "unhealthy", 2
    )

    assert result.status == "failed"
    assert result.rolled_back is False
    assert result.previous_version_id is None


def test_rolls_back_when_health_endpoint_is_unavailable():
    client = FakeClient()

    result = controller(client, HealthCheckError("endpoint unavailable")).deploy(
        Path("fixture"), "qa-worker", "healthy", 2
    )

    assert result.status == "failed"
    assert result.error_type == "server_error"
    assert result.rolled_back is True
    assert client.active == "stable"


def test_reports_original_error_when_rollback_fails():
    class RollbackFailingClient(FakeClient):
        def create_deployment(self, version_id, message):
            if version_id == "stable":
                raise CloudflareApiError(503, "rollback API unavailable")
            return super().create_deployment(version_id, message)

    client = RollbackFailingClient()

    with pytest.raises(RollbackError, match="HTTP 500.*rollback API unavailable"):
        controller(client, HealthCheckError("HTTP 500")).deploy(
            Path("fixture"), "qa-worker", "healthy", 2
        )


def test_stops_when_another_deployment_changes_active_version():
    class ConcurrentClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.reads = 0

        def active_version(self):
            self.reads += 1
            return "stable" if self.reads == 1 else "other-release"

    client = ConcurrentClient()

    with pytest.raises(ConcurrentDeploymentError, match="changed during upload"):
        controller(client).deploy(Path("fixture"), "qa-worker", "healthy", 2)

    assert client.deployments == []


@pytest.mark.parametrize("timeout", [0, -1])
def test_rejects_nonpositive_timeout_before_cloudflare_call(timeout):
    class UnexpectedClient:
        def active_version(self):
            raise AssertionError("Cloudflare must not be called")

    with pytest.raises(ConfigurationError, match="greater than zero"):
        controller(UnexpectedClient()).deploy(
            Path("fixture"), "qa-worker", "healthy", timeout
        )


def test_rejects_empty_expected_marker_before_cloudflare_call():
    class UnexpectedClient:
        def active_version(self):
            raise AssertionError("Cloudflare must not be called")

    with pytest.raises(ConfigurationError, match="cannot be empty"):
        controller(UnexpectedClient()).deploy(Path("fixture"), "qa-worker", " ", 2)

