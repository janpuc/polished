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
    """The shade, reached through the browse list like a person would: a page of its own on the
    phone and rail shells, the right-hand panel beside the list on the panel shell (Mac)."""
    t.goto(f"/shades?q={quote(title)}")
    t.page.locator("#shade-list").get_by_role("link").first.click()
    expect(t.page.get_by_role("heading", name=title, exact=True)).to_be_visible()


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
        expect(sheet.get_by_text("its 1 swatch and its tag address")).to_be_visible()
        expect(sheet.get_by_text("The sticker will stop opening anything")).to_be_visible()
        expect(sheet.get_by_text(f"{name}, 1 of 20")).to_be_visible()
        expect(sheet.get_by_role("button", name="Delete wheel")).to_be_visible()

    with t.step("Esc cancels, and the foot's Delete is the red word"):
        page.keyboard.press("Escape")
        t.close_sheet_check()
        expect(page.get_by_role("heading", level=1, name=name)).to_be_visible()
        colour = foot.get_by_role("button", name="Delete wheel").evaluate(
            "el => getComputedStyle(el).color"
        )
        sibling = foot.get_by_role("button", name="Rename").evaluate(
            "el => getComputedStyle(el).color"
        )
        assert colour != sibling, "Delete should not look like the quiet actions beside it"

    with t.step("Cancel keeps the wheel"):
        foot.get_by_role("button", name="Delete wheel").click()
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
        expect(page.get_by_role("status")).to_have_text(f"Deleted {name}")
        expect(page.get_by_role("link", name=re.compile(re.escape(name)))).to_have_count(0)

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
        expect(page.get_by_role("heading", name="Recently added")).to_be_visible()

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


# The three shells (docs/VISUAL.md section 6). The flows branch on the device profile, which is
# the test's way of picking a viewport: the app itself never looks at the user agent.


def shell_of(t: Trace) -> str:
    """phone (iPhone, 390), rail (iPad portrait, 834) or panel (Mac, 1440)."""
    return {"iphone": "phone", "ipad": "rail", "mac": "panel"}[t.device.key]


def drag_grabber(page, x: float, y: float, distance: int, fast: bool = False) -> None:
    """Pulls the sheet's grabber down: slowly (a pull the sheet should take back), or in one quick
    flick (which should dismiss it)."""
    page.mouse.move(x, y)
    page.mouse.down()
    if fast:
        page.mouse.move(x, y + distance, steps=6)
    else:
        for step in range(1, 5):
            page.mouse.move(x, y + distance * step / 4)
            page.wait_for_timeout(120)
    page.mouse.up()


def box_of(locator: Locator) -> dict:
    box = locator.bounding_box()
    assert box is not None, "not on screen"
    return box


@flow("shell-nav", "The navigation of each shell: tab bar, icon rail or labelled sidebar")
def shell_nav(t: Trace) -> None:
    page = t.page
    shell = shell_of(t)
    side = page.locator("nav.side")
    tabbar = page.locator("nav.tabbar")

    with t.step("Home"):
        t.goto("/")
        expect(page.get_by_role("heading", level=1, name=GREETING)).to_be_visible()

    with t.step(f"the {shell} shell shows the right navigation"):
        if shell == "phone":
            expect(tabbar).to_be_visible()
            expect(side).to_be_hidden()
        else:
            expect(side).to_be_visible()
            expect(tabbar).to_be_hidden()
            width = box_of(side)["width"]
            assert (width < 100) == (shell == "rail"), f"side nav is {width}px wide"
        nav = page.get_by_role("navigation", name="Main")
        expect(nav.get_by_role("link", name="Home")).to_have_attribute("aria-current", "page")

    if shell == "panel":
        with t.step("the sidebar has words, a / hint and who is signed in"):
            expect(side.get_by_text("Wishlist")).to_be_visible()
            expect(side.locator(".side-key")).to_have_text("/")
            expect(side.get_by_role("link", name="More")).to_be_visible()

    if shell != "phone":
        with t.step("the content is not hidden behind the navigation"):
            left = box_of(page.get_by_role("heading", level=1, name=GREETING))["x"]
            assert left >= box_of(side)["width"], "the greeting starts under the side nav"

    with t.step("Wheels from the navigation"):
        page.get_by_role("navigation", name="Main").get_by_role("link", name="Wheels").click()
        expect(page.get_by_role("heading", level=1, name="Wheels")).to_be_visible()


