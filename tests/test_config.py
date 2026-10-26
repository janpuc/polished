import pytest
from conftest import SECRET
from pydantic import ValidationError

from polished.cli import main
from polished.config import Settings


def build(**values) -> Settings:
    values.setdefault("public_url", "http://localhost:8080")
    values.setdefault("auth_mode", "none")
    return Settings(_env_file=None, **values)


def test_defaults_follow_design_12():
    s = build()
    assert s.db_path == "/data/polished.db"
    assert s.port == 8080
    assert (s.session_days, s.session_max_days) == (30, 90)
    assert s.sync_min_interval_s == 1.0
    assert s.timezone == "Europe/Warsaw"
    assert s.allowed_groups == {"ID-Users", "ID-Admin"}
    assert s.store_url == "https://holotaco.com"
    assert s.over_black_handle == "one-coat-black"


def test_settings_come_from_polished_environment_variables(monkeypatch):
    monkeypatch.setenv("POLISHED_PUBLIC_URL", "http://127.0.0.1:9000/")
    monkeypatch.setenv("POLISHED_AUTH_MODE", "none")
    monkeypatch.setenv("POLISHED_PORT", "9000")
    monkeypatch.setenv("POLISHED_OIDC_ALLOWED_GROUPS", "a, b")
    s = Settings(_env_file=None)
    assert s.public_url == "http://127.0.0.1:9000"
    assert s.port == 9000
    assert s.allowed_groups == {"a", "b"}


def test_public_url_is_required():
    with pytest.raises(ValidationError, match="public_url"):
        Settings(_env_file=None, auth_mode="none")


@pytest.mark.parametrize("value", [0.0, 0.5, 0.99])
def test_sync_min_interval_below_one_second_is_rejected(value):
    with pytest.raises(ValidationError, match="sync_min_interval_s"):
        build(sync_min_interval_s=value)


def test_sync_min_interval_of_one_second_or_more_is_accepted():
    assert build(sync_min_interval_s=1.0).sync_min_interval_s == 1.0
    assert build(sync_min_interval_s=2.5).sync_min_interval_s == 2.5


@pytest.mark.parametrize("url", ["http://localhost:8080", "http://127.0.0.1:8080"])
def test_auth_none_is_accepted_for_localhost(url):
    assert build(public_url=url).auth_mode == "none"


@pytest.mark.parametrize(
    "url",
    ["https://polished.janpuc.com", "http://localhost.evil.test", "http://10.0.0.5:8080"],
)
def test_auth_none_is_refused_when_public_url_is_not_localhost(url):
    with pytest.raises(ValidationError, match="AUTH_MODE=none is only allowed"):
        build(public_url=url)


def test_oidc_needs_client_credentials():
    with pytest.raises(ValidationError, match="OIDC_CLIENT_ID"):
        build(public_url="https://polished.example.test", auth_mode="oidc", session_secret=SECRET)


def test_oidc_needs_a_session_secret_of_at_least_32_characters():
    oidc = {
        "public_url": "https://polished.example.test",
        "auth_mode": "oidc",
        "oidc_client_id": "x",
        "oidc_client_secret": "x",
    }
    with pytest.raises(ValidationError, match="SESSION_SECRET is required"):
        build(**oidc)
    with pytest.raises(ValidationError, match="at least 32"):
        build(session_secret="short", **oidc)
    assert build(session_secret=SECRET, **oidc).auth_mode == "oidc"


def test_none_mode_makes_a_session_secret_when_none_is_set():
    secret = build().session_secret.get_secret_value()
    assert len(secret) >= 32
    assert secret != build().session_secret.get_secret_value()


def test_secrets_are_not_shown_in_repr():
    s = make_settings_with_oidc()
    assert "client-secret" not in repr(s)
    assert SECRET not in repr(s)


def make_settings_with_oidc() -> Settings:
    return build(
        public_url="https://polished.example.test",
        auth_mode="oidc",
        oidc_client_id="client-id",
        oidc_client_secret="client-secret",
        session_secret=SECRET,
    )


def test_unknown_timezone_is_rejected():
    with pytest.raises(ValidationError, match="timezone"):
        build(timezone="Mars/Olympus")


def test_session_max_days_may_not_be_below_session_days():
    with pytest.raises(ValidationError, match="SESSION_MAX_DAYS"):
        build(session_days=30, session_max_days=7)


def test_serve_exits_non_zero_with_a_message_for_auth_none_on_a_public_url(monkeypatch, capsys):
    monkeypatch.setenv("POLISHED_AUTH_MODE", "none")
    monkeypatch.setenv("POLISHED_PUBLIC_URL", "https://polished.janpuc.com")
    assert main(["serve"]) == 2
    err = capsys.readouterr().err
    assert "AUTH_MODE=none is only allowed" in err
    assert "https://polished.janpuc.com" in err


def test_host_defaults_to_all_interfaces_in_oidc_mode():
    assert make_settings_with_oidc().host == "0.0.0.0"


def test_host_defaults_to_loopback_in_none_mode():
    assert build().host == "127.0.0.1"


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_auth_none_accepts_an_explicit_loopback_host(host):
    assert build(host=host).host == host


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.5"])
def test_auth_none_refuses_a_non_loopback_host(host):
    with pytest.raises(ValidationError, match="loopback"):
        build(host=host)


def test_auth_none_refuses_host_from_the_environment(monkeypatch):
    monkeypatch.setenv("POLISHED_PUBLIC_URL", "http://localhost:8080")
    monkeypatch.setenv("POLISHED_AUTH_MODE", "none")
    monkeypatch.setenv("POLISHED_HOST", "0.0.0.0")
    with pytest.raises(ValidationError, match="loopback"):
        Settings(_env_file=None)


def test_the_over_black_handle_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("POLISHED_PUBLIC_URL", "http://localhost:8080")
    monkeypatch.setenv("POLISHED_AUTH_MODE", "none")
    monkeypatch.setenv("POLISHED_OVER_BLACK_HANDLE", "midnight-creme")
    assert Settings(_env_file=None).over_black_handle == "midnight-creme"


def test_native_app_settings_default_to_off():
    s = build()
    assert s.apple_team_id == "" and s.dev_token is None and s.test_reset_from == ""


def test_apple_team_id_is_ten_capital_letters_or_digits():
    assert build(apple_team_id="RW5T9P5A59").apple_team_id == "RW5T9P5A59"
    with pytest.raises(ValidationError, match="Apple team ID"):
        build(apple_team_id="not-a-team")


def test_dev_token_and_test_reset_are_for_auth_mode_none_only():
    assert build(dev_token="dev").dev_token.get_secret_value() == "dev"
    assert build(test_reset_from="template.db").test_reset_from == "template.db"
    oidc = {
        "auth_mode": "oidc",
        "public_url": "https://polished.example.test",
        "oidc_client_id": "id",
        "oidc_client_secret": "secret",
        "session_secret": SECRET,
    }
    assert Settings(_env_file=None, **oidc).dev_token is None
    with pytest.raises(ValidationError, match="DEV_TOKEN is only allowed"):
        Settings(_env_file=None, dev_token="dev", **oidc)
    with pytest.raises(ValidationError, match="TEST_RESET_FROM is only allowed"):
        Settings(_env_file=None, test_reset_from="template.db", **oidc)
    # An empty value (an unset variable in a manifest) is the same as none.
    assert Settings(_env_file=None, dev_token="", test_reset_from="", **oidc).dev_token is None


def test_dev_token_needs_a_loopback_bind(monkeypatch):
    with pytest.raises(ValidationError, match="loopback"):
        build(dev_token="dev", host="0.0.0.0")
