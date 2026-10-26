"""The error body of /api/v1: {"error": {"code", "message", "field"?}} (docs/NATIVE.md 3)."""

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..security import is_api_path

STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation",
    429: "cooldown",
}


# What the web's forms say for a field whose value has the wrong type (a price sent as text, a date
# sent as a number); pydantic's own wording is for programmers.
FIELD_MESSAGES = {
    "price_paid_cents": "Use an amount like 15.50.",
    "price_cents": "Use an amount like 15.50.",
    "bought_on": "Use a date like 2026-10-25.",
    "opened_on": "Use a date like 2026-10-25.",
    "painted_on": "Painted on needs a date like 2026-10-25.",
    "hex": "Pick a colour.",
    "priority": "Priority must be 1, 2 or 3.",
}


class ApiError(Exception):
    """An answer with an error body. `fields` maps every wrong input to its message when several
    are wrong (`field` and `message` then carry the first). `extra` keys sit beside code and
    message (retry_after_s); `headers` go on the response."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        field: str | None = None,
        *,
        fields: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        **extra,
    ):
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message
        self.field = field
        self.fields = fields
        self.headers = headers
        self.extra = extra

    def response(self) -> JSONResponse:
        body = {"code": self.code, "message": self.message}
        if self.field:
            body["field"] = self.field
        if self.fields and len(self.fields) > 1:
            body["fields"] = self.fields
        return JSONResponse(
            {"error": body | self.extra}, status_code=self.status, headers=self.headers
        )


def not_found(message: str = "Not found.") -> ApiError:
    return ApiError(404, "not_found", message)


def validation(message: str, field: str | None = None) -> ApiError:
    return ApiError(422, "validation", message, field)


def invalid(errors: dict[str, str]) -> ApiError:
    """A 422 for one or more wrong inputs, `field name -> message`, the first one leading."""
    field, message = next(iter(errors.items()))
    return ApiError(422, "validation", message, field, fields=dict(errors))


async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
    return exc.response()


async def _http_error(request: Request, exc: StarletteHTTPException):
    if not is_api_path(request.url.path):
        return await http_exception_handler(request, exc)
    code = STATUS_CODES.get(exc.status_code, "server_error" if exc.status_code >= 500 else "error")
    return ApiError(exc.status_code, code, str(exc.detail)).response()


async def _invalid_request(request: Request, exc: RequestValidationError):
    if not is_api_path(request.url.path):
        return await request_validation_exception_handler(request, exc)
    first = exc.errors()[0] if exc.errors() else {}
    location = [str(part) for part in first.get("loc", ()) if part not in ("body", "query", "path")]
    field = ".".join(location) or None
    message = first.get("msg", "Invalid request.")
    if first.get("type") != "missing" and location and location[-1] in FIELD_MESSAGES:
        message = FIELD_MESSAGES[location[-1]]
    return validation(message, field).response()


async def _server_error(request: Request, exc: Exception):
    if not is_api_path(request.url.path):
        return PlainTextResponse("Internal Server Error", status_code=500)
    return ApiError(500, "server_error", "Something went wrong on the server.").response()


def install(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _invalid_request)
    app.add_exception_handler(Exception, _server_error)
