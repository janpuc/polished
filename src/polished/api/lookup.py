"""GET /lookup (the scan and typed-code resolver), and the learned codes: list, learn, forget."""

from fastapi import APIRouter, Response

from .. import identifiers, shades
from ..db import transaction
from . import rows, schemas
from .errors import invalid, not_found
from .routing import ApiRoute, Conn

router = APIRouter(route_class=ApiRoute, tags=["lookup"])


@router.get("/lookup", response_model=schemas.Lookup, summary="Resolve a barcode, P code or name")
def lookup(conn: Conn, q: str = "", via: str = "typed"):
    """DESIGN 7.2 in one call: a barcode, a number that is not one, a P code, a SKU, then a name
    search. A known barcode counts as used (as on the web)."""
    resolution = identifiers.resolve(conn, q, via if via in ("scan", "typed") else "typed")
    found = resolution.shade
    page: shades.ShadePage | None = resolution.results
    return schemas.Lookup(
        outcome=resolution.outcome,
        code=resolution.code,
        kind=resolution.kind,
        shade=(
            schemas.LookupShade(**rows.shade_row(conn, found).model_dump(), images=found["images"])
            if found
            else None
        ),
        identifier_id=resolution.identifier_id,
        results=(
            schemas.LookupResults(items=rows.shade_rows(conn, page.rows), total=page.total)
            if page
            else None
        ),
    )


@router.get("/identifiers", response_model=schemas.Identifiers, summary="Learned codes")
def identifier_list(conn: Conn):
    """Newest first."""
    learned = identifiers.list_all(conn)
    shade_rows = rows.rows_by_id(conn, [i["shade_id"] for i in learned])
    return schemas.Identifiers(
        items=[
            schemas.Identifier(
                id=i["id"],
                kind=i["kind"],
                value=i["value"],
                shade=shade_rows[i["shade_id"]],
                use_count=i["use_count"],
                created_at=i["created_at"],
                last_used_at=i["last_used_at"],
            )
            for i in learned
        ]
    )


@router.post(
    "/identifiers",
    response_model=schemas.IdentifierLearned,
    status_code=201,
    summary="Teach the app that a code is a shade",
    responses={
        200: {
            "model": schemas.IdentifierLearned,
            "description": "The code was already known (`created` is false) and keeps its shade.",
        },
        404: {"description": "`not_found`: no such shade."},
        422: {"description": "`validation`: `kind` or `value`."},
    },
)
def learn_identifier(conn: Conn, body: schemas.IdentifierRequest, response: Response):
    """A learned code is never overwritten: if `value` already points somewhere, that mapping
    stays, 200 comes back and `identifier.shade_id` says where it points."""
    if body.kind not in identifiers.KINDS:
        raise invalid({"kind": "Kind must be gtin or printed."})
    if conn.execute("select 1 from shade where id = ?", (body.shade_id,)).fetchone() is None:
        raise not_found("No such shade.")
    try:
        with transaction(conn):
            learned = identifiers.learn(conn, body.kind, body.value, body.shade_id)
    except ValueError:
        message = (
            f"\u201c{body.value.strip()}\u201d isn\u2019t a valid barcode number."
            if body.kind == "gtin"
            else f"\u201c{body.value.strip()}\u201d isn\u2019t a P code. Use a code like P259."
        )
        raise invalid({"value": message}) from None
    response.status_code = 201 if learned.created else 200
    return schemas.IdentifierLearned(
        identifier=schemas.IdentifierBrief(
            id=learned.id, kind=learned.kind, value=learned.value, shade_id=learned.shade_id
        ),
        created=learned.created,
        shade=rows.rows_by_id(conn, [learned.shade_id])[learned.shade_id],
    )


@router.delete(
    "/identifiers/{identifier_id}",
    status_code=204,
    summary="Forget a learned code",
    responses={404: {"description": "`not_found`"}},
)
def forget_identifier(conn: Conn, identifier_id: int) -> Response:
    """\"This isn't it\" on a match, or Delete in the list of learned codes."""
    if identifiers.get(conn, identifier_id) is None:
        raise not_found("No such code.")
    identifiers.delete(conn, identifier_id)
    return Response(status_code=204)
