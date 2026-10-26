"""The token endpoints: POST /auth/exchange, POST /auth/revoke, GET/DELETE /auth/devices.
The browser half of the app's sign-in is in polished/auth.py, the token store in api/auth.py."""

from fastapi import APIRouter, Request, Response

from . import auth, schemas
from .errors import ApiError, not_found
from .routing import ApiRoute, Conn

router = APIRouter(prefix="/auth", route_class=ApiRoute, tags=["auth"])


@router.post(
    "/exchange",
    response_model=schemas.ExchangeResponse,
    summary="Trade the sign-in code for a device token",
    responses={400: {"description": "`bad_code`: expired, already used, or the wrong verifier."}},
)
def exchange(conn: Conn, body: schemas.ExchangeRequest):
    """Public: the single-use code from `/auth/app/finish` and the PKCE verifier are the
    credential. The code is used up by the attempt, right or wrong."""
    try:
        token, token_id, user = auth.exchange(
            conn, body.code, body.verifier, body.device_name, body.platform, body.app_version
        )
    except auth.BadCode:
        raise ApiError(400, "bad_code", "That sign-in has expired. Try again.") from None
    return schemas.ExchangeResponse(token=token, token_id=token_id, user=user)


@router.post("/revoke", status_code=204, summary="Sign out this device")
def revoke(request: Request, conn: Conn) -> Response:
    """Revokes the token that made the call. (The development token has nothing to revoke.)"""
    user = request.state.user
    if user.get("token_id") is not None:
        auth.revoke(conn, user["token_id"], user["sub"])
    return Response(status_code=204)


@router.get("/devices", response_model=schemas.Devices, summary="Devices signed in as you")
def device_list(request: Request, conn: Conn):
    user = request.state.user
    return schemas.Devices(items=auth.devices(conn, user["sub"], user.get("token_id")))


@router.delete(
    "/devices/{device_id}",
    status_code=204,
    summary="Sign a device out",
    responses={404: {"description": "`not_found`: not one of your devices."}},
)
def delete_device(request: Request, conn: Conn, device_id: int) -> Response:
    if not auth.revoke(conn, device_id, request.state.user["sub"]):
        raise not_found("No such device.")
    return Response(status_code=204)
