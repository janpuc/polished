import re
import struct
from pathlib import Path

from conftest import make_client, make_settings

from polished.web import STATIC_DIR

ICONS = {
    "apple-touch-icon.png": 180,
    "icon-192.png": 192,
    "icon-512.png": 512,
    "icon-maskable-512.png": 512,
}


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_manifest_fields(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    manifest = response.json()
    assert manifest["name"] == manifest["short_name"] == "Polished"
    assert manifest["start_url"] == "/?source=pwa"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["background_color"] and manifest["theme_color"]
    sizes = {(i["sizes"], i.get("purpose", "any")) for i in manifest["icons"]}
    assert sizes == {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")}


def test_every_icon_the_manifest_and_the_pages_name_exists_at_its_size(client):
    for icon in client.get("/manifest.webmanifest").json()["icons"]:
        size = int(icon["sizes"].split("x")[0])
        assert png_size(STATIC_DIR / icon["src"].removeprefix("/static/")) == (size, size)
    for name, size in ICONS.items():
        assert png_size(STATIC_DIR / "icons" / name) == (size, size)
        assert client.get(f"/static/icons/{name}").status_code == 200


def test_pages_link_the_manifest_and_the_apple_touch_icon(client):
    html = client.get("/").text
    assert '<link rel="manifest" href="/manifest.webmanifest">' in html
    assert '<link rel="apple-touch-icon" href="/static/icons/apple-touch-icon.png">' in html
    assert '<meta name="apple-mobile-web-app-capable" content="yes">' in html
    assert '<meta name="apple-mobile-web-app-title" content="Polished">' in html
    assert "viewport-fit=cover" in html
    assert '"historyCacheSize": 0' in html and '"includeIndicatorStyles": false' in html
    assert 'src="/static/js/register-sw.js?v=dev"' in html


def test_service_worker_is_served_fresh_with_the_version(tmp_path):
    client = make_client(make_settings(tmp_path, version="1.2.3"))
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["content-type"].startswith("text/javascript")
    assert 'const VERSION = "1.2.3";' in response.text
    assert client.head("/sw.js").headers["cache-control"] == "no-cache"


def test_service_worker_follows_the_rules_of_design_11(client):
    js = client.get("/sw.js").text
    assert "polished-static-" in js and "caches.delete" in js  # versioned cache, old ones go
    assert 'request.method !== "GET"' in js
    assert "url.origin !== self.location.origin" in js
    assert 'request.mode === "navigate"' in js and 'caches.match("/offline")' in js
    assert 'startsWith("/static/")' in js
    assert "fetch(request).then" in js and "cache.put" in js
    # Never HTML, partials or API responses: only /static is ever put in the cache.
    assert js.count("cache.put") == 1


def test_everything_the_service_worker_precaches_is_served(tmp_path):
    client = make_client(make_settings(tmp_path, version="1.2.3"))
    js = client.get("/sw.js").text
    block = re.search(r"const PRECACHE = \[(.*?)\];", js, re.S).group(1)
    urls = [u.replace("${SUFFIX}", "?v=1.2.3") for u in re.findall(r'`?"?(/[^`"]+)`?"?,', block)]
    assert "/offline" in urls and len(urls) >= 5
    for url in urls:
        assert client.get(url).status_code == 200, url


def test_offline_page_is_public_and_says_what_to_do(oidc_client):
    response = oidc_client.get("/offline")
    assert response.status_code == 200
    assert "Polished needs a connection" in response.text
    assert "Sign out" not in response.text and 'href="/shades"' not in response.text


def test_manifest_service_worker_and_icons_are_public(oidc_client):
    assert oidc_client.get("/manifest.webmanifest").status_code == 200
    assert oidc_client.get("/sw.js").status_code == 200
    assert oidc_client.get("/static/icons/apple-touch-icon.png").status_code == 200
    assert oidc_client.get("/shades").status_code in (302, 401)
