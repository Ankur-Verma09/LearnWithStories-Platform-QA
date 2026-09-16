import pytest

from cloudflare_qa.errors import HealthCheckError
from cloudflare_qa.health import HealthProbe, HealthResponse


def test_accepts_expected_release_and_security_headers():
    request_headers = {}
    response = HealthResponse(
        200,
        '{"status":"ok","release":"healthy"}',
        {"x-content-type-options": "nosniff"},
    )

    def transport(request, timeout):
        request_headers.update(request.header_items())
        return response

    probe = HealthProbe("https://qa.example", transport)

    result = probe.verify("healthy", 2)

    assert result.headers["x-content-type-options"] == "nosniff"
    assert request_headers["User-agent"] == "LearnWithStories-Platform-QA/1.0"


def test_rejects_non_success_response():
    response = HealthResponse(500, '{"release":"unhealthy"}', {})
    probe = HealthProbe("https://qa.example", lambda request, timeout: response)

    with pytest.raises(HealthCheckError, match="HTTP 500"):
        probe.verify("unhealthy", 2)


def test_rejects_wrong_release_marker():
    response = HealthResponse(200, '{"release":"old"}', {})
    probe = HealthProbe("https://qa.example", lambda request, timeout: response)

    with pytest.raises(HealthCheckError, match="wrong release marker"):
        probe.verify("new", 2)
