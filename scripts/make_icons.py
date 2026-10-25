"""Rasterises the app icons from the two SVGs in src/polished/static/icons/. Run after editing them;
the PNGs are committed.

    uvx --from playwright python scripts/make_icons.py [OUTPUT_DIR]

Chromium draws the SVG at each size (vector, so every size is crisp), which needs no system
cairo: install it once with `uvx --from playwright playwright install chromium`.

    logo.svg     the full-bleed mark, no rounding: iOS and Android mask it themselves
      apple-touch-icon.png   180, full bleed
      icon-maskable-512.png  512, full bleed (the nail sits inside the 80 percent safe circle)
      icon-192.png, icon-512.png  rounded corners (22 percent) on a transparent ground
    favicon.svg  the nail without gloss and smile line on a rounded tile
      favicon-32.png         32, the PNG fallback for browsers that skip the SVG favicon
"""

import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ICONS = Path(__file__).resolve().parent.parent / "src/polished/static/icons"
CORNER = "22.37%"  # the iOS icon curve is close enough to a plain 22 percent radius at these sizes

# name, source svg, size, rounded corners
SPECS = [
    ("apple-touch-icon.png", "logo.svg", 180, False),
    ("icon-maskable-512.png", "logo.svg", 512, False),
    ("icon-192.png", "logo.svg", 192, True),
    ("icon-512.png", "logo.svg", 512, True),
    ("favicon-32.png", "favicon.svg", 32, False),
]


def page_for(svg: Path, size: int, rounded: bool) -> str:
    radius = f"border-radius:{CORNER};" if rounded else ""
    return (
        "<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:transparent}"
        f"img{{display:block;width:{size}px;height:{size}px;{radius}}}</style>"
        f'<img src="{svg.as_uri()}">'
    )


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ICONS
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch()
        for name, source, size, rounded in SPECS:
            page = browser.new_page(viewport={"width": size, "height": size})
            html = Path(tmp) / f"{name}.html"
            html.write_text(page_for(ICONS / source, size, rounded))
            page.goto(html.as_uri())
            page.wait_for_function("document.images[0].complete")
            page.screenshot(path=out / name, omit_background=True)
            page.close()
            print("wrote", out / name)
        browser.close()


if __name__ == "__main__":
    main()
