"""spec/api/openapi.yaml matches the code, and every recorded fixture matches the spec."""

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from test_api_support import load_script

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "spec" / "api" / "openapi.yaml"
FIXTURES = sorted((ROOT / "spec" / "api" / "fixtures").glob("*.json"))

pytest_plugins = ["test_api_support"]


@pytest.fixture(scope="module")
def spec() -> dict:
    return yaml.safe_load(SPEC.read_text())


def test_the_spec_is_what_the_code_generates():
    expected = load_script("make_api_spec").render()
    assert SPEC.read_text() == expected, "run: uv run python scripts/make_api_spec.py"


def test_the_spec_is_openapi_3_1_with_valid_schemas(spec):
    assert spec["openapi"] == "3.1.0"
    for schema in spec["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)


def test_every_api_operation_is_secured_except_the_sign_in_ones(spec):
    open_paths = {
        "/api/v1/auth/exchange", "/auth/app/start", "/auth/app/finish", "/auth/app/callback",
        "/__test/reset", "/.well-known/apple-app-site-association",
    }  # fmt: skip
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if path in open_paths:
                assert operation["security"] == [], (method, path)
            else:
                assert "security" not in operation and "401" in operation["responses"], (
                    method,
                    path,
                )
    assert spec["security"] == [{"bearer": []}]


def test_the_spec_lists_every_endpoint_of_the_contract(spec):
    wanted = {
        ("get", "/api/v1/me"), ("get", "/api/v1/home"), ("post", "/api/v1/wear/{shade_id}"),
        ("get", "/api/v1/shades"), ("post", "/api/v1/shades"), ("get", "/api/v1/shades/facets"),
        ("get", "/api/v1/shades/{shade_id}"), ("put", "/api/v1/shades/{shade_id}/tip-colour"),
        ("get", "/api/v1/bottles"), ("get", "/api/v1/bottles/history"),
        ("post", "/api/v1/shades/{shade_id}/bottles"), ("patch", "/api/v1/bottles/{bottle_id}"),
        ("delete", "/api/v1/bottles/{bottle_id}"),
        ("get", "/api/v1/wishlist"), ("put", "/api/v1/shades/{shade_id}/wishlist"),
        ("patch", "/api/v1/wishlist/{item_id}"), ("delete", "/api/v1/wishlist/{item_id}"),
        ("post", "/api/v1/wishlist/bought"),
        ("get", "/api/v1/lookup"), ("get", "/api/v1/identifiers"), ("post", "/api/v1/identifiers"),
        ("delete", "/api/v1/identifiers/{identifier_id}"),
        ("get", "/api/v1/wheels"), ("post", "/api/v1/wheels"), ("get", "/api/v1/wheels/{wheel_id}"),
        ("get", "/api/v1/w/{slug}"), ("patch", "/api/v1/wheels/{wheel_id}"),
        ("delete", "/api/v1/wheels/{wheel_id}"),
        ("post", "/api/v1/wheels/{wheel_id}/slug/regenerate"),
        ("post", "/api/v1/wheels/{wheel_id}/slug/take"),
        ("post", "/api/v1/wheels/{wheel_id}/slots/{position}/draft"),
        ("delete", "/api/v1/wheels/{wheel_id}/slots/{position}"),
        ("get", "/api/v1/stacks/{stack_id}"), ("get", "/api/v1/stacks/copy-sources"),
        ("get", "/api/v1/stacks/pick"), ("post", "/api/v1/stacks/{stack_id}/layers"),
        ("patch", "/api/v1/stacks/{stack_id}/layers/{layer_id}"),
        ("delete", "/api/v1/stacks/{stack_id}/layers/{layer_id}"),
        ("post", "/api/v1/stacks/{stack_id}/template"), ("post", "/api/v1/stacks/{stack_id}/save"),
        ("post", "/api/v1/stacks/{stack_id}/cancel"),
        ("get", "/api/v1/sync"), ("post", "/api/v1/sync/run"),
        ("post", "/api/v1/auth/exchange"), ("post", "/api/v1/auth/revoke"),
        ("get", "/api/v1/auth/devices"), ("delete", "/api/v1/auth/devices/{device_id}"),
        ("get", "/.well-known/apple-app-site-association"), ("post", "/__test/reset"),
        ("get", "/auth/app/start"), ("get", "/auth/app/finish"), ("get", "/auth/app/callback"),
    }  # fmt: skip
    have = {(m, p) for p, item in spec["paths"].items() for m in item}
    assert have == wanted


# --- fixtures ------------------------------------------------------------------------------


def operation_of(spec: dict, method: str, path: str) -> tuple[str, dict]:
    """The spec path template and operation a recorded request belongs to (literal paths such as
    /shades/facets win over /shades/{shade_id})."""
    path = path.split("?")[0]
    candidates = []
    for template, item in spec["paths"].items():
        pattern = re.sub(
            r"\{[^}/]+\}", r"[^/]+", re.escape(template).replace(r"\{", "{").replace(r"\}", "}")
        )
        if re.fullmatch(pattern, path) and method.lower() in item:
            candidates.append((template.count("{"), template, item[method.lower()]))
    assert candidates, f"{method} {path} is not in the spec"
    _, template, operation = min(candidates)
    return template, operation


def test_there_are_fixtures():
    assert len(FIXTURES) >= 70


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.stem)
def test_fixture_validates_against_the_spec(spec, fixture):
    recorded = json.loads(fixture.read_text())
    assert set(recorded) == {"request", "status", "body"}
    request = recorded["request"]
    _, operation = operation_of(spec, request["method"], request["path"])
    response = operation["responses"].get(str(recorded["status"]))
    assert response is not None, f"{fixture.stem}: status {recorded['status']} is not documented"
    if recorded["status"] == 204:
        assert recorded["body"] is None and "content" not in response
        return
    schema = response["content"]["application/json"]["schema"]
    validator = Draft202012Validator({"components": spec["components"], **schema})
    errors = sorted(validator.iter_errors(recorded["body"]), key=lambda e: list(e.path))
    assert not errors, f"{fixture.stem}: {errors[0].message} at {list(errors[0].path)}"


