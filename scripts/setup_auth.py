"""Create local Streamlit authentication secrets without exposing a password in shell history."""

from __future__ import annotations

import json
import sys
from getpass import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_forecast.auth import hash_password


def main() -> None:
    username = input("NBA Forecast username [admin]: ").strip() or "admin"
    password = getpass("Password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    secrets_path.write_text(
        "[auth]\n"
        f"username = {json.dumps(username)}\n"
        f"password_hash = {json.dumps(hash_password(password))}\n"
        "session_minutes = 480\n"
        "max_attempts = 5\n"
        "lockout_seconds = 60\n",
        encoding="utf-8",
    )
    print(f"Authentication configured in {secrets_path}")
    print("The secrets file is ignored by Git and will not be committed.")


if __name__ == "__main__":
    main()
