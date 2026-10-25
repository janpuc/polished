"""python -m polished migrate | serve"""

import argparse
import logging
import sys

from pydantic import ValidationError

from .config import Settings
from .migrate import migrate


def _load_settings() -> Settings | None:
    try:
        return Settings()
    except ValidationError as exc:
        print("polished: invalid configuration:", file=sys.stderr)
        for error in exc.errors():
            name = ".".join(str(part) for part in error["loc"])
            message = error["msg"].removeprefix("Value error, ")
            print(f"  {name + ': ' if name else ''}{message}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="polished")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="apply SQL migrations")
    sub.add_parser("serve", help="run the web app")
    args = parser.parse_args(argv)

    settings = _load_settings()
    if settings is None:
        return 2
    logging.basicConfig(
        level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    if args.command == "migrate":
        for name in migrate(settings.db_path):
            print(f"applied {name}")
        return 0

    from .server import serve

    return serve(settings)
