from nba_forecast.auth import (
    AuthConfig,
    hash_password,
    load_auth_config,
    login_is_allowed,
    mark_authenticated,
    record_failed_login,
    session_is_valid,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple", iterations=100_000)
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("incorrect password", encoded)


def test_password_hash_rejects_short_passwords() -> None:
    try:
        hash_password("too-short")
    except ValueError as error:
        assert "12 characters" in str(error)
    else:
        raise AssertionError("Expected short password to be rejected")


def test_auth_config_prefers_secrets() -> None:
    config = load_auth_config(
        {"username": "secret-user", "password_hash": "secret-hash", "max_attempts": 2},
        {"NBA_FORECAST_AUTH_USERNAME": "env-user", "NBA_FORECAST_AUTH_PASSWORD_HASH": "env-hash"},
    )
    assert config == AuthConfig("secret-user", "secret-hash", max_attempts=3)


def test_session_expiration_and_refresh() -> None:
    config = AuthConfig("admin", "hash", session_minutes=5)
    state: dict[str, object] = {}
    mark_authenticated(state, "admin", config, now=100)
    assert session_is_valid(state, config, now=200)
    assert state["auth_expires_at"] == 500
    assert not session_is_valid(state, config, now=501)


def test_failed_login_lockout() -> None:
    config = AuthConfig("admin", "hash", max_attempts=3, lockout_seconds=60)
    state: dict[str, object] = {}
    assert record_failed_login(state, config, now=100) == 2
    assert record_failed_login(state, config, now=101) == 1
    assert record_failed_login(state, config, now=102) == 0
    assert login_is_allowed(state, now=103) == (False, 59)
    assert login_is_allowed(state, now=163) == (True, 0)
