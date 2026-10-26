"""The flows. Each is a function of a harness.Trace, registered with @flow, and works through named
steps (see harness.py). Selectors are roles, labels and visible text; the few ids used are the
ones htmx itself targets (#search-results, #shade-list, #stack-summary, #slot-N), which a restyle
keeps. Flows add their own data through the UI and use names with the trace's `uid`, so they also
work on a server that other runs have used."""

import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import Locator, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .harness import Trace
from .media import GTIN, make_images

# Home's title is the greeting, which follows the hour.
GREETING = re.compile(r"^Good (morning|afternoon|evening)")


@dataclass(frozen=True)
class Flow:
    name: str
    title: str
    run: Callable[[Trace], None]


FLOWS: dict[str, Flow] = {}


def flow(name: str, title: str):
    def register(function: Callable[[Trace], None]):
        FLOWS[name] = Flow(name, title, function)
        return function

    return register


# Helpers the flows share. None of them records a step; they run inside one.


def type_and_wait(t: Trace, box: Locator, text: str, url_part: str) -> None:
    """Types into a search field and waits for the answer to the request it makes. A field that
    has just been swapped in (a sheet) may not have its htmx trigger yet, so an unanswered input is
    cleared and typed again."""
    for attempt in range(3):
        try:
            with t.page.expect_response(
                lambda r: url_part in r.url and r.request.method == "GET", timeout=2500
            ):
                box.fill("")
                box.fill(text)
            return
        except PlaywrightTimeoutError:
            if attempt == 2:
                raise


def row_titles(rows: Locator, count: int = 3) -> list[str]:
    """The first lines of the first `count` rows' text, which is the shade's title."""
    return [rows.nth(i).inner_text().splitlines()[0] for i in range(min(count, rows.count()))]


def open_shade(t: Trace, title: str) -> None:
    """The shade's page, reached through the browse list like a person would."""
    t.goto(f"/shades?q={quote(title)}")
    t.page.locator("#shade-list").get_by_role("link").first.click()
    expect(t.page.get_by_role("heading", level=1, name=title)).to_be_visible()


def add_bottle(t: Trace, title: str, *, price: str = "", bought_on: str = "") -> None:
    open_shade(t, title)
    t.page.get_by_role("button", name="Add bottle").click()
    sheet = t.open_sheet()
    if price or bought_on:
        sheet.get_by_label("Bought on").fill(bought_on)
        sheet.get_by_text("More details").click()
        sheet.get_by_label("Price paid ($)").fill(price)
    sheet.get_by_role("button", name="Add bottle").click()
    t.close_sheet_check()
    expect(t.page.locator("#bottles")).to_contain_text("Full")


def make_wheel(t: Trace, name: str) -> str:
    """Creates a wheel through the form and opens it; returns the wheel page's path."""
    t.goto("/wheels")
    t.page.get_by_label("Name").fill(name)
    t.page.get_by_role("button", name="Make a wheel").click()
    expect(t.page.get_by_role("heading", level=1, name="Tag and QR code")).to_be_visible()
    t.page.get_by_role("link", name="Open the wheel").click()
    expect(t.page.get_by_role("heading", level=1, name=name)).to_be_visible()
    return t.page.url.removeprefix(t.base)


def pick_layer(t: Trace, query: str, title: str) -> None:
    """In the builder sheet: search the picker and tap the result."""
    sheet = t.open_sheet()
    sheet.get_by_role(
        "radio", name="All"
    ).check()  # the picker starts on Owned once a bottle exists
    box = sheet.get_by_role("searchbox", name="Search shades or a P code")
    type_and_wait(t, box, query, "/search")
    sheet.get_by_role("button", name=f"Add {title}").click()
    expect(sheet.locator("#stack-summary")).to_contain_text(title)


def swatch(t: Trace, position: int, layers: list[tuple[str, str]]) -> None:
    """Builds and saves a swatch in a slot: layers are (what to type, the title to tap)."""
    t.page.get_by_role("button", name=re.compile(rf"^Slot {position}, empty")).click()
    for query, title in layers:
        pick_layer(t, query, title)
    sheet = t.open_sheet()
    sheet.get_by_role("button", name="Save swatch").click()
    t.close_sheet_check()
    expect(t.page.locator(f"#slot-{position}")).to_have_class(re.compile(r"\bis-filled\b"))