@flow("shade-panel", "A shade opens in the right-hand panel on a Mac and as a page elsewhere")
def shade_panel(t: Trace) -> None:
    page = t.page
    shell = shell_of(t)
    rows = page.locator("#shade-list").get_by_role("link")
    panel = page.locator("#panel")

    with t.step("search the list"):
        t.goto("/shades")
        box = page.get_by_role("searchbox", name="Search shades")
        type_and_wait(t, box, "magnetic taco", "/shades")
        expect(rows.first).to_contain_text("Magnetic Taco")
        page.evaluate("window.__listPage = 1")  # survives only while no page is loaded

    if shell != "panel":
        with t.step("a row is a link to the shade's page"):
            rows.first.click()
            expect(page.get_by_role("heading", level=1, name="Magnetic Taco")).to_be_visible()
            expect(panel).to_be_hidden()
            page.go_back()
            expect(page.get_by_role("heading", level=1, name="Shades")).to_be_visible()
        return

    with t.step("a row click opens the panel without a page load"):
        rows.first.click()
        expect(panel.get_by_role("heading", name="Magnetic Taco", exact=True)).to_be_visible()
        assert page.evaluate("window.__listPage") == 1, "the page was reloaded"
        expect(page).to_have_url(re.compile(r"/shades/\d+$"))
        expect(rows.first).to_have_attribute("aria-current", "true")
        expect(panel.get_by_role("button", name="Add bottle")).to_be_visible()
        right = box_of(panel)
        assert right["x"] + right["width"] >= 1439 and right["width"] >= 390, right

    with t.step("another row replaces the shade in the panel"):
        rows.nth(1).click()
        expect(panel.get_by_role("heading", name="Holo Magnetic Taco", exact=True)).to_be_visible()
        expect(rows.nth(1)).to_have_attribute("aria-current", "true")
        expect(page.locator("a.row-link[aria-current]")).to_have_count(1)

    with t.step("Esc closes the panel and the list stays"):
        page.keyboard.press("Escape")
        expect(panel).to_be_hidden()
        assert page.evaluate("window.__listPage") == 1, "the page was reloaded"
        assert "/shades/" not in page.url, page.url
        expect(rows.first).to_contain_text("Magnetic Taco")

    with t.step("the close button closes it too"):
        rows.first.click()
        expect(panel.get_by_role("heading", name="Magnetic Taco", exact=True)).to_be_visible()
        panel.get_by_role("button", name="Close panel").click()
        expect(panel).to_be_hidden()

    with t.step("Back closes the panel, Forward opens it again"):
        rows.first.click()
        expect(panel.get_by_role("heading", name="Magnetic Taco", exact=True)).to_be_visible()
        page.go_back()
        expect(panel).to_be_hidden()
        expect(rows.first).to_contain_text("Magnetic Taco")
        assert page.evaluate("window.__listPage") == 1, "Back reloaded the list"
        page.go_forward()
        expect(panel.get_by_role("heading", name="Magnetic Taco", exact=True)).to_be_visible()

    with t.step("a shade's own address opens the list with the panel"):
        shade_url = page.url
        page.goto(shade_url)
        expect(panel.get_by_role("heading", name="Magnetic Taco", exact=True)).to_be_visible()
        expect(page.get_by_role("heading", level=1, name="Shades")).to_be_visible()
        expect(page.locator("#shade-list a.row-link").first).to_be_visible()
        page.keyboard.press("Escape")
        expect(panel).to_be_hidden()
        assert page.url.endswith("/shades"), page.url


