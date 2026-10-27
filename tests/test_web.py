import re

from polished.web import date_words, day, thumb, words

URL = "https://cdn.shopify.com/s/files/1/x/files/a.jpg?v=1"


def test_thumb_with_a_height_asks_the_cdn_for_a_centre_crop():
    assert thumb(URL, 96) == f"{URL}&width=96"
    assert thumb(URL, 96, 128) == f"{URL}&width=96&height=128&crop=center"
    assert thumb("https://cdn.shopify.com/a.jpg", 96, 128).startswith(
        "https://cdn.shopify.com/a.jpg?width=96&height=128&crop=center"
    )
    assert thumb(None, 96, 128) == ""


def test_words_and_day_read_like_people_say_them():
    assert words(["glitter", "rose-gold"]) == "Glitter, rose gold"
    assert words([]) == ""
    assert day("2026-10-01") == "1 Oct 2026"
    assert day("not a date") == "not a date" and day(None) == ""


def test_date_words_say_today_and_yesterday_and_otherwise_the_date_and_the_weekday():
    assert date_words("2026-10-26", "2026-10-26") == ("Today", "26 Oct 2026")
    assert date_words("2026-10-25", "2026-10-26") == ("Yesterday", "25 Oct 2026")
    assert date_words("2026-07-21", "2026-10-26") == ("21 Jul 2026", "Tuesday")
    assert date_words("", "2026-10-26") == ("", "") == date_words(None, "2026-10-26")
    assert date_words("not a date", "2026-10-26") == ("", "")


def test_every_tab_of_the_bar_has_a_page(client):
    html = client.get("/").text
    for href in ("/", "/shades", "/bottles", "/wheels", "/wishlist"):
        assert f'class="tab" href="{href}"' in html
        assert client.get(href).status_code == 200
    assert "No wheels yet" in client.get("/wheels").text
    # the side nav and the tab bar each mark the page they are on
    assert client.get("/shades").text.count('aria-current="page"') == 2


def test_pages_that_need_no_account_have_no_tab_bar(client):
    assert 'class="tabbar"' not in client.get("/offline").text
    assert 'class="tabbar"' not in client.get("/signed-out").text


def test_every_icon_a_page_uses_exists_in_the_sprite(client):
    import re
    from pathlib import Path

    sprite = (Path(__file__).parents[1] / "src/polished/static/icons/ui.svg").read_text()
    ids = set(re.findall(r'<symbol[^>]*id="([^"]+)"', sprite))
    for path in ("/", "/shades", "/bottles", "/wheels", "/wishlist", "/lookup"):
        used = set(re.findall(r'ui\.svg\?v=[^#"]*#([\w-]+)', client.get(path).text))
        assert used, path
        assert used <= ids, (path, used - ids)


def test_fraunces_is_vendored_with_its_licence_and_the_hashes_recorded():
    import hashlib

    from polished.web import STATIC_DIR

    folder = STATIC_DIR / "vendor" / "fraunces"
    versions = (STATIC_DIR / "vendor" / "VERSIONS.txt").read_text()
    for name in ("fraunces-latin.woff2", "fraunces-latin-ext.woff2", "OFL.txt"):
        digest = hashlib.sha256((folder / name).read_bytes()).hexdigest()
        assert digest in versions, name
    assert "SIL Open Font License" in (folder / "OFL.txt").read_text()
    assert "registry.npmjs.org/@fontsource-variable/fraunces" in versions


def test_the_latin_font_is_preloaded_and_served_from_the_app(client):
    html = client.get("/").text
    assert (
        '<link rel="preload" href="/static/vendor/fraunces/fraunces-latin.woff2" as="font" '
        'type="font/woff2" crossorigin>' in html
    )
    font = client.get("/static/vendor/fraunces/fraunces-latin.woff2")
    assert font.status_code == 200 and font.content[:4] == b"wOF2"
    assert "fonts.googleapis" not in html and "fonts.gstatic" not in html


def test_the_display_face_is_used_by_four_roles_and_nothing_else():
    """docs/VISUAL.md section 3: the greeting, the shade title, the wheel name and the big
    numbers; never a row, button, label, chip, tab or summary."""
    from polished.web import STATIC_DIR

    css = re.sub(r"/\*.*?\*/", "", (STATIC_DIR / "css" / "app.css").read_text(), flags=re.S)
    selectors = set()
    for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        if "font-family: var(--display)" in rule.group(2):
            selectors |= {part.strip() for part in rule.group(1).split(",")}
    assert selectors == {
        ".greeting",
        ".title-detail",
        ".wear-name",
        ".title-wheel",
        ".wheel-name",
        ".home-wheel-name",
        ".hub-name",
        ".count-n",
    }
    assert "background-clip: text" not in css  # no gradient text


def test_every_page_with_tabs_has_the_side_nav_beside_the_tab_bar(client):
    html = client.get("/shades").text
    nav = re.search(r'<nav class="side".*?</nav>', html, re.S).group(0)
    for href in ("/", "/shades", "/bottles", "/wheels", "/wishlist", "/more"):
        assert f'class="side-link" href="{href}"' in nav
    assert 'class="side-key"' in nav and "Signed in as" in nav
    assert 'aria-current="page"' in re.search(
        r'<a class="side-link" href="/shades".*?</a>', nav
    ).group(0)
    for script in ("sheet.js", "panel.js", "keys.js"):
        assert f'/static/js/{script}?v=dev"' in html
    # pages without tabs (offline, signed out) have neither navigation
    assert 'class="side"' not in client.get("/offline").text


def test_the_more_page_marks_more_in_the_side_nav(client):
    html = client.get("/more").text
    assert re.search(r'<a class="side-link" href="/more"[^>]*aria-current="page"', html)
