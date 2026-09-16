from pathlib import Path

import pytest

from cloudflare_qa.api import CloudflareClient
from cloudflare_qa.config import Settings
from cloudflare_qa.errors import CloudflareApiError
from cloudflare_qa.health import HealthProbe
from cloudflare_qa.release import ReleaseController
from cloudflare_qa.wrangler import WranglerUploader


pytestmark = pytest.mark.live
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def live_controller(live_environment):
    settings = Settings.from_environment()
    client = CloudflareClient(settings.account_id, settings.api_token, settings.worker_name)
    return settings, client, ReleaseController(
        client,
        WranglerUploader(client),
        HealthProbe(settings.worker_url),
    )


def ensure_healthy_baseline(settings, client, controller):
    result = controller.deploy(
        ROOT / "fixtures" / "healthy",
        settings.worker_name,
        "healthy",
        10,
    )
    assert result.status == "healthy", result.error
    assert client.active_version() == result.version_id
    return result.version_id


def test_successful_release_is_active_and_serving(live_controller):
    settings, client, controller = live_controller

    result = controller.deploy(
        ROOT / "fixtures" / "healthy",
        settings.worker_name,
        "healthy",
        10,
    )

    assert result.status == "healthy"
    assert result.rolled_back is False
    assert client.active_version() == result.version_id
    response = controller.probe.verify("healthy", 10)
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_invalid_token_is_rejected_by_cloudflare(live_controller):
    settings, _, _ = live_controller
    client = CloudflareClient(settings.account_id, "invalid-token", settings.worker_name)

    with pytest.raises(CloudflareApiError) as error:
        client.list_deployments()

    assert error.value.status in {401, 403}


def test_unhealthy_release_restores_previous_version(live_controller):
    settings, client, controller = live_controller
    stable_version = ensure_healthy_baseline(settings, client, controller)

    result = controller.deploy(
        ROOT / "fixtures" / "unhealthy",
        settings.worker_name,
        "unhealthy",
        10,
    )

    assert result.status == "failed"
    assert result.rolled_back is True
    assert "HTTP 500" in result.error
    assert client.active_version() == stable_version
    controller.probe.verify("healthy", 10)


def test_slow_release_times_out_and_restores_previous_version(live_controller):
    settings, client, controller = live_controller
    stable_version = ensure_healthy_baseline(settings, client, controller)

    result = controller.deploy(
        ROOT / "fixtures" / "slow",
        settings.worker_name,
        "slow",
        0.5,
    )

    assert result.status == "failed"
    assert result.rolled_back is True
    assert "timeout" in result.error.lower()
    assert client.active_version() == stable_version
    controller.probe.verify("healthy", 10)
