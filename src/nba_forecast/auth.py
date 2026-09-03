"""Dependency-free authentication helpers for the Streamlit app."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import secrets
import time
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass

PBKDF2_ALGORITHM = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000
MIN_ITERATIONS = 100_000
SALT_BYTES = 16
KEY_BYTES = 32


@dataclass(frozen=True)
class AuthConfig:
    """Runtime authentication policy loaded from secrets or environment."""

    username: str
    password_hash: str
    session_minutes: int = 480
    max_attempts: int = 5
    lockout_seconds: int = 60


def hash_password(password: str, *, iterations: int = DEFAULT_ITERATIONS) -> str:
    """Return a salted PBKDF2 password hash suitable for Streamlit secrets."""

    if not isinstance(password, str) or len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")
    if iterations < MIN_ITERATIONS:
        raise ValueError(f"PBKDF2 iterations must be at least {MIN_ITERATIONS}.")
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=KEY_BYTES
    )
    return "$".join(
        [
            PBKDF2_ALGORITHM,
            str(iterations),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        ]
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a password without revealing whether the stored value is malformed."""

    try:
        algorithm, iterations_text, salt_text, digest_text = encoded_hash.split("$", 3)
        iterations = int(iterations_text)
        if algorithm != PBKDF2_ALGORITHM or iterations < MIN_ITERATIONS:
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected)
        )
        return hmac.compare_digest(actual, expected)
    except (AttributeError, ValueError, TypeError, UnicodeEncodeError, binascii.Error):
        return False


def _bounded_int(value: object, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def load_auth_config(
    secret_config: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
) -> AuthConfig | None:
    """Load auth settings, preferring Streamlit secrets over environment values."""

    if secret_config is None:
        try:
            from streamlit import secrets as streamlit_secrets

            secret_config = streamlit_secrets.get("auth", {})
        except (FileNotFoundError, KeyError, AttributeError):
            secret_config = {}
    if not isinstance(secret_config, Mapping):
        secret_config = {}
    environ = os.environ if environ is None else environ

    username = str(
        secret_config.get("username") or environ.get("NBA_FORECAST_AUTH_USERNAME", "")
    ).strip()
    password_hash = str(
        secret_config.get("password_hash")
        or environ.get("NBA_FORECAST_AUTH_PASSWORD_HASH", "")
    ).strip()
    if not username or not password_hash:
        return None

    return AuthConfig(
        username=username,
        password_hash=password_hash,
        session_minutes=_bounded_int(
            secret_config.get("session_minutes", 480), 480, minimum=5, maximum=10080
        ),
        max_attempts=_bounded_int(
            secret_config.get("max_attempts", 5), 5, minimum=3, maximum=10
        ),
        lockout_seconds=_bounded_int(
            secret_config.get("lockout_seconds", 60), 60, minimum=15, maximum=3600
        ),
    )


def clear_auth_state(state: MutableMapping[str, object]) -> None:
    """Remove authentication and login-throttling state from a Streamlit session."""

    for key in (
        "auth_authenticated",
        "auth_username",
        "auth_expires_at",
        "auth_failed_attempts",
        "auth_locked_until",
    ):
        state.pop(key, None)


def session_is_valid(
    state: MutableMapping[str, object], config: AuthConfig, *, now: float | None = None
) -> bool:
    """Validate and refresh a sliding session expiration window."""

    if not state.get("auth_authenticated"):
        return False
    now = time.time() if now is None else now
    try:
        expires_at = float(state.get("auth_expires_at", 0))
    except (TypeError, ValueError):
        clear_auth_state(state)
        return False
    if expires_at <= now:
        clear_auth_state(state)
        return False
    state["auth_expires_at"] = now + config.session_minutes * 60
    return True


def mark_authenticated(
    state: MutableMapping[str, object], username: str, config: AuthConfig, *, now: float | None = None
) -> None:
    """Mark a verified Streamlit session as authenticated."""

    now = time.time() if now is None else now
    state["auth_authenticated"] = True
    state["auth_username"] = username
    state["auth_expires_at"] = now + config.session_minutes * 60
    state["auth_failed_attempts"] = 0
    state.pop("auth_locked_until", None)


def login_is_allowed(
    state: MutableMapping[str, object], *, now: float | None = None
) -> tuple[bool, int]:
    """Return whether another login attempt is allowed and seconds remaining if not."""

    now = time.time() if now is None else now
    try:
        locked_until = float(state.get("auth_locked_until", 0))
    except (TypeError, ValueError):
        state.pop("auth_locked_until", None)
        return True, 0
    if locked_until <= now:
        state.pop("auth_locked_until", None)
        return True, 0
    return False, max(1, int(locked_until - now))


def record_failed_login(
    state: MutableMapping[str, object], config: AuthConfig, *, now: float | None = None
) -> int:
    """Record a failure and return the number of attempts remaining before lockout."""

    now = time.time() if now is None else now
    attempts = int(state.get("auth_failed_attempts", 0)) + 1
    if attempts >= config.max_attempts:
        state["auth_failed_attempts"] = 0
        state["auth_locked_until"] = now + config.lockout_seconds
        return 0
    state["auth_failed_attempts"] = attempts
    return config.max_attempts - attempts
