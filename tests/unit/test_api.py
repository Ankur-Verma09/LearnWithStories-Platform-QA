import json
import socket

import pytest

from cloudflare_qa import api
from cloudflare_qa.api import CloudflareClient
from cloudflare_qa.errors import CloudflareApiError


class RecordedTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return next(self.responses)


def response(result, success=True):
    return 200, json.dumps({"success": success, "result": result, "errors": []}).encode()


def test_returns_version_with_highest_traffic_percentage():
    transport = RecordedTransport(
        [response({"deployments": [{"versions": [
            {"version_id": "candidate", "percentage": 10},
            {"version_id": "stable", "percentage": 90},
        ]}]})]
    )
    client = CloudflareClient("account", "secret", "qa-worker", transport)

    assert client.active_version() == "stable"
    request, _ = transport.requests[0]
    assert request.get_header("Authorization") == "Bearer secret"


def test_creates_single_version_deployment():
    transport = RecordedTransport([response({"id": "deployment-1"})])
    client = CloudflareClient("account", "secret", "qa-worker", transport)

    result = client.create_deployment("version-2", "activate candidate")

    assert result["id"] == "deployment-1"
    request, _ = transport.requests[0]
    body = json.loads(request.data)
    assert body["versions"] == [{"version_id": "version-2", "percentage": 100}]


def test_surfaces_cloudflare_error_without_token():
    payload = {
        "success": False,
        "errors": [{"code": 10000, "message": "Authentication error"}],
    }
    transport = RecordedTransport([(403, json.dumps(payload).encode())])
    client = CloudflareClient("account", "secret", "qa-worker", transport)

    with pytest.raises(CloudflareApiError) as error:
        client.list_deployments()

    assert error.value.status == 403
    assert str(error.value) == "Authentication error"


def test_reports_cloudflare_timeout(monkeypatch):
    def time_out(request, timeout):
        raise socket.timeout()

    monkeypatch.setattr(api, "urlopen", time_out)

    with pytest.raises(CloudflareApiError, match="timed out") as error:
        api._default_transport(object(), 1)

    assert error.value.status == 0