@flow(
    "keyboard", "Keys on a Mac: / searches, arrows move, Enter opens, n adds a bottle, Esc closes"
)
def keyboard(t: Trace) -> None:
    page = t.page
    if shell_of(t) != "panel":
        with t.step("no keyboard hint on a screen without one"):
            t.goto("/shades")
            expect(page.locator(".keys-hint")).to_be_hidden()
        return
    rows = page.locator("#shade-list").get_by_role("link")
    panel = page.locator("#panel")

    with t.step("/ focuses the search field"):
        t.goto("/shades")
        expect(page.locator(".keys-hint")).to_be_hidden()  # until a key was used
        page.keyboard.press("/")
        expect(page.get_by_role("searchbox", name="Search shades")).to_be_focused()
        type_and_wait(
            t, page.get_by_role("searchbox", name="Search shades"), "magnetic taco", "/shades"
        )

    with t.step("the hint line appears with the first keyboard focus"):
        expect(page.locator(".keys-hint")).to_be_visible()
        expect(page.get_by_text("close panel")).to_be_visible()

    with t.step("the first result is selected and Enter opens it"):
        expect(rows.first).to_have_attribute("aria-current", "true")
        page.keyboard.press("Enter")
        expect(panel.get_by_role("heading", name="Magnetic Taco", exact=True)).to_be_visible()

    with t.step("n opens Add bottle in the right-hand sheet"):
        page.locator("body").click(position={"x": 700, "y": 600})
        page.keyboard.press("n")
        sheet = t.open_sheet()
        expect(sheet.get_by_role("heading", name="Add bottle")).to_be_visible()
        right = box_of(sheet)
        assert right["x"] + right["width"] >= 1439 and right["height"] >= 890, right

    with t.step("Esc closes the sheet first, then the panel"):
        page.keyboard.press("Escape")
        t.close_sheet_check()
        expect(panel).to_be_visible()
        page.keyboard.press("Escape")
        expect(panel).to_be_hidden()

    with t.step("the arrows move the selection and / works again"):
        page.keyboard.press("Escape")
        page.locator("body").click(position={"x": 700, "y": 700})
        page.keyboard.press("ArrowDown")
        page.keyboard.press("ArrowDown")
        expect(rows.nth(1)).to_have_attribute("aria-current", "true")
        page.keyboard.press("ArrowUp")
        expect(rows.first).to_have_attribute("aria-current", "true")
        page.keyboard.press("/")
        expect(page.get_by_role("searchbox", name="Search shades")).to_be_focused()


@flow("sheet-shells", "The sheet is a bottom sheet, a centred modal or a right panel by width")
def sheet_shells(t: Trace) -> None:
    page = t.page
    shell = shell_of(t)
    vw = page.viewport_size["width"]

    with t.step("open Add bottle on a shade"):
        open_shade(t, "Thirst Trap")
        page.get_by_role("button", name="Add bottle").click()
        sheet = t.open_sheet()
        expect(sheet.get_by_role("heading", name="Add bottle")).to_be_visible()

    with t.step(f"the {shell} shape"):
        sheet = t.open_sheet()
        page.wait_for_timeout(500)
        box = box_of(sheet)
        grabber = sheet.locator(".grabber")
        if shell == "phone":
            assert box["x"] <= 1 and box["width"] >= vw - 2, box
            expect(grabber).to_be_visible()
        elif shell == "rail":
            assert box["width"] <= 561 and box["x"] > 20, box
            assert abs(box["x"] + box["width"] / 2 - vw / 2) < 2, "not centred"
            expect(grabber).to_be_hidden()
        else:
            assert 395 <= box["width"] <= 401 and box["x"] + box["width"] >= vw - 1, box
            expect(grabber).to_be_hidden()
            expect(sheet.get_by_role("button", name="Cancel")).to_be_visible()

    if shell == "phone":
        with t.step("a short drag on the grabber springs back"):
            grab = box_of(t.open_sheet().locator(".grabber"))
            x, y = grab["x"] + grab["width"] / 2, grab["y"] + grab["height"] / 2
            drag_grabber(page, x, y, 40)
            page.wait_for_timeout(500)
            t.open_sheet()

        with t.step("a long drag on the grabber dismisses the sheet"):
            grab = box_of(t.open_sheet().locator(".grabber"))
            x, y = grab["x"] + grab["width"] / 2, grab["y"] + grab["height"] / 2
            drag_grabber(page, x, y, 420, fast=True)
            t.close_sheet_check()
    else:
        with t.step("Cancel closes it"):
            t.open_sheet().get_by_role("button", name="Cancel").click()
            t.close_sheet_check()