# Search


@flow("search", "Search: the exact title first, typos, a missing space, accents, no match")
def search(t: Trace) -> None:
    page = t.page
    box = page.get_by_role("searchbox", name="Search shades")
    rows = page.locator("#search-results").get_by_role("link")

    def ask(text: str) -> None:
        type_and_wait(t, box, text, "/search")

    with t.step("open Home"):
        t.goto("/")
        expect(page.get_by_role("heading", level=1, name=GREETING)).to_be_visible()
        expect(box).to_be_visible()

    with t.step("Magnetic Taco before Holo Magnetic Taco, the difference marked"):
        ask("magnetic taco")
        expect(rows.first).to_contain_text("Magnetic Taco")
        assert row_titles(rows, 2) == ["Magnetic Taco", "Holo Magnetic Taco"], row_titles(rows, 3)
        assert rows.nth(1).locator("mark").all_inner_texts() == ["Magnetic", "Taco"]
        assert "Holo" not in "".join(rows.nth(1).locator("mark").all_inner_texts())

    cases = [
        (
            "a swapped letter: magentic taco",
            "magentic taco",
            ["Magnetic Taco", "Holo Magnetic Taco"],
        ),
        ("a missing letter: holo magnetc", "holo magnetc", ["Holo Magnetic Taco"]),
        ("two words with typos: spirit fingrs", "spirit fingrs", ["Spirit Fingers"]),
        ("words in a hyphenated title: one coat black", "one coat black", ["One-Coat Black"]),
        ("a missing space: onecoat", "onecoat", ["One-Coat Black"]),
        ("accents ignored: creme brulee", "creme brulee", ["Crème Brûlée"]),
        (
            "the trademark sign ignored: aurora unicorn skin",
            "aurora unicorn skin",
            ["Aurora Unicorn Skin™"],
        ),
    ]
    for name, text, expected in cases:
        with t.step(name):
            ask(text)
            expect(rows.first).to_contain_text(expected[0])
            assert row_titles(rows, len(expected)) == expected, row_titles(rows, 3)

    with t.step("nothing matches"):
        ask("xyzzyplugh")
        expect(page.get_by_text("Nothing matches")).to_be_visible()
        expect(page.get_by_text("Try fewer letters")).to_be_visible()
        expect(page.get_by_role("link", name="Add it by hand")).to_be_visible()

    with t.step("open a result"):
        ask("spirit fingrs")
        rows.first.click()
        expect(page.get_by_role("heading", level=1, name="Spirit Fingers")).to_be_visible()

    with t.step("the Shades page ranks the same way"):
        t.goto("/shades")
        page.get_by_role("searchbox", name="Search shades").fill("magentic taco")
        listing = page.locator("#shade-list").get_by_role("link")
        expect(listing.first).to_contain_text("Magnetic Taco")
        assert row_titles(listing, 2) == ["Magnetic Taco", "Holo Magnetic Taco"], row_titles(
            listing, 3
        )


# Bottles


