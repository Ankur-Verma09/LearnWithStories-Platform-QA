from dataclasses import asdict, dataclass
from pathlib import Path
import time
import uuid

from .errors import (
    ConcurrentDeploymentError,
    ConfigurationError,
    HealthCheckError,
    RollbackError,
    classify_error,
)


@dataclass(frozen=True)
class ReleaseResult:
    status: str
    version_id: str
    previous_version_id: str | None
    rolled_back: bool
    error: str | None = None
    error_type: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class ReleaseController:
    def __init__(self, client, uploader, probe, sleeper=time.sleep):
        self.client = client
        self.uploader = uploader
        self.probe = probe
        self.sleeper = sleeper

    def _wait_until_active(self, version_id: str, timeout: float = 20) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.client.active_version() == version_id:
                return
            self.sleeper(0.5)
        raise HealthCheckError("Cloudflare did not activate the expected version in time")

    def rollback(self, version_id: str, reason: str) -> None:
        self.client.create_deployment(version_id, f"Rollback: {reason}")
        try:
            self._wait_until_active(version_id)
        except HealthCheckError as exc:
            raise RollbackError(str(exc)) from exc

    def deploy(
        self,
        fixture: Path,
        worker_name: str,
        expected_marker: str,
        health_timeout: float,
    ) -> ReleaseResult:
        if health_timeout <= 0:
            raise ConfigurationError("Health timeout must be greater than zero")
        if not expected_marker.strip():
            raise ConfigurationError("Expected release marker cannot be empty")

        previous = self.client.active_version()
        tag = f"qa-{uuid.uuid4().hex[:12]}"
        version_id = self.uploader.upload(fixture, worker_name, tag)
        if self.client.active_version() != previous:
            raise ConcurrentDeploymentError(
                "Active version changed during upload; deployment was not activated"
            )
        self.client.create_deployment(version_id, f"Activate {tag}")

        try:
            self._wait_until_active(version_id)
            self.probe.verify(expected_marker, health_timeout)
        except Exception as exc:
            if previous:
                try:
                    self.rollback(previous, str(exc))
                except Exception as rollback_exc:
                    raise RollbackError(
                        f"Release failed: {exc}; rollback failed: {rollback_exc}"
                    ) from rollback_exc
                return ReleaseResult(
                    "failed", version_id, previous, True, str(exc), classify_error(exc)
                )
            return ReleaseResult(
                "failed", version_id, None, False, str(exc), classify_error(exc)
            )

        return ReleaseResult("healthy", version_id, previous, False)

