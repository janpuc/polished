"""POST /wear/{shade_id}: "I wore this". (Today's pick comes with GET /home.)"""

from fastapi import APIRouter

from .. import wear
from . import schemas
from .errors import not_found
from .routing import ApiRoute, AppSettings, Conn, household_today

router = APIRouter(prefix="/wear", route_class=ApiRoute, tags=["home"])


@router.post(
    "/{shade_id}",
    response_model=schemas.Worn,
    summary="Record that a shade was worn today",
    responses={404: {"description": "`not_found`: no such shade."}},
)
def wear_record(conn: Conn, settings: AppSettings, shade_id: int):
    """Today is the household's date. Recording the same shade twice in a day is one wearing, so
    a repeated tap changes nothing."""
    try:
        worn_on = wear.record(conn, shade_id, household_today(settings))
    except LookupError:
        raise not_found("No such shade.") from None
    return schemas.Worn(worn_on=worn_on)