@flow("add-bottle", "Add a bottle from a shade page")
def add_bottle_flow(t: Trace) -> None:
    page = t.page
    with t.step("open Thirst Trap"):
        open_shade(t, "Thirst Trap")
        expect(page.get_by_role("button", name="Add bottle")).to_be_visible()

    with t.step("open the add-bottle sheet"):
        page.get_by_role("button", name="Add bottle").click()
        sheet = t.open_sheet()
        expect(sheet.get_by_role("heading", name=re.compile("Add bottle"))).to_be_visible()

    with t.step("the date field says it in words and its presets set it"):
        sheet = t.open_sheet()
        field = sheet.locator("[data-date-field]").first
        today, yesterday = date.today(), date.today() - timedelta(days=1)
        expect(field.locator(".date-main")).to_have_text("Today")
        sheet.get_by_role("button", name="Yesterday").click()
        expect(field.locator(".date-main")).to_have_text("Yesterday")
        expect(sheet.get_by_label("Bought on")).to_have_value(yesterday.isoformat())
        expect(sheet.get_by_role("button", name="Yesterday")).to_have_attribute(
            "aria-pressed", "true"
        )
        sheet.get_by_role("button", name=re.compile("Don.t know")).click()
        expect(field.locator(".date-main")).to_have_text(re.compile("Don.t know"))
        expect(sheet.get_by_label("Bought on")).to_have_value("")
        sheet.get_by_role("button", name="Today").click()
        expect(sheet.get_by_label("Bought on")).to_have_value(today.isoformat())
        expect(sheet.get_by_label("Bought on")).to_have_attribute("max", today.isoformat())

    with t.step("a day in the future is not accepted: the browser holds the form back"):
        sheet = t.open_sheet()
        box = sheet.get_by_label("Bought on")
        box.fill((date.today() + timedelta(days=2)).isoformat())
        sheet.get_by_role("button", name="Add bottle").click()
        assert box.evaluate("input => input.validity.rangeOverflow"), "max did not stop the date"
        t.open_sheet()  # still open: nothing was sent (the server's own check is in the unit tests)

    with t.step("fill in the date and price"):
        sheet = t.open_sheet()
        sheet.get_by_label("Bought on").fill(date.today().isoformat())
        sheet.get_by_text("More details").click()
        sheet.get_by_label("Price paid ($)").fill("12.50")
        sheet.get_by_label("Notes").fill("Test bottle")

    with t.step("save: the bottle is listed and the shade is owned"):
        t.open_sheet().get_by_role("button", name="Add bottle").click()
        t.close_sheet_check()
        bottles = page.locator("#bottles")
        expect(bottles).to_contain_text("Full")
        expect(bottles).to_contain_text("$12.50")
        expect(bottles).to_contain_text("Test bottle")
        expect(page.get_by_text("Owned ×1")).to_be_visible()

    with t.step("the shade shows as owned in the list"):
        t.goto("/shades?owned=owned")
        expect(page.locator("#shade-list").get_by_role("link").first).to_contain_text("Thirst Trap")
        expect(page.locator("#result-count")).to_have_text("1 shade")


@flow("bottle-level", "Change a bottle's level until it is empty")
def bottle_level(t: Trace) -> None:
    page = t.page
    with t.step("a full bottle of Thirst Trap"):
        add_bottle(t, "Thirst Trap")
        expect(page.get_by_role("button", name=re.compile("Full"))).to_be_visible()

    for level in ("Half", "Low"):
        with t.step(f"set the level to {level}"):
            page.locator("#bottles").get_by_role("button").first.click()
            sheet = t.open_sheet()
            expect(sheet.get_by_role("heading", name=re.compile("Edit bottle"))).to_be_visible()
            sheet.get_by_role("radio", name=level).check()
            sheet.get_by_role("button", name="Save changes").click()
            t.close_sheet_check()
            expect(page.locator("#bottles")).to_contain_text(level)
            expect(page.get_by_text("Owned ×1")).to_be_visible()

    with t.step("empty: the shade is no longer owned"):
        page.locator("#bottles").get_by_role("button").first.click()
        sheet = t.open_sheet()
        sheet.get_by_role("radio", name="Empty").check()
        sheet.get_by_role("button", name="Save changes").click()
        t.close_sheet_check()
        expect(page.locator("#bottles")).to_contain_text("Empty")
        expect(page.get_by_text("Owned ×1")).to_have_count(0)

    with t.step("archive it: it moves to past bottles"):
        page.locator("#bottles").get_by_role("button").first.click()
        t.open_sheet().get_by_role("button", name="Archive this bottle").click()
        t.close_sheet_check()
        expect(page.locator("#bottles")).to_contain_text("Archived")
        page.reload()
        expect(page.get_by_role("heading", name="Past bottles")).to_be_visible()

    with t.step("the Bottles tab"):
        page.get_by_role("navigation", name="Main").get_by_role("link", name="Bottles").click()
        expect(page.get_by_role("heading", level=1, name="Bottles")).to_be_visible()


# Wishlist