def test_every_api_operation_has_a_fixture(spec):
    recorded = set()
    for fixture in FIXTURES:
        request = json.loads(fixture.read_text())["request"]
        template = operation_of(spec, request["method"], request["path"])[0]
        recorded.add((request["method"].lower(), template))
    for template, item in spec["paths"].items():
        if not template.startswith("/api/v1/"):
            continue
        for method in item:
            if (method, template) == ("post", "/api/v1/auth/revoke") or (
                method,
                template,
            ) == ("delete", "/api/v1/auth/devices/{device_id}"):
                continue  # signing a device out would end the recorded session
            assert (method, template) in recorded, f"no fixture for {method.upper()} {template}"


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.stem)
def test_a_write_fixture_records_a_body_that_fits_the_spec(spec, fixture):
    request = json.loads(fixture.read_text())["request"]
    _, operation = operation_of(spec, request["method"], request["path"])
    if "requestBody" not in operation:
        assert "body" not in request
        return
    assert "body" in request, f"{fixture.stem} sent a body the fixture does not record"
    schema = operation["requestBody"]["content"]["application/json"]["schema"]
    validator = Draft202012Validator({"components": spec["components"], **schema})
    errors = sorted(validator.iter_errors(request["body"]), key=lambda e: list(e.path))
    wrong_on_purpose = fixture.stem.startswith("error_validation") or fixture.stem in (
        "error_empty_stack",
    )
    assert wrong_on_purpose or not errors, f"{fixture.stem}: {errors[0].message}"


def test_the_example_token_in_the_fixtures_is_not_a_real_one():
    exchange = json.loads((ROOT / "spec/api/fixtures/auth_exchange.json").read_text())
    assert exchange["body"]["token"].startswith("example-token")
