import json

from cloudflare_qa import cli
from cloudflare_qa.release import ReleaseResult


class Controller:
    def __init__(self, result):
        self.result = result

    def deploy(self, fixture, worker_name, expected_marker, timeout):
        return self.result


class Settings:
    worker_name = "learn-with-stories-qa"


def test_failed_release_returns_nonzero_exit_code(monkeypatch, capsys):
    result = ReleaseResult("failed", "candidate", "stable", True, "HTTP 500")
    monkeypatch.setattr(cli, "_dependencies", lambda: (Settings(), object(), Controller(result)))

    code = cli.main([
        "deploy",
        "--fixture",
        "fixtures/unhealthy",
        "--expected-marker",
        "unhealthy",
    ])

    output = json.loads(capsys.readouterr().out)
    assert code == 1
    assert output["rolled_back"] is True
    assert output["error"] == "HTTP 500"


def test_healthy_release_returns_success(monkeypatch, capsys):
    result = ReleaseResult("healthy", "candidate", "stable", False)
    monkeypatch.setattr(cli, "_dependencies", lambda: (Settings(), object(), Controller(result)))

    code = cli.main([
        "deploy",
        "--fixture",
        "fixtures/healthy",
        "--expected-marker",
        "healthy",
    ])

    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert output["status"] == "healthy"