@flow("wishlist", "Wishlist: add, set a priority, mark as bought")
def wishlist(t: Trace) -> None:
    page = t.page
    tabs = page.get_by_role("navigation", name="Main")

    for title in ("Thirst Trap", "Hit The Lights"):
        with t.step(f"wish for {title}"):
            open_shade(t, title)
            page.get_by_role("button", name="Add to the wishlist").click()
            expect(
                page.get_by_role("button", name="On the wishlist, tap to remove")
            ).to_be_visible()

    with t.step("the wishlist lists both"):
        tabs.get_by_role("link", name="Wishlist").click()
        expect(page.get_by_role("heading", level=1, name="Wishlist")).to_be_visible()
        expect(page.get_by_role("combobox", name="Priority of Thirst Trap")).to_be_visible()
        expect(page.get_by_role("combobox", name="Priority of Hit The Lights")).to_be_visible()

    with t.step("set Thirst Trap to Want most"):
        with page.expect_response(lambda r: "/priority" in r.url):
            page.get_by_role("combobox", name="Priority of Thirst Trap").select_option(
                label="Want most"
            )
        expect(page.get_by_role("heading", name=re.compile(r"^Want most"))).to_be_visible()
        expect(page.get_by_role("combobox", name="Priority of Thirst Trap")).to_have_value("1")

    with t.step("the checkout follows the priority"):
        with page.expect_response(lambda r: "/wishlist/cart" in r.url):
            page.locator("#cart-box").get_by_role("radio", name="Want most").check()
        expect(page.locator("#cart-box")).to_contain_text("1 shade in stock")
        expect(page.get_by_role("link", name="Open in Holo Taco checkout")).to_be_visible()

    with t.step("I bought these"):
        page.get_by_role("button", name="I bought these").click()
        sheet = t.open_sheet()
        expect(sheet.get_by_role("heading", name=re.compile("I bought these"))).to_be_visible()
        sheet.get_by_label("Bought on").fill(date.today().isoformat())
        price = sheet.get_by_label("Price paid for Thirst Trap, in dollars")
        price.fill("13.50")

    with t.step("save: the bottles are added and leave the wishlist"):
        t.open_sheet().get_by_role("button", name="Add bottles").click()
        t.close_sheet_check()
        expect(page.get_by_text(re.compile(r"\d bottles? added"))).to_be_visible()
        expect(page.get_by_role("combobox", name="Priority of Thirst Trap")).to_have_count(0)

    with t.step("History shows the purchase with its price"):
        page.get_by_role("link", name="History").click()
        expect(page.get_by_role("link", name=re.compile("Thirst Trap"))).to_be_visible()
        expect(page.get_by_text("$13.50").first).to_be_visible()


# Wheels


