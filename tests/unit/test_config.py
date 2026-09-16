import pytest

from cloudflare_qa.config import Settings
from cloudflare_qa.errors import ConfigurationError


def test_reads_qa_configuration(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "account")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    monkeypatch.setenv("CLOUDFLARE_QA_WORKER_NAME", "learn-with-stories-qa")
    monkeypatch.setenv("CLOUDFLARE_QA_URL", "https://qa.example.workers.dev/")

    settings = Settings.from_environment()

    assert settings.worker_name == "learn-with-stories-qa"
    assert settings.worker_url == "https://qa.example.workers.dev"


def test_rejects_production_worker(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "account")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    monkeypatch.setenv("CLOUDFLARE_QA_WORKER_NAME", "learn-with-stories")
    monkeypatch.setenv("CLOUDFLARE_QA_URL", "https://production.example.workers.dev")

    with pytest.raises(ConfigurationError, match="production Worker"):
        Settings.from_environment()


def test_reports_all_missing_configuration(monkeypatch):
    for name in (
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_QA_WORKER_NAME",
        "CLOUDFLARE_QA_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ConfigurationError) as error:
        Settings.from_environment()

    assert "account_id" in str(error.value)
    assert "api_token" in str(error.value)

