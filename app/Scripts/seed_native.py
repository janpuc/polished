"""Builds the database the native UI flows run against: the e2e catalog (`tests/e2e/flows/seed.py`,
called, not modified) plus the invented household of the API fixtures (`scripts/make_api_fixtures.py`:
bottles, a wishlist, two wheels, a draft, learned codes), plus enough swatches on Holos for the ring
to look like a wheel in use. Catalog fields and invented bottles only.

    uv run python app/Scripts/seed_native.py DB_PATH
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from e2e.flows.seed import build  # noqa: E402

from polished import stacks  # noqa: E402
from polished.db import connect  # noqa: E402


def household_module():
    spec = importlib.util.spec_from_file_location(
        "make_api_fixtures", ROOT / "scripts" / "make_api_fixtures.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# (position, shade titles base to top, painted on): the slots Holos has besides the fixtures' 12 to 14
EXTRA_SWATCHES = [
    (1, ["Mermaid Jelly"], "2026-10-11"),
    (2, ["Magnetic Taco"], "2026-10-12"),
    (3, ["One-Coat Black", "Holo Magnetic Taco"], "2026-10-13"),
    (5, ["Crème Brûlée"], "2026-10-15"),
    (6, ["Silver Flake Taco"], "2026-10-16"),
    (8, ["Spirit Fingers", "Flakie Holo Taco"], "2026-10-18"),
    (9, ["Mermaid Jelly", "Flakie Holo Taco"], "2026-10-19"),
    (16, ["Holo Magnetic Taco"], "2026-10-11"),
    (17, ["Crème Brûlée", "Silver Flake Taco"], "2026-10-12"),
    (19, ["Magnetic Taco"], "2026-10-14"),
]


def main(path: str) -> None:
    build(path)
    conn = connect(path)
    ids = household_module().add_household(conn)
    holos = ids["holos"]

    def shade(title: str) -> int:
        return conn.execute("select id from shade where title = ?", (title,)).fetchone()["id"]

    for position, titles, painted_on in EXTRA_SWATCHES:
        stack_id = stacks.open_draft(conn, holos, position).stack_id
        for title in titles:
            stacks.append(conn, stack_id, shade(title))
        stacks.save(conn, stack_id, painted_on=painted_on)
    conn.execute("pragma wal_checkpoint(truncate)")
    conn.commit()
    conn.close()
    print(f"seeded {path}")


if __name__ == "__main__":
    main(sys.argv[1])
