"""Per-device API tokens and the app's PKCE sign-in (docs/NATIVE.md 2.4, DESIGN 17).

The browser half (`/auth/app/start`, `/auth/app/finish`) is in polished/auth.py and calls
`mint_login_code`. The app trades the code for a token at `POST /api/v1/auth/exchange`. Tokens and
codes are stored as sha256 hashes; the clear value exists only in the response that creates it.
"""

import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

from ..db import transaction

CODE_TTL_S = 60
LAST_USED_EVERY_S = 60
# base64url(sha256(...)) without padding is always 43 characters.
CHALLENGE = re.compile(r"[A-Za-z0-9_-]{43}")
DEVICE_NAME_LIMIT = 60


class BadCode(Exception):
    """The code is unknown, expired, already used, or the verifier does not match."""


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def now() -> datetime:
    return datetime.now(UTC)


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def challenge_for(verifier: str) -> str:
    """The PKCE S256 challenge of a verifier."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def clean_device_name(raw: str | None, default: str = "iPhone") -> str:
    return " ".join((raw or "").split())[:DEVICE_NAME_LIMIT] or default


def mint_login_code(
    conn: sqlite3.Connection,
    user_sub: str,
    user_name: str,
    challenge: str,
    device_name: str,
    at: datetime | None = None,
) -> str:
    """A single-use code bound to the signed-in user and the app's challenge, valid for 60 s.
    Old rows are dropped on the way."""
    at = at or now()
    code = secrets.token_urlsafe(32)
    with transaction(conn):
        conn.execute(
            "delete from app_login_code where expires_at < ?", (_stamp(at - timedelta(days=1)),)
        )
        conn.execute(
            "insert into app_login_code (code_hash, user_sub, user_name, challenge, device_name,"
            " expires_at) values (?, ?, ?, ?, ?, ?)",
            (
                hash_secret(code),
                user_sub,
                user_name,
                challenge,
                device_name,
                _stamp(at + timedelta(seconds=CODE_TTL_S)),
            ),
        )
    return code


def exchange(
    conn: sqlite3.Connection,
    code: str,
    verifier: str,
    device_name: str,
    platform: str,
    app_version: str,
    at: datetime | None = None,
) -> tuple[str, int, dict]:
    """Trades a code for a token: (token, token_id, {"sub", "name"}). The code is used up by the
    attempt, so a wrong verifier burns it too. Raises BadCode."""
    at = at or now()
    with transaction(conn):
        row = conn.execute(
            "select * from app_login_code where code_hash = ?", (hash_secret(code),)
        ).fetchone()
        if row is None or row["used_at"] is not None or row["expires_at"] <= _stamp(at):
            raise BadCode
        conn.execute(
            "update app_login_code set used_at = ? where code_hash = ?",
            (_stamp(at), row["code_hash"]),
        )
    if not hmac.compare_digest(challenge_for(verifier), row["challenge"]):
        raise BadCode
    token = secrets.token_urlsafe(32)
    token_id = conn.execute(
        "insert into api_token (user_sub, user_name, device_name, platform, app_version,"
        " token_hash, created_at) values (?, ?, ?, ?, ?, ?, ?)",
        (
            row["user_sub"],
            row["user_name"],
            clean_device_name(device_name, row["device_name"]),
            platform[:20],
            app_version[:40] or None,
            hash_secret(token),
            _stamp(at),
        ),
    ).lastrowid
    return token, token_id, {"sub": row["user_sub"], "name": row["user_name"]}


def authenticate(conn: sqlite3.Connection, token: str, at: datetime | None = None) -> dict | None:
    """The user and token id of a live token, else None. last_used_at moves at most once a
    minute, so reading does not turn into a write on every request."""
    at = at or now()
    row = conn.execute(
        "select id, user_sub, user_name, last_used_at from api_token"
        " where token_hash = ? and revoked_at is null",
        (hash_secret(token),),
    ).fetchone()
    if row is None:
        return None
    due = _stamp(at - timedelta(seconds=LAST_USED_EVERY_S))
    if row["last_used_at"] is None or row["last_used_at"] <= due:
        conn.execute("update api_token set last_used_at = ? where id = ?", (_stamp(at), row["id"]))
    return {"token_id": row["id"], "sub": row["user_sub"], "name": row["user_name"]}


def revoke(
    conn: sqlite3.Connection, token_id: int, user_sub: str, at: datetime | None = None
) -> bool:
    """Revokes one of the user's tokens; False when there is no such live token."""
    cursor = conn.execute(
        "update api_token set revoked_at = ? where id = ? and user_sub = ? and revoked_at is null",
        (_stamp(at or now()), token_id, user_sub),
    )
    return cursor.rowcount == 1


def devices(conn: sqlite3.Connection, user_sub: str, current_id: int | None) -> list[dict]:
    """The user's live tokens, newest first."""
    rows = conn.execute(
        "select id, device_name, platform, created_at, last_used_at from api_token"
        " where user_sub = ? and revoked_at is null order by id desc",
        (user_sub,),
    )
    return [{**dict(row), "current": row["id"] == current_id} for row in rows]
