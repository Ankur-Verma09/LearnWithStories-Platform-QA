from pathlib import Path

from cloudflare_qa.errors import HealthCheckError, HealthCheckTimeout
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

