from pathlib import Path
import subprocess

import pytest

from cloudflare_qa.errors import ConfigurationError, UploadError
from cloudflare_qa.wrangler import WranglerUploader


ROOT = Path(__file__).resolve().parents[2]


class Client:
    def __init__(self, versions):
        self.versions = iter(versions)

    def version_with_tag(self, tag):
        return next(self.versions)


def test_rejects_incomplete_fixture():
    uploader = WranglerUploader(Client([]))

    with pytest.raises(ConfigurationError, match="wrangler.jsonc and worker.js"):
        uploader.upload(ROOT / "tests" / "unit", "qa-worker", "tag")


def test_returns_uploaded_version_after_it_appears():
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "uploaded", "")

    uploader = WranglerUploader(Client([None, "version-2"]), run, sleeper=lambda _: None)

    version = uploader.upload(ROOT / "fixtures" / "healthy", "qa-worker", "tag")

    assert version == "version-2"
    assert "versions" in commands[0]
    assert "upload" in commands[0]


def test_surfaces_wrangler_failure():
    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "syntax error")

    uploader = WranglerUploader(Client([]), run)

    with pytest.raises(UploadError, match="syntax error"):
        uploader.upload(ROOT / "fixtures" / "healthy", "qa-worker", "tag")
