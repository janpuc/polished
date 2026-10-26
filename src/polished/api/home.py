"""GET /me and GET /home."""

from fastapi import APIRouter, Query, Request

from .. import bottles, stacks, wear, wheels, wishlist
from . import rows, schemas
from .routing import ApiRoute, AppSettings, Conn, household_today

router = APIRouter(route_class=ApiRoute, tags=["home"])

RECENT = 6


def first_name(name: str) -> str:
    """The first word of the name (the part before an @ when the name is an address)."""
    words = name.split("@")[0].split()
    return words[0] if words else ""


def wear_body(conn, today, another: bool) -> schemas.Wear | None:
    shade_id = wear.pick_today(conn, today)
    if shade_id is not None and another:
        shade_id = wear.pick_another(conn, today, not_this=shade_id)
    if shade_id is None:
        return None
    return schemas.Wear(
        shade=rows.rows_by_id(conn, [shade_id])[shade_id],
        bottle=rows.bottle(wear.bottle_for(conn, shade_id)),
        worn_today=wear.worn_today(conn, shade_id, today),
    )


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
    another: bool = Query(
        False,
        description="Pick another owned shade to wear, weighted away from the last 30 days. "
        "Random on every call, never the shade that would be shown without it.",
    ),
):
    """Wear today, the six newest bottles, the wheel worked on last and the collection numbers.
    Today's pick is the same all day (or the shade already worn today); `another` replaces it."""
    today = household_today(settings)
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
        wear=wear_body(conn, today, another),
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
