"""GET /lookup (the scan and typed-code resolver) and GET /identifiers (learned codes)."""

from fastapi import APIRouter

from .. import identifiers, shades
from . import rows, schemas
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
