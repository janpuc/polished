from polished.web import day, thumb, words

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


def test_every_tab_of_the_bar_has_a_page(client):
    html = client.get("/").text
    for href in ("/", "/shades", "/bottles", "/wheels", "/wishlist"):
        assert f'class="tab" href="{href}"' in html
        assert client.get(href).status_code == 200
    assert "No wheels yet" in client.get("/wheels").text
    assert client.get("/shades").text.count('aria-current="page"') == 1


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
