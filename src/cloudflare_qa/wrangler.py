from pathlib import Path
import subprocess
import time
from typing import Callable

from .errors import ConfigurationError, UploadError


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


class WranglerUploader:
    def __init__(self, client, run_command: RunCommand = subprocess.run, sleeper=time.sleep):
        self.client = client
        self.run_command = run_command
        self.sleeper = sleeper

    def upload(self, fixture: Path, worker_name: str, tag: str) -> str:
        fixture = fixture.resolve()
        config = fixture / "wrangler.jsonc"
        entrypoint = fixture / "worker.js"
        if not fixture.is_dir():
            raise ConfigurationError(f"Fixture directory does not exist: {fixture}")
        if not config.is_file() or not entrypoint.is_file():
            raise ConfigurationError("Fixture must contain wrangler.jsonc and worker.js")

        command = [
            "npx",
            "--yes",
            "wrangler@4.37.1",
            "versions",
            "upload",
            "--config",
            str(config),
            "--name",
            worker_name,
            "--tag",
            tag,
            "--message",
            f"QA release {tag}",
        ]
        completed = self.run_command(
            command,
            cwd=fixture,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode:
            detail = (completed.stderr or completed.stdout or "Wrangler upload failed").strip()
            raise UploadError(detail[-1200:])

        for _ in range(10):
            version_id = self.client.version_with_tag(tag)
            if version_id:
                return version_id
            self.sleeper(1)
        raise UploadError("Uploaded version did not appear in the Cloudflare version list")

