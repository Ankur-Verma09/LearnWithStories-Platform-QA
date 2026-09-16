import argparse
import json
from pathlib import Path
import sys

from .api import CloudflareClient
from .config import Settings
from .errors import ReleaseError
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
        output = {"status": "error", "error": str(exc)}
        code = 2
    print(json.dumps(output, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
