"""Builds the catalog the flows run against: the trimmed fixture feed, the shades the flows look
for, the trimmed release sheet, and a painted tip colour for every shade. No network: the feed is
applied from files and the colour step (which reads photos from the shop's CDN) is skipped.

    uv run python tests/e2e/flows/seed.py DB_PATH

`run_flows.py` calls this once per run and copies the result for every flow. Point `--base` at a
server whose database was made the same way (and whose POLISHED_PUBLIC_URL is that server's own
address) to run the flows against it.
"""

import colorsys
import copy
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from polished.catalog.sheet import apply_sheet, parse_sheet
from polished.catalog.sync import apply_feed, format_time
from polished.db import connect
from polished.migrate import migrate

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# (title, fixture product to copy, tags). The pair Jan mixes up, a black base, a topper, one
# shade per finish the filter flow uses.
EXTRA = [
    ("Magnetic Taco", "thirst-trap", ["finish:magnetic", "color:blue", "collection:magnetic"]),
    ("Holo Magnetic Taco", "thirst-trap", ["finish:magnetic", "color:purple"]),
    ("One-Coat Black", "thirst-trap", ["finish:creme", "color:black"]),
    ("Spirit Fingers", "jam-session", ["finish:glitter", "color:orange"]),
    ("Flakie Holo Taco", "aurora-unicorn-skin", ["finish:flakie", "finish:holographic", "toppers"]),
    ("Mermaid Jelly", "thirst-trap", ["finish:jelly", "color:blue", "color:green"]),
    ("Crème Brûlée", "rest-in-peach", ["finish:creme", "color:orange"]),
    ("Silver Flake Taco", "thirst-trap", ["finish:flakie", "color:silver"]),
]


def products() -> list[dict]:
    feed = json.loads((FIXTURES / "feed_trimmed.json").read_text(encoding="utf-8"))["products"]
    by_handle = {p["handle"]: p for p in feed}
    made = []
    for number, (title, template, tags) in enumerate(EXTRA, 1):
        product = copy.deepcopy(by_handle[template])
        product["id"] = 7_100_000_000 + number
        product["handle"] = title.lower().replace("è", "e").replace("û", "u").replace(" ", "-")
        product["title"] = title
        product["tags"] = tags
        variant = product["variants"][0]
        variant["id"] = 6_100_000_000 + number
        variant["sku"] = f"HL-E{number:04d}-NP"
        variant["available"] = True
        made.append(product)
    return [*feed, *made]


def build(path: str) -> None:
    migrate(path)
    conn = connect(path)
    now = datetime.now(UTC)
    run_id = conn.execute(
        "insert into sync_run (started_at, trigger, status) values (?, 'cli', 'running')",
        (format_time(now),),
    ).lastrowid
    apply_feed(conn, run_id, [products()], now, ZoneInfo("Europe/Warsaw"))
    sheet = (FIXTURES / "release_sheet_trimmed.csv").read_text(encoding="utf-8")
    apply_sheet(conn, parse_sheet(sheet, min_rows=1))
    for (shade_id,) in conn.execute("select id from shade").fetchall():
        hue = (shade_id * 0.137) % 1
        r, g, b = colorsys.hls_to_rgb(hue, 0.55, 0.6)
        hex_colour = f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"
        conn.execute("update shade set swatch_hex = ? where id = ?", (hex_colour, shade_id))
    conn.execute("update shade set swatch_hex = '#111111' where title = 'One-Coat Black'")
    conn.execute("pragma wal_checkpoint(truncate)")
    conn.close()


if __name__ == "__main__":
    build(sys.argv[1])
    print(f"seeded {sys.argv[1]}")