@flow(
    "wheel-build", "Create a wheel, build a 3-layer swatch, see it on the ring and in Swatched on"
)
def wheel_build(t: Trace) -> None:
    page = t.page
    name = f"Flow wheel {t.uid}"
    layers = [
        ("magnetic taco", "Magnetic Taco"),
        ("onecoat", "One-Coat Black"),
        ("flakie", "Flakie Holo Taco"),
    ]

    with t.step("the Wheels tab offers a new wheel"):
        t.goto("/wheels")
        expect(page.get_by_role("heading", level=1, name="Wheels")).to_be_visible()
        expect(page.get_by_role("button", name="Make a wheel")).to_be_visible()

    with t.step("make a wheel: its tag page opens"):
        page.get_by_label("Name").fill(name)
        page.get_by_role("button", name="Make a wheel").click()
        expect(page.get_by_role("heading", level=1, name="Tag and QR code")).to_be_visible()
        expect(page.get_by_role("img", name=re.compile("QR code"))).to_be_visible()

    with t.step("open the wheel: 0 of 20"):
        page.get_by_role("link", name="Open the wheel").click()
        expect(page.get_by_role("heading", level=1, name=name)).to_be_visible()
        expect(page.get_by_role("group", name=re.compile("0 of 20 swatched"))).to_be_visible()

    with t.step("tap slot 3: the builder opens empty"):
        page.get_by_role("button", name=re.compile(r"^Slot 3, empty")).click()
        sheet = t.open_sheet()
        expect(sheet.get_by_role("heading", name="Slot 3")).to_be_visible()
        expect(sheet.get_by_text("No layers yet")).to_be_visible()
        expect(sheet.get_by_role("button", name="Save swatch")).to_be_disabled()

    for query, title in layers:
        with t.step(f"search “{query}” and add {title}"):
            pick_layer(t, query, title)

    with t.step("three layers: the summary names them in order"):
        sheet = t.open_sheet()
        summary = sheet.locator("#stack-summary")
        for _, title in layers:
            expect(summary).to_contain_text(title)
        assert summary.inner_text().count(" + ") == 2, summary.inner_text()
        expect(sheet.get_by_role("button", name="Save swatch")).to_be_enabled()

    with t.step("a second coat on the first layer"):
        sheet = t.open_sheet()
        sheet.get_by_role("button", name="More coats").first.click()
        expect(sheet.locator("#stack-summary")).to_contain_text("×")

    with t.step("name it and save"):
        sheet = t.open_sheet()
        sheet.get_by_text("Name and note").click()
        sheet.get_by_label("Name").fill("Flow swatch")
        sheet.get_by_role("button", name="Save swatch").click()
        t.close_sheet_check()
        expect(page.locator("#slot-3")).to_have_class(re.compile(r"\bis-filled\b"))

    with t.step("the ring, the hub and the list show it"):
        expect(page.locator("#hub-name")).to_have_text("1")
        expect(page.locator("#hub-count")).to_have_text("of 20")
        expect(page.get_by_role("group", name=re.compile("1 of 20 swatched"))).to_be_visible()
        slots = page.get_by_role("button", name=re.compile(r"^Slot 3, .*Magnetic Taco"))
        expect(slots).to_have_count(2)  # the tile on the ring and the row in the list

    with t.step("Swatched on, on the shade page"):
        open_shade(t, "Magnetic Taco")
        expect(page.get_by_role("heading", name="Swatched on")).to_be_visible()
        page.get_by_role("link", name=re.compile(rf"{name}, slot 3")).click()
        expect(page.get_by_role("heading", level=1, name=name)).to_be_visible()
        expect(page.get_by_text(re.compile(r"Magnetic Taco is on slot 3"))).to_be_visible()


@flow("wheel-delete", "Delete a wheel for good, after a confirmation")
def wheel_delete(t: Trace) -> None:
    page = t.page
    name = f"Test wheel {t.uid}"
    foot = page.get_by_role("navigation", name="This wheel")

    with t.step("a wheel with one swatch"):
        wheel_path = make_wheel(t, name)
        swatch(t, 5, [("spirit fingers", "Spirit Fingers")])
        expect(page.locator("#hub-name")).to_have_text("1")

    with t.step("Delete wheel opens a confirmation that says what goes"):
        foot.get_by_role("button", name="Delete wheel").click()
        sheet = t.open_sheet()
        expect(sheet.get_by_role("heading", name=f"Delete {name}?")).to_be_visible()
        expect(sheet.get_by_text("Its 1 swatch goes too")).to_be_visible()
        expect(sheet.get_by_text("tag and QR code stop working")).to_be_visible()
        expect(sheet.get_by_text("This can’t be undone")).to_be_visible()
        expect(sheet.get_by_role("button", name="Delete wheel")).to_be_visible()

    with t.step("Cancel keeps the wheel"):
        t.open_sheet().get_by_role("button", name="Cancel").click()
        t.close_sheet_check()
        expect(page.get_by_role("heading", level=1, name=name)).to_be_visible()
        page.reload()
        expect(
            page.get_by_role("group", name=re.compile("1 of 20 swatched"))
        ).to_be_visible()  # server-rendered label

    with t.step("confirm: back on the list without the wheel"):
        foot.get_by_role("button", name="Delete wheel").click()
        t.open_sheet().get_by_role("button", name="Delete wheel").click()
        page.wait_for_url(re.compile(r"/wheels$"))
        expect(page.get_by_role("heading", level=1, name="Wheels")).to_be_visible()
        expect(page.get_by_text(name)).to_have_count(0)

    with t.step("its tag address now opens a 404 page"):
        with t.allow_status(404):
            t.goto(wheel_path)
        expect(page.get_by_text("There is no wheel with that address")).to_be_visible()

    with t.step("the shade it used is untouched"):
        open_shade(t, "Spirit Fingers")
        expect(page.get_by_role("heading", name="Swatched on")).to_have_count(0)


