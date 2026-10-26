"""Bottles: GET /bottles and /bottles/history, and the writes (add, edit, archive, delete)."""

from fastapi import APIRouter, Response

from .. import bottles, identifiers, shades
from ..db import transaction
from . import rows, schemas
from .errors import invalid, not_found
from .routing import ApiRoute, AppSettings, Conn, household_today

router = APIRouter(route_class=ApiRoute, tags=["bottles"])

MAX_PRICE_CENTS = 999_999  # what the form's "9999.99" allows
PRICE_MESSAGE = "Use an amount like 15.50."
EDITABLE = ("state", "printed_code", "bought_on", "price_paid_cents", "opened_on", "notes")


def price_text(cents: int | None) -> str:
    """Cents as the form's amount; ValueError outside 0..MAX_PRICE_CENTS."""
    if cents is None:
        return ""
    if not 0 <= cents <= MAX_PRICE_CENTS:
        raise ValueError(cents)
    return f"{cents // 100}.{cents % 100:02d}"


def parse_fields(settings, fields: dict) -> tuple[bottles.BottleInput, dict[str, str]]:
    """The bottle form's rules (bottles.parse_input) over JSON values: a BottleInput and a message
    for each wrong field, in the form's words."""
    errors = {}
    try:
        price = price_text(fields["price_paid_cents"])
    except ValueError:
        price, errors["price_paid_cents"] = "", PRICE_MESSAGE
    values, found = bottles.parse_input(
        state=fields["state"],
        printed_code=fields["printed_code"] or "",
        bought_on=fields["bought_on"] or "",
        price_paid=price,
        opened_on=fields["opened_on"] or "",
        notes=fields["notes"] or "",
        today=household_today(settings),
    )
    renamed = {"price_paid": "price_paid_cents"}
    return values, {renamed.get(name, name): message for name, message in found.items()} | errors


def shade_or_404(conn, shade_id: int) -> dict:
    shade = shades.get_shade(conn, shade_id)
    if shade is None:
        raise not_found("No such shade.")
    return shade


def bottle_or_404(conn, bottle_id: int) -> dict:
    bottle = bottles.get(conn, bottle_id)
    if bottle is None:
        raise not_found("No such bottle.")
    return bottle


@router.get("/bottles", response_model=schemas.BottleGroups, summary="Bottles grouped by shade")
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


@router.get("/bottles/history", response_model=schemas.History, summary="Purchases by month bought")
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


@router.post(
    "/shades/{shade_id}/bottles",
    status_code=201,
    response_model=schemas.BottleCreated,
    summary="Add a bottle of a shade",
    responses={404: {"description": "`not_found`: no such shade."}},
)
def create_bottle(conn: Conn, settings: AppSettings, shade_id: int, body: schemas.BottleRequest):
    """A P code on the bottle is learned (shade identifiers) in the same transaction. A code that
    already meant another shade keeps that mapping; the bottle is saved all the same and
    `learned.previous_shade` says which shade it was."""
    shade_or_404(conn, shade_id)
    values, errors = parse_fields(settings, body.model_dump(include=set(EDITABLE)))
    if errors:
        raise invalid(errors)
    with transaction(conn):
        bottle_id = bottles.add(conn, shade_id, values)
        learned = identifiers.learn_printed(conn, shade_id, values.printed_code)
    result = None
    if learned is not None and (learned.created or learned.shade_id != shade_id):
        previous = None if learned.created else rows.rows_by_id(conn, [learned.shade_id])
        result = schemas.LearnedCode(
            code=learned.value,
            previous_shade=previous[learned.shade_id] if previous else None,
        )
    return schemas.BottleCreated(bottle=rows.bottle(bottles.get(conn, bottle_id)), learned=result)


@router.patch(
    "/bottles/{bottle_id}",
    response_model=schemas.Bottle,
    summary="Change a bottle",
    responses={
        404: {"description": "`not_found`"},
        422: {"description": "`validation`, per field."},
    },
)
def edit_bottle(conn: Conn, settings: AppSettings, bottle_id: int, body: schemas.BottlePatch):
    """Any subset of the fields, `archived` included; fields left out keep their value and `null`
    clears an optional one. A P code is not learned here (as on the web's edit sheet)."""
    bottle = bottle_or_404(conn, bottle_id)
    sent = body.model_fields_set
    if "state" in sent and body.state is None:
        raise invalid({"state": "Pick full, half, low or empty."})
    merged = {name: getattr(body, name) if name in sent else bottle[name] for name in EDITABLE}
    values, errors = parse_fields(settings, merged)
    errors = {name: message for name, message in errors.items() if name in sent}
    if errors:
        raise invalid(errors)
    for name in EDITABLE:
        if name not in sent:  # what was stored stays exactly as stored
            setattr(values, name, bottle[name])
    with transaction(conn):
        bottles.update(conn, bottle_id, values)
        if "archived" in sent and body.archived is not None:
            bottles.set_archived(conn, bottle_id, body.archived)
    return rows.bottle(bottles.get(conn, bottle_id))


@router.delete(
    "/bottles/{bottle_id}",
    status_code=204,
    summary="Delete a bottle entered by mistake",
    responses={404: {"description": "`not_found`"}},
)
def remove_bottle(conn: Conn, bottle_id: int) -> Response:
    bottle_or_404(conn, bottle_id)
    bottles.delete(conn, bottle_id)
    return Response(status_code=204)
