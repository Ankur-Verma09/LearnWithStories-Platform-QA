from dataclasses import dataclass, field
import os
from urllib.parse import urlparse

from .errors import ConfigurationError


@dataclass(frozen=True)
class Settings:
    account_id: str
    api_token: str = field(repr=False)
    worker_name: str
    worker_url: str

    @classmethod
    def from_environment(cls) -> "Settings":
        values = {
            "account_id": os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip(),
            "api_token": os.getenv("CLOUDFLARE_API_TOKEN", "").strip(),
            "worker_name": os.getenv("CLOUDFLARE_QA_WORKER_NAME", "").strip(),
            "worker_url": os.getenv("CLOUDFLARE_QA_URL", "").strip().rstrip("/"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            names = ", ".join(sorted(missing))
            raise ConfigurationError(f"Missing configuration: {names}")
        if values["worker_name"] == "learn-with-stories":
            raise ConfigurationError("The production Worker cannot be used by this suite")
        if not values["worker_url"].startswith("https://"):
            raise ConfigurationError("CLOUDFLARE_QA_URL must use HTTPS")
        hostname = urlparse(values["worker_url"]).hostname or ""
        if not hostname.startswith(f"{values['worker_name']}."):
            raise ConfigurationError("CLOUDFLARE_QA_URL does not match the QA Worker name")
        return cls(**values)
