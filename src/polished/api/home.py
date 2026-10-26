"""GET /me and GET /home."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, Request

from .. import bottles, stacks, wheels, wishlist
from . import rows, schemas
from .routing import ApiRoute, AppSettings, Conn

router = APIRouter(route_class=ApiRoute, tags=["home"])

RECENT = 6


def first_name(name: str) -> str:
    """The first word of the name (the part before an @ when the name is an address)."""
    words = name.split("@")[0].split()
    return words[0] if words else ""


@router.get("/me", response_model=schemas.Me, summary="Who is signed in, and the server's facts")
def me(request: Request, conn: Conn, settings: AppSettings):
    user = request.state.user
    return schemas.Me(
        user=schemas.User(sub=user["sub"], name=user["name"], first_name=first_name(user["name"])),
        server=schemas.ServerInfo(
            version=settings.version,
            public_url=settings.public_url,
            store_url=settings.store_url,
            timezone=settings.timezone,
            over_black_available=stacks.over_black_shade(conn, settings.over_black_handle)
            is not None,
            shade_count=conn.execute("select count(*) from shade").fetchone()[0],
        ),
    )


@router.get("/home", response_model=schemas.Home, summary="The home shelf")
def home(
    request: Request,
    conn: Conn,
    settings: AppSettings,
    another: bool = Query(False, description="Pick another shade to wear (needs the wear log)."),
):
    """Wear today, the six newest bottles, the wheel worked on last and the collection numbers.
    `wear` is null until the wear log exists; `another` has no effect before then."""
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    recent = bottles.recent(conn, RECENT)
    shade_rows = rows.rows_by_id(conn, [b["shade_id"] for b in recent])
    wheel = wheels.most_recent(conn)
    tiles = wheels.slot_grid(conn, wheel) if wheel else []
    counts = bottles.counts(conn)
    wished = wishlist.summary(wishlist.items(conn))
    user = request.state.user
    return schemas.Home(
        greeting_name=first_name(user["name"]),
        date=today.isoformat(),
        wear=None,
        recent=[
            schemas.RecentBottle(bottle=rows.bottle(b), shade=shade_rows[b["shade_id"]])
            for b in recent
        ],
        wheel=(
            schemas.WheelWithTiles(
                **rows.wheel_fields(wheel, settings.public_url, tiles),
                tiles=[rows.tile(t) for t in tiles],
            )
            if wheel
            else None
        ),
        counts=schemas.HomeCounts(
            bottles=counts["bottles"],
            shades=counts["shades"],
            wished=wished["count"],
            wished_cents=wished["total_cents"],
        ),
    )