@flow("builder-panel", "The builder on a Mac is a right-hand panel beside the ring")
def builder_panel(t: Trace) -> None:
    page = t.page
    name = f"Panel wheel {t.uid}"
    with t.step("a wheel"):
        make_wheel(t, name)

    with t.step("tap slot 2: the builder opens"):
        page.get_by_role("button", name=re.compile(r"^Slot 2, empty")).click()
        sheet = t.open_sheet()
        page.wait_for_timeout(500)
        expect(sheet.get_by_role("heading", name="Slot 2")).to_be_visible()
        if shell_of(t) == "panel":
            box = box_of(sheet)
            assert 395 <= box["width"] <= 401 and box["x"] + box["width"] >= 1439, box
            ring = box_of(page.locator(".ring"))
            assert ring["x"] + ring["width"] <= box["x"] + 1, "the ring is under the panel"

    with t.step("add a layer: the footer stays in view"):
        pick_layer(t, "magnetic taco", "Magnetic Taco")
        sheet = t.open_sheet()
        save = sheet.get_by_role("button", name="Save swatch")
        expect(save).to_be_enabled()
        box = box_of(save)
        assert box["y"] + box["height"] <= page.viewport_size["height"], "Save is below the fold"

    with t.step("Esc closes the builder and the draft dot stays"):
        page.keyboard.press("Escape")
        t.close_sheet_check()
        expect(page.locator("#slot-2")).to_be_visible()


@flow("tag-page", "The tag page: Copy address first, the NFC Tools steps by shell")
def tag_page(t: Trace) -> None:
    page = t.page
    shell = shell_of(t)
    name = f"Tag wheel {t.uid}"
    written = "Open NFC Tools on your iPhone and tap Write."

    with t.step("make a wheel: its tag page opens"):
        t.goto("/wheels")
        page.get_by_label("Name").fill(name)
        page.get_by_role("button", name="Make a wheel").click()
        expect(page.get_by_role("heading", level=1, name="Tag and QR code")).to_be_visible()
        expect(page.get_by_role("button", name="Copy address")).to_be_visible()

    if shell == "phone":
        with t.step("the phone shows the steps and the plain lede"):
            expect(page.get_by_role("heading", name="Write the tag")).to_be_visible()
            expect(page.locator(".tag-steps-narrow").get_by_text(written)).to_be_visible()
            expect(page.locator(".tag-steps-wide")).to_be_hidden()
            expect(page.get_by_text("Scan this with the iPhone camera")).to_be_hidden()
    else:
        with t.step("the wide shells send you to the iPhone, with the steps collapsed"):
            expect(page.get_by_text("Scan this with the iPhone camera")).to_be_visible()
            expect(page.get_by_text("Or write it from the Polished app on iPhone")).to_be_visible()
            wide = page.locator(".tag-steps-wide")
            expect(page.locator(".tag-steps-narrow")).to_be_hidden()
            expect(wide.get_by_text(written)).to_be_hidden()
            wide.get_by_text("Write the tag").click()
            expect(wide.get_by_text(written)).to_be_visible()

    with t.step("Copy address says it copied"):
        page.get_by_role("button", name="Copy address").click()
        expect(
            page.get_by_role("button", name=re.compile("Copied|Select and copy"))
        ).to_be_visible()


# Home, the shelf (docs/VISUAL.md section 6)

PHONE_SCREEN_PX = 844  # the spec's phone: 390 by 844
SURFACE = {"light": "rgb(254, 252, 251)", "dark": "rgb(32, 19, 29)"}
VELVET = {"light": "rgb(254, 252, 251)", "dark": "rgb(15, 7, 14)"}


def animation_names(page) -> list[str]:
    """The CSS animations that are running or holding their end state on the page."""
    return page.evaluate("document.getAnimations().map((a) => a.animationName)")


def wait_for_animation(page, name: str) -> None:
    page.wait_for_function(
        "(name) => document.getAnimations().some((a) => a.animationName === name)", arg=name
    )


