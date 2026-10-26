"""spec/api/openapi.yaml, generated from the routes and response models of this package.

`python scripts/make_api_spec.py` writes it; tests/test_api_spec.py fails when the file and the
code disagree. FastAPI's own generator does the schemas; this adds what it cannot know: the bearer
scheme, the shared error body, ETag and 304 on every GET."""

import copy
import warnings

from fastapi import FastAPI

from . import schemas

API_VERSION = "1"
APP_PATHS = frozenset(
    {
        "/.well-known/apple-app-site-association",
        "/__test/reset",
        "/auth/app/start",
        "/auth/app/finish",
        "/auth/app/callback",
    }
)
PUBLIC_OPERATIONS = frozenset(
    {
        "/api/v1/auth/exchange",
        "/.well-known/apple-app-site-association",
        "/__test/reset",
        "/auth/app/start",
        "/auth/app/finish",
        "/auth/app/callback",
    }
)
DESCRIPTION = """\
The JSON API of the Polished iPhone and iPad app (docs/NATIVE.md section 3). Generated from the
server's response models by `scripts/make_api_spec.py`; `fixtures/` holds recorded responses.

* `Authorization: Bearer <token>` is the only credential under `/api/v1` (cookies are ignored).
  A missing, unknown or revoked token is a 401 with the error body, never a redirect.
* Every GET answers `ETag` and honours `If-None-Match` (304, empty body); `Cache-Control: private,
  no-cache`. Every answer carries `X-Polished-Api: 1`.
* Errors are `{"error": {"code", "message", "field"?}}`. Ids are opaque integers, money is cents,
  dates are `YYYY-MM-DD`, timestamps are UTC (`…Z`).
* Additive changes (new optional fields, new endpoints) stay in v1; a breaking change is `/api/v2`.
"""
GET_HEADERS = {
    "ETag": {"description": "A hash of the body.", "schema": {"type": "string"}},
    "X-Polished-Api": {"description": "Always `1`.", "schema": {"type": "string"}},
}
ERROR = {"$ref": "#/components/schemas/ErrorResponse"}


def _error(description: str) -> dict:
    return {
        "description": description,
        "content": {"application/json": {"schema": copy.deepcopy(ERROR)}},
    }


def _refs(node, found: set[str]) -> None:
    """Collects the names of the component schemas a JSON fragment points at."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            found.add(ref.rsplit("/", 1)[1])
        for value in node.values():
            _refs(value, found)
    elif isinstance(node, list):
        for value in node:
            _refs(value, found)


def build_spec(app: FastAPI) -> dict:
    """The OpenAPI 3.1 document of the routes under /api/v1 and the few outside it."""
    with warnings.catch_warnings():
        warnings.simplefilter(
            "ignore"
        )  # the web routes' duplicate operation ids; they are filtered out
        spec = copy.deepcopy(app.openapi())
    spec["paths"] = {
        path: item
        for path, item in spec["paths"].items()
        if path.startswith("/api/v1/") or path in APP_PATHS
    }
    spec["info"] = {
        "title": "Polished API",
        "version": API_VERSION,
        "summary": "The server contract of the Polished native app",
        "description": DESCRIPTION,
    }
    spec["openapi"] = "3.1.0"
    for path, name, summary in (
        ("/auth/app/start", "app_start", "Start the app's sign-in (in a browser session)"),
        ("/auth/app/finish", "app_finish", "Finish the app's sign-in (in a browser session)"),
        (
            "/auth/app/callback",
            "app_callback",
            "The app's https sign-in callback (a harmless page)",
        ),
    ):
        operation = spec["paths"][path]["get"]
        operation.update(operationId=name, summary=summary, tags=["auth"])
    spec["servers"] = [{"url": "https://polished.janpuc.com"}]
    # Shapes the generator emits for FastAPI's own validation errors; ours is ErrorResponse.
    for unused in ("HTTPValidationError", "ValidationError"):
        spec["components"]["schemas"].pop(unused, None)
    error_schema = schemas.ErrorResponse.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    spec["components"]["schemas"].update(error_schema.pop("$defs"))
    spec["components"]["schemas"]["ErrorResponse"] = error_schema
    spec["components"]["securitySchemes"] = {
        "bearer": {"type": "http", "scheme": "bearer", "description": "A per-device API token."}
    }
    spec["security"] = [{"bearer": []}]
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            responses = operation["responses"]
            responses.pop("422", None)
            if path in PUBLIC_OPERATIONS:
                operation["security"] = []
            else:
                responses["401"] = _error("Missing, unknown or revoked token (`unauthorized`).")
            if operation.get("parameters") or operation.get("requestBody"):
                responses["422"] = _error("`validation`, with `field` set.")
            if method == "get" and path.startswith("/api/v1"):
                responses["200"]["headers"] = copy.deepcopy(GET_HEADERS)
                responses["304"] = {"description": "`If-None-Match` matched the ETag."}
            for status, response in list(responses.items()):
                if status.startswith("4") and "content" not in response:
                    response["content"] = {"application/json": {"schema": copy.deepcopy(ERROR)}}
    for path, status in (("/auth/app/start", "302"), ("/auth/app/finish", "302")):
        operation = spec["paths"][path]["get"]
        operation["responses"] = {
            status: {
                "description": "Redirects to `/auth/login?next=/auth/app/finish`."
                if path.endswith("start")
                else "Redirects to `https://<host of PUBLIC_URL>/auth/app/callback?code=<code>`, "
                "which the app claims as its `ASWebAuthenticationSession` callback.",
            },
            "400": {"description": "A page saying the sign-in cannot start or finish."},
        }
    spec["paths"]["/auth/app/callback"]["get"]["responses"] = {
        "200": {
            "description": "A page that says to open Polished. It never reads the `code`. "
            "`Cache-Control: no-store`, `X-Robots-Tag: noindex`, no referrer.",
            "content": {"text/html": {"schema": {"type": "string"}}},
        }
    }
    used: set[str] = set()
    _refs(spec["paths"], used)
    pending = list(used)
    while pending:
        name = pending.pop()
        more: set[str] = set()
        _refs(spec["components"]["schemas"][name], more)
        pending += list(more - used)
        used |= more
    spec["components"]["schemas"] = {
        name: schema for name, schema in spec["components"]["schemas"].items() if name in used
    }
    return spec
