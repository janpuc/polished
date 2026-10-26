"""GET /bottles and /bottles/history."""

from fastapi import APIRouter

from .. import bottles
from . import rows, schemas
from .routing import ApiRoute, Conn

router = APIRouter(prefix="/bottles", route_class=ApiRoute, tags=["bottles"])


@router.get("", response_model=schemas.BottleGroups, summary="Bottles grouped by shade")
def bottle_list(conn: Conn, state: str = "", archived: bool = False):
    """`archived=true` lists archived bottles only. An unknown `state` means no filter."""
    groups = bottles.list_groups(conn, state, archived)
    shade_rows = rows.rows_by_id(conn, [g["shade_id"] for g in groups])
    return schemas.BottleGroups(
        groups=[
            schemas.BottleGroup(
                shade=shade_rows[g["shade_id"]], bottles=[rows.bottle(b) for b in g["bottles"]]
            )
            for g in groups
        ]
    )


@router.get("/history", response_model=schemas.History, summary="Purchases by month bought")
def bottle_history(conn: Conn):
    """Every bottle, archived and empty ones included. Totals add the prices paid; a bottle
    without a price counts in `unpriced`."""
    years = bottles.history(conn)
    shade_rows = rows.rows_by_id(
        conn, [r["shade_id"] for y in years for m in y["months"] for r in m["rows"]]
    )
    return schemas.History(
        years=[
            schemas.HistoryYear(
                year=int(y["year"]),
                count=y["count"],
                total_cents=y["total_cents"],
                unpriced=y["unpriced"],
                months=[
                    schemas.HistoryMonth(
                        month=int(m["month"]),
                        label=m["label"],
                        count=m["count"],
                        total_cents=m["total_cents"],
                        unpriced=m["unpriced"],
                        rows=[
                            schemas.HistoryRow(
                                bottle=rows.bottle(r),
                                shade=shade_rows[r["shade_id"]],
                                dated_by_entry=r["dated_by_entry"],
                            )
                            for r in m["rows"]
                        ],
                    )
                    for m in y["months"]
                ],
            )
            for y in years
        ]
    )