@flow("home-empty", "Home with nothing yet: unpainted tips, the empty rack and ring, one button")
def home_empty(t: Trace) -> None:
    page = t.page
    hero = page.locator("#wear-slot")

    with t.step("Home says there is nothing to wear and where to start"):
        t.goto("/")
        expect(page.get_by_role("heading", level=1, name=GREETING)).to_be_visible()
        expect(page.get_by_role("heading", level=2, name="Wear today")).to_be_visible()
        expect(hero.get_by_role("heading", name="Nothing to wear yet")).to_be_visible()
        expect(hero.get_by_role("link", name="Scan a bottle")).to_be_visible()
        expect(hero.locator(".tip")).to_have_count(1)
        expect(hero.get_by_role("button", name="I wore this")).to_have_count(0)

    with t.step("the empty rack is unpainted tips on the ledge and one line"):
        expect(page.get_by_text("Bottles you add stand here, newest first.")).to_be_visible()
        expect(page.locator(".rack-list.is-empty .tip")).to_have_count(3)
        expect(page.locator(".rack-list.is-empty img")).to_have_count(0)
        expect(page.get_by_role("link", name=re.compile(r"^All \d+ bottles"))).to_have_count(0)

    with t.step("no wheel: the unpainted ring and Make one"):
        card = page.get_by_role("link", name=re.compile("No wheels yet"))
        expect(card).to_be_visible()
        expect(card).to_contain_text("Make one")
        expect(card).to_have_attribute("href", "/wheels")
        expect(card.locator(".slot.is-filled")).to_have_count(0)
        expect(page.get_by_role("heading", level=2, name="Collection")).to_have_count(0)

    with t.step("the empty wishlist draws the unpainted tip"):
        t.goto("/wishlist")
        expect(page.get_by_role("heading", name="Nothing on the wishlist")).to_be_visible()
        expect(page.locator(".empty-state .tip")).to_have_count(1)


