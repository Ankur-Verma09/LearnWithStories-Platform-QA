import json
import socket
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .errors import CloudflareApiError


Transport = Callable[[Request, float], tuple[int, bytes]]


def _default_transport(request: Request, timeout: float) -> tuple[int, bytes]:
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()
    except (TimeoutError, socket.timeout) as exc:
        raise CloudflareApiError(0, "Cloudflare API request timed out") from exc
    except URLError as exc:
        raise CloudflareApiError(0, f"Cloudflare API is unavailable: {exc.reason}") from exc


class CloudflareClient:
    def __init__(
        self,
        account_id: str,
        api_token: str,
        worker_name: str,
        transport: Transport = _default_transport,
    ):
        self.base_url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{quote(account_id, safe='')}/workers/scripts/{quote(worker_name, safe='')}"
        )
        self.api_token = api_token
        self.transport = transport

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: float = 30,
    ) -> Any:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        status, raw = self.transport(request, timeout)
        try:
            document = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CloudflareApiError(status, "Cloudflare returned an invalid JSON response") from exc
        if status >= 400 or document.get("success") is False:
            errors = document.get("errors") or []
            message = errors[0].get("message") if errors else f"Cloudflare API returned HTTP {status}"
            raise CloudflareApiError(status, message)
        return document.get("result", document)

    def list_deployments(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/deployments")
        if isinstance(result, list):
            return result
        return result.get("deployments", [])

    def active_version(self) -> str | None:
        deployments = self.list_deployments()
        if not deployments:
            return None
        versions = deployments[0].get("versions", [])
        if not versions:
            return None
        return max(versions, key=lambda item: float(item.get("percentage", 0))).get("version_id")

    def create_deployment(self, version_id: str, message: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/deployments",
            {
                "strategy": "percentage",
                "versions": [{"version_id": version_id, "percentage": 100}],
                "annotations": {"workers/message": message[:1000]},
            },
        )

    def list_versions(self) -> list[dict[str, Any]]:
        result = self._request("GET", "/versions?deployable=true")
        if isinstance(result, list):
            return result
        return result.get("items", [])

    def version_with_tag(self, tag: str) -> str | None:
        for version in self.list_versions():
            metadata = version.get("metadata") or {}
            annotations = metadata.get("annotations") or version.get("annotations") or {}
            if annotations.get("workers/tag") == tag:
                return version.get("id")
        return None
