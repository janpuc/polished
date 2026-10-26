"""Rasterises src/polished/static/icons/logo.svg to the 1024 px flattened AppIcon of the asset
catalog (docs/NATIVE.md 5.11). iOS applies the mask and the glass itself, so the PNG is square,
full bleed and has no alpha channel.

    uvx --from playwright --with pillow python app/Scripts/make_app_icon.py
"""

import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
LOGO = ROOT / "src/polished/static/icons/logo.svg"
ICONSET = ROOT / "app/Polished/Resources/Assets.xcassets/AppIcon.appiconset"
SIZE = 1024


def main() -> None:
    ICONSET.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": SIZE, "height": SIZE})
        html = Path(tmp) / "icon.html"
        html.write_text(
            "<!doctype html><meta charset=utf-8><style>html,body{margin:0;background:#180b1e}"
            f"img{{display:block;width:{SIZE}px;height:{SIZE}px}}</style>"
            f'<img src="{LOGO.as_uri()}">'
        )
        page.goto(html.as_uri())
        page.wait_for_function("document.images[0].complete")
        raw = Path(tmp) / "raw.png"
        page.screenshot(path=raw)
        browser.close()
        Image.open(raw).convert("RGB").save(ICONSET / "AppIcon.png", optimize=True)
    (ICONSET / "Contents.json").write_text(
        '{\n  "images" : [\n    {\n      "filename" : "AppIcon.png",\n      "idiom" : "universal",\n'
        '      "platform" : "ios",\n      "size" : "1024x1024"\n    }\n  ],\n'
        '  "info" : {\n    "author" : "xcode",\n    "version" : 1\n  }\n}\n'
    )
    print("wrote", ICONSET / "AppIcon.png")


if __name__ == "__main__":
    main()
