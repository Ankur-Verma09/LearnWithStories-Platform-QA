import argparse
import json
import os
from pathlib import Path
import sys

from .api import CloudflareClient
from .config import Settings
from .errors import ReleaseError, classify_error
from .health import HealthProbe
from .release import ReleaseController
from .wrangler import WranglerUploader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cf-release")
    commands = parser.add_subparsers(dest="command", required=True)

    deploy = commands.add_parser("deploy")
    deploy.add_argument("--fixture", type=Path, required=True)
    deploy.add_argument("--expected-marker", required=True)
    deploy.add_argument("--timeout", type=float, default=10)

    commands.add_parser("status")
    rollback = commands.add_parser("rollback")
    rollback.add_argument("--version-id", required=True)
    return parser


def _dependencies():
    settings = Settings.from_environment()
    client = CloudflareClient(
        settings.account_id,
        settings.api_token,
        settings.worker_name,
    )
    controller = ReleaseController(
        client,
        WranglerUploader(client),
        HealthProbe(settings.worker_url),
    )
    return settings, client, controller


def _add_alert(output: dict) -> dict:
    error = output.get("error")
    if not error:
        return output
    category = output.get("error_type") or "server_error"
    output["alert"] = {"category": category, "message": error}
    if os.getenv("GITHUB_ACTIONS") == "true":
        safe_error = str(error).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title={category}::{safe_error}", file=sys.stderr)
    return output


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings, client, controller = _dependencies()
        if args.command == "status":
            output = {"worker": settings.worker_name, "active_version": client.active_version()}
            code = 0
        elif args.command == "rollback":
            controller.rollback(args.version_id, "manual request")
            output = {"status": "rolled_back", "active_version": client.active_version()}
            code = 0
        else:
            result = controller.deploy(
                args.fixture,
                settings.worker_name,
                args.expected_marker,
                args.timeout,
            )
            output = result.to_dict()
            code = 0 if result.status == "healthy" else 1
    except ReleaseError as exc:
        output = {
            "status": "error",
            "error": str(exc),
            "error_type": classify_error(exc),
        }
        code = 2
    print(json.dumps(_add_alert(output), sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
