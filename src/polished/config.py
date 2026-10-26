import re
import secrets
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_HOSTS = ("localhost", "127.0.0.1")
LOOPBACK_BINDS = ("127.0.0.1", "::1", "localhost")
MIN_SESSION_SECRET = 32
RELEASE_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/1NzRWMdQngZg_xnehoUtjtvUnc4nIaSbqUBqmE7KwB8g"
    "/export?format=csv&gid=186001220"
)


def _check_http_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"must be an http(s) URL, got {value!r}")
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLISHED_", env_file=".env", extra="ignore")

    version: str = "dev"
    log_level: str = "INFO"
    db_path: str = "/data/polished.db"
    host: str = "0.0.0.0"
    port: int = Field(8080, gt=0, le=65535)

    # External base URL: OIDC redirect, QR and tag URLs, and the host the Origin check expects.
    public_url: str
    # "none" is for local development and tests; it is refused unless public_url is localhost.
    auth_mode: Literal["oidc", "none"] = "oidc"

    oidc_issuer: str = "https://id.janpuc.com"
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = None
    # Comma-separated, exact match against the token's `groups` claim.
    oidc_allowed_groups: str = "ID-Users,ID-Admin"

    # Required in oidc mode; in none mode a random one is made per start (sessions are not
    # worth keeping across dev restarts).
    session_secret: SecretStr | None = None
    session_days: int = Field(30, gt=0)
    session_max_days: int = Field(90, gt=0)

    store_url: str = "https://holotaco.com"
    sync_enabled: bool = True
    sync_hour: int = Field(6, ge=0, le=23)
    sync_jitter_min: int = Field(30, ge=0, le=120)
    # Gap between requests to the store; the store is small, so values below 1.0 are rejected.
    sync_min_interval_s: float = Field(1.0, ge=1.0)
    sync_manual_cooldown_s: int = Field(3600, ge=0)
    # Holo Taco's official release list (a public Google Sheet, CSV export), read once per sync
    # after the shop pages. Empty turns it off.
    release_sheet_url: str = RELEASE_SHEET_URL

    timezone: str = "Europe/Warsaw"
    over_black_handle: str = "one-coat-black"

    # The 10-character Apple team ID of the native app; with it the server answers
    # /.well-known/apple-app-site-association (universal links). Empty: that route is off.
    apple_team_id: str = ""
    # AUTH_MODE=none only: a fixed bearer token for /api/v1 (local development, UI tests).
    dev_token: SecretStr | None = None
    # AUTH_MODE=none only: a template database that POST /__test/reset copies over the live one.
    test_reset_from: str = ""

    @field_validator("public_url", "store_url", "oidc_issuer")
    @classmethod
    def _http_url(cls, value: str) -> str:
        return _check_http_url(value).rstrip("/")

    @field_validator("release_sheet_url")
    @classmethod
    def _optional_http_url(cls, value: str) -> str:
        value = value.strip()
        return _check_http_url(value) if value else ""

    @field_validator("apple_team_id")
    @classmethod
    def _team_id(cls, value: str) -> str:
        value = value.strip()
        if value and not re.fullmatch(r"[A-Z0-9]{10}", value):
            raise ValueError("must be the 10-character Apple team ID, e.g. ABCDE12345")
        return value

    @field_validator("dev_token")
    @classmethod
    def _dev_token_not_empty(cls, value: SecretStr | None) -> SecretStr | None:
        return value if value is not None and value.get_secret_value() else None

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone {value!r}") from exc
        return value

    @model_validator(mode="after")
    def _check_auth(self) -> "Settings":
        if self.auth_mode != "none":
            for name, value in (
                ("DEV_TOKEN", self.dev_token),
                ("TEST_RESET_FROM", self.test_reset_from),
            ):
                if value:
                    raise ValueError(
                        f"POLISHED_{name} is only allowed with POLISHED_AUTH_MODE=none"
                    )
        if self.auth_mode == "none":
            host = urlsplit(self.public_url).hostname
            if host not in LOCAL_HOSTS:
                raise ValueError(
                    "POLISHED_AUTH_MODE=none is only allowed when POLISHED_PUBLIC_URL is "
                    f"localhost or 127.0.0.1 (got {self.public_url}); use POLISHED_AUTH_MODE=oidc"
                )
            # An unset HOST defaults to loopback so a dev config can't be exposed by accident.
            if "host" not in self.model_fields_set:
                self.host = "127.0.0.1"
            elif self.host not in LOOPBACK_BINDS:
                raise ValueError(
                    "POLISHED_AUTH_MODE=none needs POLISHED_HOST to be a loopback address "
                    f"(127.0.0.1, ::1 or localhost), got {self.host!r}"
                )
            if self.session_secret is None:
                self.session_secret = SecretStr(secrets.token_urlsafe(48))
        else:
            if not self.oidc_client_id or self.oidc_client_secret is None:
                raise ValueError(
                    "POLISHED_AUTH_MODE=oidc needs POLISHED_OIDC_CLIENT_ID and "
                    "POLISHED_OIDC_CLIENT_SECRET"
                )
            if self.session_secret is None:
                raise ValueError("POLISHED_SESSION_SECRET is required")
        if len(self.session_secret.get_secret_value()) < MIN_SESSION_SECRET:
            raise ValueError(
                f"POLISHED_SESSION_SECRET must be at least {MIN_SESSION_SECRET} characters"
            )
        if self.session_max_days < self.session_days:
            raise ValueError("POLISHED_SESSION_MAX_DAYS must not be below POLISHED_SESSION_DAYS")
        return self

    @property
    def allowed_groups(self) -> frozenset[str]:
        return frozenset(g.strip() for g in self.oidc_allowed_groups.split(",") if g.strip())

    @property
    def public_netloc(self) -> str:
        return urlsplit(self.public_url).netloc
