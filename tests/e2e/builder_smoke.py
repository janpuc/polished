"""Headless-browser smoke test of the layer-stack builder (DESIGN 10). Not part of `pytest -q`: it
needs Chromium and a running server on a throwaway database.

    export POLISHED_DB_PATH=$(mktemp -d)/polished.db POLISHED_AUTH_MODE=none \\
           POLISHED_PUBLIC_URL=http://localhost:8080 POLISHED_SYNC_ENABLED=false
    uv run python -m polished migrate
    uv run python -m polished sync --from-files tests/fixtures/feed_trimmed.json
    (uv run python -m polished serve & echo $! > /tmp/polished.pid); sleep 2
    uvx --from playwright python tests/e2e/builder_smoke.py
    kill $(cat /tmp/polished.pid)

Playwright needs its Chromium (`uvx --from playwright playwright install chromium`, kept in
~/Library/Caches/ms-playwright). Optional argument: the base URL (default http://localhost:8080).
The database must be fresh: the run creates the wheel "Holos" and fills its slot 12.

What it checks, on an iPhone-sized viewport, with no console errors and no 4xx/5xx:
1. A new wheel opens its builder on slot 12: empty state, Save disabled.
2. Three taps on results add three layers; the live summary names them with " + " and the head
   draws the stack's composite tip (one picture once the cross-fade is done).
3. Over black (skipped with a note when the catalog has no `one-coat-black`, as the trimmed
   fixture has not), a layer moves up, a coat is added.
4. A typed name survives a layer edit (the form is never re-rendered); the head tip changes.
5. Save swatch closes the sheet, tile 12 is filled and the list shows the summary.
6. Reopening shows the saved layers and the name; Cancel closes it and the swatch stays.
"""

import re
import sys

from playwright.sync_api import expect, sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")

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


def layer_names(page) -> list[str]:
    return page.locator("#stack-layers .layer-name").all_inner_texts()


def run() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(**p.devices["iPhone 15"])
        context.route(
            "https://cdn.shopify.com/**",
            lambda route: route.fulfill(status=200, content_type="image/png", body=PIXEL),
        )
        page = context.new_page()
        problems: list[str] = []
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

        # 1. A wheel, and its slot 12.
        page.goto(f"{BASE}/wheels")
        page.fill("input[name=name]", "Holos")
        page.get_by_role("button", name="Make a wheel").click()
        page.goto(f"{BASE}/wheels")
        page.locator('a[href^="/w/"]').first.click()
        page.locator("#slot-12 .slot-hit").click()
        sheet = page.locator("#sheet[open]")
        sheet.locator(".builder").wait_for()
        check("Slot 12" in sheet.inner_text(), "tapping slot 12 opens the builder sheet")
        check("No layers yet." in sheet.inner_text(), "an empty draft shows the empty state")
        check(page.locator("#save-button").is_disabled(), "Save swatch is disabled with no layer")
        check(
            page.locator("#slot-12 .tip-dot").count() == 1,
            "opening a draft puts the draft dot on tile 12 out of band",
        )

        # 2. Three taps on + build x + y + z.
        for count in (1, 2, 3):
            page.locator("#picker-results .pick-add").nth(count).click()
            expect(page.locator("#stack-layers .layer")).to_have_count(count)
        names = layer_names(page)
        check(len(names) == 3, f"three taps add three layers ({names})")
        summary = page.locator("#stack-summary").inner_text()
        check(
            summary.count(" + ") == 2 and all(name in summary for name in names),
            f"the live summary names them in order ({summary})",
        )
        check(page.locator("#save-button").is_enabled(), "Save swatch enables with layers")
        tip = page.locator("#stack-tip img")
        expect(tip).to_have_count(1)  # the fade is done: the older pictures are dropped
        first_src = tip.get_attribute("src")
        check(
            "/tips/stack/" in first_src, f"the head draws the stack's composite tip ({first_src})"
        )

        # 3. Over black, move, coats.
        over_black = page.get_by_role("button", name="Over black")
        if over_black.count():
            over_black.click()
            expect(page.locator("#stack-layers .layer")).to_have_count(4)
            check(layer_names(page)[0] == "One-Coat Black", "Over black puts the black first")
        else:
            print("skip  Over black: no one-coat-black in this catalog")
        before = layer_names(page)
        page.locator("#stack-layers .layer").nth(1).get_by_role(
            "button", name="earlier", exact=False
        ).click()
        expect(page.locator("#stack-layers .layer-name").first).to_have_text(before[1])
        check(layer_names(page)[:2] == [before[1], before[0]], "a layer moves up one place")

        # 4. A typed name survives a layer edit.
        page.locator("details.more-fields summary").click()
        page.fill("#stack-name", "Smoke swatch")
        first = page.locator("#stack-layers .layer").first
        count = first.locator(".step-count")
        coats = int(count.inner_text())
        first.get_by_role("button", name="More coats").click()
        expect(page.locator("#stack-layers .layer").first.locator(".step-count")).to_have_text(
            str(coats + 1)
        )
        check(
            page.input_value("#stack-name") == "Smoke swatch",
            "the typed name is still there after a coat change",
        )
        summary = page.locator("#stack-summary").inner_text()
        check(f"×{coats + 1}" in summary, f"the summary shows the new coats ({summary})")
        expect(page.locator("#stack-tip img")).to_have_count(1)
        check(
            page.locator("#stack-tip img").get_attribute("src") != first_src,
            "the head tip is a new picture after the layers changed",
        )

        # 5. Save.
        page.locator("#save-button").click()
        page.locator("#sheet:not([open])").wait_for(state="attached")
        tile = page.locator("#slot-12")
        # sheetClose arrives with the headers, the out-of-band tile a moment later.
        expect(tile).to_have_class(re.compile(r"\bis-filled\b"))
        check(True, "tile 12 is filled after Save swatch")
        row = page.locator("#slot-list .slot-row", has_text="12").first
        row_title = row.locator(".row-title").inner_text()
        check(" + " in row_title, f"the list row shows the summary ({row_title})")
        check(
            page.locator("#hub-name").inner_text() == "1",
            "the number in the hub follows",
        )

        # 6. Reopen, then Cancel.
        page.locator("#slot-12 .slot-hit").click()
        page.locator("#sheet[open] .builder").wait_for()
        check(len(layer_names(page)) == 3 + bool(over_black.count()), "reopening shows the layers")
        check(page.input_value("#stack-name") == "Smoke swatch", "reopening shows the name")
        check(
            page.get_by_role("button", name="Remove swatch").is_visible(),
            "a saved slot offers Remove swatch",
        )
        page.get_by_role("button", name="Cancel").click()
        page.locator("#sheet:not([open])").wait_for(state="attached")
        expect(page.locator("#slot-12 .tip-dot")).to_have_count(0)
        expect(page.locator("#slot-12")).to_have_class(re.compile(r"\bis-filled\b"))
        check(True, "Cancel discards the draft, the dot is gone and the saved swatch stays")

        check(not problems, f"no console errors, failed requests or 4xx/5xx ({problems})")
        browser.close()


if __name__ == "__main__":
    run()
    print("builder smoke test passed")