@flow("home-shelf", "Home as a shelf: hero, rack on its ledge, wheel card, collection, two columns")
def home_shelf(t: Trace) -> None:
    page = t.page
    shell = shell_of(t)

    with t.step("something on the shelf: three bottles, a wish and a wheel with a swatch"):
        for title in ("Thirst Trap", "Spirit Fingers", "Magnetic Taco"):
            add_bottle(t, title)
        open_shade(t, "Mermaid Jelly")
        page.get_by_role("button", name="Add to the wishlist").click()
        expect(page.get_by_role("button", name="On the wishlist, tap to remove")).to_be_visible()
        make_wheel(t, f"Holos {t.uid}")
        swatch(t, 1, [("thirst trap", "Thirst Trap")])

    with t.step("Home has every part of the shelf"):
        t.goto("/")
        expect(page.get_by_role("heading", level=1, name=GREETING)).to_be_visible()
        for heading in ("Wear today", "Recently added", "Wheels", "Collection"):
            expect(page.get_by_role("heading", level=2, name=heading)).to_be_visible()
        expect(page.get_by_role("button", name="I wore this")).to_be_visible()
        expect(page.get_by_role("button", name="Another")).to_be_visible()
        expect(page.locator(".rack-item")).to_have_count(3)
        expect(page.get_by_role("link", name="All 3 bottles")).to_be_visible()
        expect(page.get_by_role("link", name=re.compile(f"Holos {t.uid}"))).to_be_visible()
        expect(page.locator(".count-n")).to_have_text(["3", "3", "1"])
        for link in ("Browse all shades", "Toppers", "New and in stock"):
            expect(page.get_by_role("link", name=link)).to_be_visible()

    with t.step(f"the {shell} shell sets the sections in its columns", full_page=True):
        hero = box_of(page.locator(".wear"))
        rack = box_of(page.locator(".rack"))
        card = box_of(page.locator(".home-wheel"))
        links = box_of(page.locator(".home-links"))
        if shell == "phone":
            assert card["y"] > rack["y"] + rack["height"], "the wheel card follows the rack"
            assert links["y"] > card["y"], "the links come last"
            assert abs(card["x"] - hero["x"]) < 1, "one column"
            assert (
                rack["x"] <= 1
                and rack["width"] >= page.evaluate("document.documentElement.clientWidth") - 1
            ), "the ledge bleeds"
            height = page.evaluate("document.documentElement.scrollHeight")
            assert height <= 2 * PHONE_SCREEN_PX, f"Home is {height}px tall"
        else:
            assert card["x"] > hero["x"] + hero["width"], "the wheel card sits right of the hero"
            assert abs(card["y"] - hero["y"]) < 3, "the two columns start level"
            assert abs(links["x"] - card["x"]) < 1, "the links are in the second column"
            assert rack["y"] > hero["y"] + hero["height"], "the rack sits under the hero"
            assert abs(rack["x"] - hero["x"]) < 1 and abs(rack["width"] - hero["width"]) < 1, (
                "the rack and the hero share the left column"
            )

    with t.step("the ledge runs under the tips and the rack snaps"):
        ledge = page.evaluate(
            """() => {
              const rack = document.querySelector('.rack');
              const tip = rack.querySelector('.tip').getBoundingClientRect();
              const before = getComputedStyle(rack, '::before');
              const list = getComputedStyle(rack.querySelector('.rack-list'));
              return {
                ledgeTop: rack.getBoundingClientRect().top + parseFloat(before.top),
                foot: tip.bottom, height: before.height, snap: list.scrollSnapType,
              };
            }"""
        )
        assert abs(ledge["ledgeTop"] - ledge["foot"]) <= 1, ledge
        assert ledge["height"] == "1.5px" and "x mandatory" in ledge["snap"], ledge

    with t.step(f"the hero plate is the {'velvet' if t.scheme == 'dark' else 'surface'}"):
        plate = page.locator(".wear").evaluate("(el) => getComputedStyle(el).backgroundColor")
        assert plate == VELVET[t.scheme], plate
        card_fill = page.locator(".home-wheel").evaluate(
            "(el) => getComputedStyle(el).backgroundColor"
        )
        assert card_fill == SURFACE[t.scheme], card_fill

    with t.step("the display face is on the greeting, the shade, the wheel and the numbers"):
        for selector in (".greeting", ".wear-name", ".home-wheel-name", ".count-n"):
            face = page.locator(selector).first.evaluate("(el) => getComputedStyle(el).fontFamily")
            assert face.startswith("Fraunces"), (selector, face)
        sizes = page.evaluate(
            "[...document.querySelectorAll('.wear-name, .home-wheel-name, .count-n')]"
            ".map((el) => parseFloat(getComputedStyle(el).fontSize))"
        )
        assert min(sizes) >= 22, sizes

    with t.step("a rack tip opens its shade"):
        page.locator(".rack-item").first.click()
        expect(page.get_by_role("heading", level=1)).to_be_visible()
        assert "/shades/" in page.url

    with t.step("switching the system theme does not smear"):
        t.goto("/")
        expect(page.locator(".wear")).to_be_visible()
        other = "light" if t.scheme == "dark" else "dark"
        before = page.locator("body").evaluate("(el) => getComputedStyle(el).backgroundColor")
        page.emulate_media(color_scheme=other)
        page.wait_for_function(
            "(was) => getComputedStyle(document.body).backgroundColor !== was", arg=before
        )
        page.wait_for_function(
            "() => !document.documentElement.classList.contains('theme-switching')"
        )
        page.emulate_media(color_scheme=t.scheme)
        expect(page.locator(".wear")).to_be_visible()


