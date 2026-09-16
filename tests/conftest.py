import os

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="run tests that deploy the isolated Cloudflare QA Worker",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live"):
        return
    skip = pytest.mark.skip(reason="use --run-live to run Cloudflare deployment tests")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def live_environment():
    names = [
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_QA_WORKER_NAME",
        "CLOUDFLARE_QA_URL",
    ]
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        pytest.fail(f"Missing live-test configuration: {', '.join(missing)}")
    return {name: os.environ[name] for name in names}

