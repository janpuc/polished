import re
from pathlib import Path

import pytest

from polished.security import CSP

ORIGIN = "http://localhost:8080"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_unsafe_method_without_origin_is_403(client, method):
    response = client.request(method, "/anything", headers={"Origin": ""})
    assert response.status_code == 403


def test_post_with_a_foreign_origin_is_403(client):
    response = client.post("/anything", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403


def test_post_with_a_lookalike_origin_is_403(client):
    response = client.post("/anything", headers={"Origin": "http://localhost:8080.evil.example"})
    assert response.status_code == 403
    assert client.post("/anything", headers={"Origin": "http://localhost:9999"}).status_code == 403


def test_post_with_origin_null_is_403(client):
    assert client.post("/anything", headers={"Origin": "null"}).status_code == 403


def test_post_with_the_right_origin_reaches_the_app(client):
    assert client.post("/anything").status_code == 404


def test_referer_is_used_when_there_is_no_origin(client):
    ok = client.post("/anything", headers={"Origin": "", "Referer": f"{ORIGIN}/shades?q=a"})
    assert ok.status_code == 404
    bad = client.post("/anything", headers={"Origin": "", "Referer": "https://evil.example/x"})
    assert bad.status_code == 403


def test_get_needs_no_origin(client):
    assert client.get("/healthz", headers={"Origin": ""}).status_code == 200


def test_origin_check_runs_before_the_gate(oidc_client):
    """Middleware order of DESIGN 8.3: a signed-out POST without an Origin is 403, with one 401."""
    assert oidc_client.post("/anything", headers={"Origin": ""}).status_code == 403
    assert oidc_client.post("/anything").status_code == 401


def test_security_headers_on_every_kind_of_response(client, oidc_client):
    for response in (
        client.get("/"),
        client.get("/healthz"),
        client.get("/nope"),
        client.get("/static/css/app.css"),
        client.post("/anything", headers={"Origin": ""}),
        oidc_client.get("/"),
        oidc_client.post("/anything"),
    ):
        assert response.headers["content-security-policy"] == CSP
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "same-origin"


def test_csp_follows_design_8_3():
    assert "default-src 'self'" in CSP
    assert "img-src 'self' https://cdn.shopify.com data:" in CSP
    assert "script-src 'self' 'wasm-unsafe-eval'" in CSP
    assert "frame-ancestors 'none'" in CSP
    assert "base-uri 'none'" in CSP
    assert "form-action 'self'" in CSP
    assert "unsafe-inline" not in CSP
    assert "unsafe-eval" not in CSP.replace("wasm-unsafe-eval", "")


def test_html_is_private_no_cache_and_varies_on_htmx_headers(client):
    response = client.get("/")
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "private, no-cache"
    vary = {v.strip().lower() for v in response.headers["vary"].split(",")}
    assert {"hx-request", "hx-history-restore-request"} <= vary


def test_error_pages_that_are_html_are_not_cached_either(oidc_client):
    response = oidc_client.get("/auth/signed-out")
    assert response.headers["cache-control"] == "private, no-cache"


def test_json_and_static_responses_keep_their_own_cache_headers(client):
    assert "private, no-cache" not in client.get("/healthz").headers.get("cache-control", "")
    css = client.get("/static/css/app.css")
    assert css.headers["cache-control" if "cache-control" in css.headers else "etag"]


def test_templates_and_css_have_no_inline_script_style_or_handlers():
    package = Path(__file__).parent.parent / "src" / "polished"
    for path in (package / "templates").glob("*.html"):
        text = path.read_text()
        assert not re.search(r"<script(?![^>]*\bsrc=)", text), path
        assert "<style" not in text, path
        assert not re.search(r"\sstyle=", text), path
        assert not re.search(r"\son[a-z]+=", text), path
