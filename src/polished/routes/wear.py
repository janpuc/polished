"""Wear today on the web: the hero of Home, "I wore this" and "Another" (DESIGN 17.7). The rules
live in wear.py, which the API shares; this module only turns a shade into the hero's context and
answers the two requests the hero makes."""

import sqlite3
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from .. import shades, wear
from ..db import get_conn
from ..web import is_partial_request, render

router = APIRouter()

Conn = Annotated[sqlite3.Connection, Depends(get_conn)]

# How a bottle's level reads after its P code: "P12, half left".
LEVEL_WORDS = {"full": "full", "half": "half left", "low": "running low"}


def household_today(request: Request) -> date:
    return wear.local_today(request.app.state.settings.timezone)


def facts_line(finishes: list[str], bottle: dict | None) -> str:
    """The hero's one line of facts: the finishes, then the bottle that would be worn."""
    parts = []
    if finishes:
        parts.append(", ".join(f.replace("-", " ") for f in finishes))
    if bottle is not None:
        level = LEVEL_WORDS.get(bottle["state"], "")
        parts.append(", ".join(p for p in (bottle["printed_code"], level) if p))
    text = ". ".join(p for p in parts if p)
    return text[:1].upper() + text[1:]


def hero_context(conn: sqlite3.Connection, shade_id: int | None, today: date) -> dict:
    """What `_wear_hero.html` needs: the shade to wear (None draws the empty hero)."""
    shade = shades.get_shade(conn, shade_id) if shade_id is not None else None
    if shade is None:
        return {"wear": None}
    return {
        "wear": {
            "shade": shade,
            "facts": facts_line(shade["tags"]["finish"], wear.bottle_for(conn, shade["id"])),
            "worn": wear.worn_today(conn, shade["id"], today),
        }
    }


def choose(conn: sqlite3.Connection, today: date, another: bool, shown: int | None) -> int | None:
    """Today's pick, or with `another` a different owned shade than `shown` (than the pick, when
    the page does not say which one it shows)."""
    if not another:
        return wear.pick_today(conn, today)
    if shown is None:
        shown = wear.pick_today(conn, today)
    return wear.pick_another(conn, today, not_this=shown)


@router.get("/wear/another")
def another(request: Request, conn: Conn, shown: int | None = None):
    """A different shade for the hero, as a fragment. Asked for as a page it is Home's own."""
    if not is_partial_request(request):
        target = "/?another=1" + (f"&shown={shown}" if shown is not None else "")
        return RedirectResponse(target, 303)
    today = household_today(request)
    return render(
        request,
        "_wear_hero.html",
        hero_context(conn, choose(conn, today, True, shown), today) | {"arriving": True},
    )


@router.post("/wear/{shade_id}")
def i_wore_this(request: Request, conn: Conn, shade_id: int) -> Response:
    """Logs the shade as worn today (a second tap the same day changes nothing). The hero comes
    back saying "Worn today"; without htmx the person goes back to Home."""
    today = household_today(request)
    try:
        wear.record(conn, shade_id, today)
    except LookupError:
        raise HTTPException(404, "No such shade") from None
    if not is_partial_request(request):
        return RedirectResponse("/", 303)
    return render(request, "_wear_hero.html", hero_context(conn, shade_id, today))