# Scanning


@flow("scan-photo", "Scan a bottle from a photo of its barcode")
def scan_photo(t: Trace) -> None:
    page = t.page
    result = page.locator("#lookup-result")
    directory = Path(tempfile.mkdtemp(prefix="polished-barcode-"))
    photo, _ = make_images(directory)

    with t.step("open the scan page"):
        t.goto("/lookup")
        expect(page.get_by_role("heading", level=1, name="Scan a bottle")).to_be_visible()

    with t.step("a photo of an unknown barcode"):
        page.get_by_label("Take a photo instead").set_input_files(str(photo))
        expect(result.get_by_text(f"New barcode {GTIN}")).to_be_visible(timeout=20000)

    with t.step("pick the shade once"):
        picker = result.get_by_role("searchbox", name="Search shades by name")
        type_and_wait(t, picker, "thirst", "/search")
        result.get_by_role("button", name=re.compile("^Thirst Trap")).click()
        expect(result.get_by_text("Saved.")).to_be_visible()
        expect(result.get_by_role("button", name="Add bottle")).to_be_visible()

    with t.step("the same photo is now a match"):
        page.get_by_label("Take a photo instead").set_input_files(str(photo))
        expect(result.get_by_text("Saved.")).to_have_count(0)
        expect(result.get_by_text(f"Barcode {GTIN} is")).to_be_visible(timeout=20000)
        expect(result.get_by_text("New barcode")).to_have_count(0)

    with t.step("add the bottle from the result"):
        result.get_by_role("button", name="Add bottle").click()
        t.open_sheet().get_by_role("button", name="Add bottle").click()
        t.close_sheet_check()
        expect(result.get_by_text("Added Thirst Trap")).to_be_visible()


# Browsing


@flow("browse-filters", "Browse shades with filters, the badge, the URL and Clear all")
def browse_filters(t: Trace) -> None:
    page = t.page
    count = page.locator("#result-count")
    rows = page.locator("#shade-list").get_by_role("link")
    panel = page.locator("details.filter-toggle")
    total = 0

    def number() -> int:
        return int(count.inner_text().split()[0])

    def open_panel() -> None:
        if panel.get_attribute("open") is None:
            page.get_by_label("Filters", exact=True).click()

    def choose(role: str, label: str) -> None:
        with page.expect_response(lambda r: "/shades" in r.url):
            panel.get_by_role(role, name=label, exact=True).check()

    with t.step("all shades"):
        t.goto("/shades")
        expect(page.get_by_role("heading", level=1, name="Shades")).to_be_visible()
        expect(count).to_contain_text("shades")
        total = number()
        assert total >= 20, total

    with t.step("open the filter panel"):
        page.get_by_label("Filters", exact=True).click()
        expect(panel.get_by_text("Toppers", exact=True)).to_be_visible()

    with t.step("Toppers only"):
        choose("radio", "Toppers")
        expect(count).not_to_have_text(f"{total} shades")
        toppers = number()
        assert 1 <= toppers < total, (toppers, total)

    with t.step("plus the Flakie finish"):
        choose("checkbox", "Flakie")
        expect(page.locator("#filter-count")).to_have_text("2")
        assert 1 <= number() <= toppers
        expect(page.locator("#shade-list")).to_contain_text("Flakie Holo Taco")

    with t.step("Show N shades closes the panel and the URL keeps the filters"):
        page.get_by_role("button", name=re.compile(r"^Show \d+ shades?$")).click()
        expect(page.locator("details.filter-toggle[open]")).to_have_count(0)
        assert "kind=topper" in page.url and "finish=flakie" in page.url, page.url

    with t.step("reload: the same list comes back"):
        before = number()
        page.reload()
        expect(count).to_have_text(f"{before} shade{'' if before == 1 else 's'}")
        expect(page.locator("#filter-count")).to_have_text("2")

    with t.step("Clear all"):
        open_panel()
        page.get_by_role("link", name="Clear all").click()
        expect(count).to_have_text(f"{total} shades")

    with t.step("Retired shades"):
        open_panel()
        choose("radio", "Retired")
        expect(page.locator("#filter-count")).to_have_text("1")
        retired = number()
        assert 1 <= retired < total, retired
        expect(rows.first.locator(".status")).to_contain_text("Retired")

    with t.step("a name search inside the filter"):
        search_box = page.get_by_role("searchbox", name="Search shades")
        with page.expect_response(lambda r: "/shades" in r.url):
            search_box.fill("gold plai")  # a typo-prone half word
        expect(rows.first).to_contain_text("Gold Play Button")


