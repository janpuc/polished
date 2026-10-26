"""GET /shades, /shades/facets, /shades/{id}: the same queries as the web's browse and detail pages."""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Query

from .. import bottles, shades, wheels, wishlist
from .. import search as name_search
from . import rows, schemas
from .errors import not_found
from .routing import ApiRoute, AppSettings, Conn

router = APIRouter(prefix="/shades", route_class=ApiRoute, tags=["shades"])


def only_fuzzy_matches(conn, text: str) -> bool:
    """Whether the best match of `text` anywhere in the catalogue is in the typo-tolerant tier,
    i.e. nothing matches by title or tag. (search.py ranks ids; its tier is not exposed, so the
    top shade is matched again.)"""
    words = name_search.tokens(text)
    ranked = name_search.rank(conn, text) if words else []
    if not ranked:
        return False
    top = conn.execute("select title, search_text from shade where id = ?", (ranked[0],)).fetchone()
    entry = name_search._entry(top["title"], top["search_text"])
    match = name_search._match(entry, words, " ".join(words))
    return match is not None and match[0] == name_search.FUZZY


@router.get("", response_model=schemas.ShadePage, summary="Search and filter shades")
def shade_list(
    conn: Conn,
    *,
    q: str = "",
    finish: Annotated[list[str], Query(default_factory=list)],
    color: Annotated[list[str], Query(default_factory=list)],
    collection: str = "",
    kind: str = "",
    status: str = "",
    sort: str = "name",
    owned: str = "",
    page: int = 1,
):
    """The web's /shades, 40 a page. A query with words ranks by relevance (sort=name) and fills
    `marks`; unknown filter values mean no filter."""
    query = shades.ShadeQuery.from_params(q, finish, color, collection, kind, status, sort, owned)
    result = shades.list_shades(conn, query, page)
    return schemas.ShadePage(
        items=rows.shade_rows(conn, result.rows),
        total=result.total,
        page=result.page,
        has_more=result.has_more,
        fuzzy=only_fuzzy_matches(conn, query.q),
    )


@router.get("/facets", response_model=schemas.Facets, summary="The values to offer as filters")
def shade_facets(conn: Conn):
    return shades.facets(conn)


@router.get(
    "/{shade_id}",
    response_model=schemas.ShadeDetail,
    summary="One shade",
    responses={404: {"description": "`not_found`"}},
)
def shade_detail(conn: Conn, settings: AppSettings, shade_id: int):
    shade = shades.get_shade(conn, shade_id)
    if shade is None:
        raise not_found("No such shade.")
    row = rows.shade_row(conn, {**shade, "finishes": shade["tags"]["finish"]})
    wish = wishlist.for_shade(conn, shade_id)
    swatched = wheels.swatched_on(conn, shade_id)
    wheel_ids = {
        w["slug"]: w["id"]
        for w in wheels.list_wheels(conn) + wheels.list_wheels(conn, archived=True)
    }
    tip_source = (
        "override" if shade["swatch_override_hex"] else "sampled" if shade["swatch_hex"] else "none"
    )
    return schemas.ShadeDetail(
        shade=row,
        images=shade["images"],
        tags=shade["tags"],
        sku=shade["sku"],
        handle=shade["handle"],
        store_url=(
            f"{settings.store_url}/products/{quote(shade['handle'])}" if shade["handle"] else None
        ),
        on_sale=shade["on_sale"],
        bottles=[rows.bottle(b) for b in bottles.for_shade(conn, shade_id)],
        wishlist=(
            schemas.WishlistEntry(id=wish["id"], priority=wish["priority"], note=wish["note"])
            if wish
            else None
        ),
        swatched_on=[
            schemas.SwatchedOn(
                wheel_id=wheel_ids[s["slug"]],
                slug=s["slug"],
                name=s["name"],
                position=s["position"],
                stack_id=s["stack_id"],
            )
            for s in swatched
        ],
        tip_source=tip_source,
    )
