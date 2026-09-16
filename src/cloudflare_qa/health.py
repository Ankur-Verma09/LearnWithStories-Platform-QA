from dataclasses import dataclass
import json
import socket
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import HealthCheckError, HealthCheckTimeout


@dataclass(frozen=True)
class HealthResponse:
    status: int
    body: str
    headers: dict[str, str]


HealthTransport = Callable[[Request, float], HealthResponse]


def _default_transport(request: Request, timeout: float) -> HealthResponse:
    try:
        with urlopen(request, timeout=timeout) as response:
            return HealthResponse(
                response.status,
                response.read().decode("utf-8", errors="replace"),
                {key.lower(): value for key, value in response.headers.items()},
            )
    except HTTPError as exc:
        return HealthResponse(
            exc.code,
            exc.read().decode("utf-8", errors="replace"),
            {key.lower(): value for key, value in exc.headers.items()},
        )
    except (TimeoutError, socket.timeout) as exc:
        raise HealthCheckTimeout("Health check exceeded the release timeout") from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise HealthCheckTimeout("Health check exceeded the release timeout") from exc
        raise HealthCheckError(f"Health endpoint is unavailable: {exc.reason}") from exc


class HealthProbe:
    def __init__(self, worker_url: str, transport: HealthTransport = _default_transport):
        self.url = f"{worker_url.rstrip('/')}/health"
        self.transport = transport

    def verify(self, expected_marker: str, timeout: float) -> HealthResponse:
        request = Request(
            self.url,
            headers={
                "Accept": "application/json",
                "User-Agent": "LearnWithStories-Platform-QA/1.0",
            },
        )
        response = self.transport(request, timeout)
        if response.status != 200:
            raise HealthCheckError(f"Health endpoint returned HTTP {response.status}")
        try:
            payload = json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise HealthCheckError("Health endpoint did not return JSON") from exc
        if payload.get("release") != expected_marker:
            raise HealthCheckError("Health endpoint returned the wrong release marker")
        return response
