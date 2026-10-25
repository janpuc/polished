"""Headless-browser smoke test of the barcode scanner (DESIGN 7.3). Not part of `pytest -q`: it
needs Chromium and a running server on a throwaway database.

    export POLISHED_DB_PATH=$(mktemp -d)/polished.db POLISHED_AUTH_MODE=none \\
           POLISHED_PUBLIC_URL=http://localhost:8080 POLISHED_SYNC_ENABLED=false
    uv run python -m polished migrate
    uv run python -m polished sync --from-files tests/fixtures/feed_trimmed.json
    (uv run python -m polished serve & echo $! > /tmp/polished.pid); sleep 2
    uvx --from playwright --with python-barcode --with pillow python tests/e2e/scanner_smoke.py
    kill $(cat /tmp/polished.pid)

Playwright needs its Chromium (`uvx --from playwright playwright install chromium`, kept in
~/Library/Caches/ms-playwright). Optional argument: the base URL (default http://localhost:8080).
The database must be fresh: the run learns the barcode of the fixture's "Thirst Trap".

What it checks, with no console errors and no request that leaves the server:
1. /lookup: a UPC-A image of 810170284120 chosen through the still-photo input is decoded by
   zxing-wasm (loaded from /static/vendor/zxing-wasm/) and the page shows "New barcode
   0810170284120".
2. The typeahead teaches the barcode to a shade in one tap, and a second photo is a match.
3. The live-camera path: Chromium's fake camera plays the barcode image, the dialog opens, the
   code is read, the camera stops and the result is the match. (BarcodeDetector is removed so
   zxing-wasm decodes, as on an iPhone.)
"""

import sys
import tempfile
from pathlib import Path

from barcode import UPCA
from barcode.writer import ImageWriter
from PIL import Image
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
UPC = "810170284120"
GTIN = "0810170284120"
SHADE_QUERY = "thirst"


def make_images(directory: Path) -> tuple[Path, Path]:
    """The barcode as a PNG (for the photo input) and as a few-frame MJPEG file (a fake camera)."""
    code = directory / "upca"
    UPCA(UPC[:-1], writer=ImageWriter()).save(str(code), {"quiet_zone": 6.5, "module_height": 18})
    barcode = Image.open(f"{code}.png").convert("RGB")
    photo = directory / "barcode.png"
    barcode.save(photo)

    frame = Image.new("RGB", (1280, 720), "white")
    scale = 560 / barcode.width
    resized = barcode.resize((560, round(barcode.height * scale)))
    frame.paste(resized, ((1280 - resized.width) // 2, (720 - resized.height) // 2))
    jpeg = directory / "frame.jpg"
    frame.save(jpeg, quality=92)
    mjpeg = directory / "camera.mjpeg"
    mjpeg.write_bytes(jpeg.read_bytes() * 30)
    return photo, mjpeg


# A 1x1 transparent PNG: product thumbnails are hotlinked from Shopify's CDN, which a smoke test
# should not hit.
PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"ok  {message}")


def run(photo: Path, mjpeg: Path) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=[
                "--use-fake-device-for-media-stream",
                "--use-fake-ui-for-media-stream",
                f"--use-file-for-fake-video-capture={mjpeg}",
            ]
        )
        context = browser.new_context(
            viewport={"width": 800, "height": 450}, permissions=["camera"]
        )
        context.add_init_script("delete window.BarcodeDetector")
        context.route(
            "https://cdn.shopify.com/**",
            lambda route: route.fulfill(status=200, content_type="image/png", body=PIXEL),
        )
        page = context.new_page()
        problems: list[str] = []
        requested: list[str] = []
        page.on(
            "console",
            lambda m: (
                problems.append(f"console {m.type}: {m.text}")
                if m.type in ("error", "warning")
                else None
            ),
        )
        page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: problems.append(f"request failed: {r.url}"))
        page.on(
            "response",
            lambda r: problems.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None,
        )
        page.on("request", lambda r: requested.append(r.url))

        # 1. The still photo.
        page.goto(f"{BASE}/lookup")
        page.set_input_files("#scan-photo", str(photo))
        result = page.locator("#lookup-result")
        result.get_by_text(f"New barcode {GTIN}").wait_for(timeout=20000)
        check(True, f"the photo of {UPC} gives 'New barcode {GTIN}'")
        check(
            any(u.endswith("/static/vendor/zxing-wasm/zxing_reader.wasm") for u in requested),
            "the wasm came from /static/vendor/zxing-wasm/",
        )

        # 2. Teach it, then read the photo again.
        page.locator(".learn-picker input").fill(SHADE_QUERY)
        page.locator(".learn-results button.row-link").first.click()
        result.get_by_text("Saved.").wait_for()
        check(
            result.get_by_role("button", name="Add bottle").is_visible(),
            "one tap saves the barcode and offers 'Add bottle'",
        )
        page.set_input_files("#scan-photo", str(photo))
        result.get_by_text("Saved.").wait_for(
            state="detached"
        )  # no string eval: the CSP forbids it
        check(
            result.get_by_role("button", name="Add bottle").is_visible()
            and "New barcode" not in result.inner_text(),
            "the second photo is a match",
        )

        # 3. The live camera, on a fresh page.
        page.goto(f"{BASE}/lookup")
        page.locator("button[data-scan-open]").click()
        page.locator("#scanner[open]").wait_for(timeout=10000)
        page.locator("#scanner:not([open])").wait_for(state="attached", timeout=30000)
        result.get_by_role("button", name="Add bottle").wait_for(timeout=10000)
        check(True, "the live camera read the barcode and landed on the match")
        stopped = page.evaluate(
            "document.getElementById('scanner-video').srcObject === null || document.getElementById('scanner-video').srcObject.getTracks().every(t => t.readyState === 'ended')"
        )
        check(stopped, "the camera tracks are stopped after the read")

        outside = [
            u
            for u in requested
            if not u.startswith((BASE, "data:", "blob:", "https://cdn.shopify.com/"))
        ]
        check(
            not outside,
            f"no request left the server (bar the stubbed Shopify thumbnails) ({outside})",
        )
        check(not problems, f"no console errors, failed requests or 4xx/5xx ({problems})")
        browser.close()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        run(*make_images(Path(tmp)))
    print("scanner smoke test passed")