@flow("wear-today", "Wear today: I wore this flips the hero, Another picks a different shade")
def wear_today(t: Trace) -> None:
    page = t.page
    title = page.locator(".wear-name")

    with t.step("two bottles to choose from"):
        add_bottle(t, "Thirst Trap")
        add_bottle(t, "Spirit Fingers")
        t.goto("/")
        expect(title).to_be_visible()
        expect(page.get_by_role("button", name="I wore this")).to_be_visible()

    with t.step("I wore this flips the hero to Worn today, without a page load"):
        first = title.inner_text()
        page.evaluate("window.__stay = 'same page'")
        page.get_by_role("button", name="I wore this").click()
        expect(page.locator("#wear-slot").get_by_text("Worn today")).to_be_visible()
        expect(page.get_by_role("button", name="I wore this")).to_have_count(0)
        expect(title).to_have_text(first)
        assert page.evaluate("window.__stay") == "same page", "the page reloaded"
        assert page.evaluate("document.activeElement.id") == "wear-primary", "focus was lost"

    with t.step("a reload still says Worn today"):
        page.reload()
        expect(page.locator("#wear-slot").get_by_text("Worn today")).to_be_visible()
        expect(title).to_have_text(first)

    with t.step("Another shows a different shade with one sweep across its tip"):
        page.get_by_role("button", name="Another").click()
        expect(title).not_to_have_text(first)
        wait_for_animation(page, "tip-sweep")
        expect(page.get_by_role("button", name="I wore this")).to_be_visible()
        expect(page.locator(".wear")).to_have_class(re.compile(r"\bis-arriving\b"))
        assert "tip-arrive" not in animation_names(page), "the hero only sweeps"

    with t.step("wearing it too: both are Worn today in turn"):
        second = title.inner_text()
        page.get_by_role("button", name="I wore this").click()
        expect(page.locator("#wear-slot").get_by_text("Worn today")).to_be_visible()
        page.reload()
        expect(title).to_have_text(second)

    with t.step("under reduced motion Another is a fade, with no sweep"):
        page.emulate_media(reduced_motion="reduce")
        page.get_by_role("button", name="Another").click()
        expect(title).not_to_have_text(second)
        wait_for_animation(page, "tip-fade")
        names = animation_names(page)
        assert "tip-sweep" not in names and "tip-arrive" not in names, names


@flow(
    "bottle-arrives", "A new bottle arrives on the rack once, and the tip carries over to its shade"
)
def bottle_arrives(t: Trace) -> None:
    page = t.page
    nav = page.get_by_role("navigation", name="Main")
    first = page.locator(".rack-item").first

    with t.step("add a bottle: Home has it first on the rack, arriving"):
        add_bottle(t, "Thirst Trap")
        nav.get_by_role("link", name="Home").click()
        expect(page.get_by_role("heading", level=1, name=GREETING)).to_be_visible()
        expect(first).to_contain_text("Thirst Trap")
        expect(first).to_have_class(re.compile(r"\bis-arriving\b"))
        wait_for_animation(page, "tip-arrive")
        wait_for_animation(page, "tip-sweep")

    with t.step("it arrives once: a reload leaves it standing"):
        page.reload()
        expect(first).to_contain_text("Thirst Trap")
        expect(page.locator(".rack-item.is-arriving")).to_have_count(0)
        names = animation_names(page)
        assert "tip-arrive" not in names and "tip-sweep" not in names, names

    with t.step("under reduced motion the next one fades in, without scale or sweep"):
        page.emulate_media(reduced_motion="reduce")
        add_bottle(t, "Spirit Fingers")
        nav.get_by_role("link", name="Home").click()
        expect(first).to_contain_text("Spirit Fingers")
        expect(first).to_have_class(re.compile(r"\bis-arriving\b"))
        wait_for_animation(page, "tip-fade")
        names = animation_names(page)
        assert "tip-arrive" not in names and "tip-sweep" not in names, names
        page.emulate_media(reduced_motion="no-preference")

    with t.step("a rack tip is named for the view transition as its shade is revealed"):
        page.add_init_script(
            """addEventListener('pagereveal', (event) => setTimeout(() => {
              const tip = document.querySelector('.detail-head .tip');
              sessionStorage.setItem('vt', JSON.stringify({
                transition: !!event.viewTransition,
                name: tip ? tip.style.viewTransitionName : null,
              }));
            }, 0));"""
        )
        t.goto("/")
        first.click()
        expect(page.get_by_role("heading", level=1, name="Spirit Fingers")).to_be_visible()
        seen = page.evaluate("JSON.parse(sessionStorage.getItem('vt') || 'null')")
        if seen and seen["transition"]:  # a browser without cross-document transitions skips this
            shade = re.search(r"/shades/(\d+)", page.url).group(1)
            assert seen["name"] == f"tip-{shade}", seen