# History


@flow("history", "Bottle history: purchases by month with what they cost")
def history(t: Trace) -> None:
    page = t.page
    today = date.today().isoformat()

    with t.step("two bottles with prices"):
        add_bottle(t, "Thirst Trap", price="15.50", bought_on=today)
        add_bottle(t, "Jam Session", price="14.00", bought_on=today)

    with t.step("the Bottles tab lists both shades"):
        page.get_by_role("navigation", name="Main").get_by_role("link", name="Bottles").click()
        expect(page.get_by_role("heading", level=1, name="Bottles")).to_be_visible()
        expect(page.get_by_text("Thirst Trap").first).to_be_visible()
        expect(page.get_by_text("Jam Session").first).to_be_visible()

    with t.step("History: the year line and the month"):
        page.get_by_role("navigation", name="Bottles view").get_by_role(
            "link", name="History"
        ).click()
        year = page.get_by_role("heading", name=re.compile(rf"^{date.today().year}:"))
        expect(year).to_contain_text("2 bottles")
        expect(year).to_contain_text("$29.50")
        expect(page.get_by_role("link", name=re.compile("Thirst Trap"))).to_be_visible()
        expect(page.get_by_role("link", name=re.compile("Jam Session"))).to_be_visible()

    with t.step("a history row opens its shade"):
        page.get_by_role("link", name=re.compile("Jam Session")).click()
        expect(page.get_by_role("heading", level=1, name="Jam Session")).to_be_visible()
        expect(page.get_by_text("Owned ×1")).to_be_visible()


# Every page once, with something in it


@flow("tabs", "Every tab and the pages behind More, once, with a bottle, a wish and a wheel")
def tabs(t: Trace) -> None:
    page = t.page
    nav = page.get_by_role("navigation", name="Main")

    with t.step("something to look at: a bottle, a wish, a wheel with a swatch"):
        add_bottle(t, "Thirst Trap", price="15.50", bought_on=date.today().isoformat())
        open_shade(t, "Spirit Fingers")
        page.get_by_role("button", name="Add to the wishlist").click()
        expect(page.get_by_role("button", name="On the wishlist, tap to remove")).to_be_visible()
        make_wheel(t, f"Holos {t.uid}")
        swatch(t, 2, [("thirst trap", "Thirst Trap"), ("flakie", "Flakie Holo Taco")])

    with t.step("Home"):
        nav.get_by_role("link", name="Home").click()
        expect(page.get_by_role("heading", level=1, name=GREETING)).to_be_visible()
        expect(page.get_by_text("Recent bottles")).to_be_visible()

    for tab, heading in (
        ("Shades", "Shades"),
        ("Bottles", "Bottles"),
        ("Wheels", "Wheels"),
        ("Wishlist", "Wishlist"),
    ):
        with t.step(f"the {tab} tab"):
            nav.get_by_role("link", name=tab).click()
            expect(page.get_by_role("heading", level=1, name=heading)).to_be_visible()

    with t.step("a shade page with a bottle and a swatch"):
        open_shade(t, "Thirst Trap")
        expect(page.get_by_role("heading", name="Swatched on")).to_be_visible()

    with t.step("More"):
        t.goto("/more")
        expect(page.get_by_role("heading", level=1, name="More")).to_be_visible()

    with t.step("Catalog sync"):
        t.goto("/sync")
        expect(page.get_by_role("heading", level=1)).to_be_visible()

    with t.step("Learned codes"):
        t.goto("/identifiers")
        expect(page.get_by_role("heading", level=1)).to_be_visible()

    with t.step("add a shade by hand"):
        t.goto("/shades/new")
        expect(page.get_by_role("heading", level=1)).to_be_visible()
