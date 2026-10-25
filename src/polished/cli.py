"""python -m polished migrate | serve | sync [--from-files PAGE.json ...] | colours [--recompute]"""

import argparse
import asyncio
import logging
import sqlite3
import sys
from pathlib import Path

import httpx
from pydantic import ValidationError

from .config import Settings
from .db import connect
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


def _sync(settings: Settings, files: list[Path] | None) -> int:
    from .catalog.sync import RunRefused, SyncRunner

    runner = SyncRunner(settings)
    try:
        outcome = asyncio.run(runner.run("cli", files))
    except RunRefused as exc:
        print(f"polished: {exc}", file=sys.stderr)
        return 1
    except sqlite3.OperationalError as exc:
        print(
            f"polished: database not ready ({exc}); run `python -m polished migrate`",
            file=sys.stderr,
        )
        return 1
    if outcome.status != "ok":
        print(f"polished: sync failed: {outcome.error}", file=sys.stderr)
        return 1
    conn = connect(settings.db_path)
    try:
        run = conn.execute("select * from sync_run where id = ?", (outcome.run_id,)).fetchone()
    finally:
        conn.close()
    print(
        f"sync ok: {run['products_seen']} products in {run['pages_fetched']} page(s), "
        f"{run['new_shades']} new shades, {run['changed_shades']} changed, "
        f"{run['newly_missing']} newly missing, {run['returned']} returned, "
        f"{run['unresolved_aliases']} unresolved aliases"
    )
    return 0


def _colours(
    settings: Settings,
    *,
    recompute: bool,
    only: list[str] | None,
    transport: httpx.BaseTransport | None = None,
) -> int:
    from .catalog.colour import fill_colours

    try:
        conn = connect(settings.db_path)
    except sqlite3.OperationalError as exc:
        print(f"polished: database not ready ({exc})", file=sys.stderr)
        return 1
    try:
        stored = fill_colours(conn, transport=transport, recompute=recompute, only=only)
    except sqlite3.OperationalError as exc:
        print(f"polished: database not ready ({exc})", file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(f"colours: {stored} shade(s) read")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="polished")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="apply SQL migrations")
    sub.add_parser("serve", help="run the web app")
    sync = sub.add_parser("sync", help="sync the catalog once (live, or from local JSON pages)")
    sync.add_argument(
        "--from-files",
        nargs="+",
        type=Path,
        metavar="PAGE.json",
        help="apply local /products.json pages instead of fetching the shop",
    )
    colours = sub.add_parser("colours", help="read the polish colour of shades from their photos")
    colours.add_argument(
        "--recompute",
        action="store_true",
        help="read every shade again, whatever photo its colour came from (not the manual override)",
    )
    colours.add_argument(
        "--only", metavar="TITLES", help="with --recompute: comma-separated shade titles"
    )
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

    if args.command == "sync":
        return _sync(settings, args.from_files)

    if args.command == "colours":
        only = [t for t in (args.only or "").split(",") if t.strip()] or None
        return _colours(settings, recompute=args.recompute, only=only)

    from .server import serve

    return serve(settings)
