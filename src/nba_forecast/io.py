"""Workbook ingestion and lightweight schema normalization."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


EXPECTED_SHEETS = {
    "players_season_stats",
    "team_season_stats",
    "player_game_logs",
    "player_contracts",
    "team_roster_context",
    "team_model_features",
    "sources_and_dictionary",
}


def load_workbook(path: str | Path) -> dict[str, pd.DataFrame]:
    """Load all workbook sheets as data frames without changing source values."""
    workbook_path = Path(path)
    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    sheets = pd.read_excel(workbook_path, sheet_name=None, engine="openpyxl")
    for name, frame in sheets.items():
        frame.columns = [str(column).strip() for column in frame.columns]
        for column in frame.select_dtypes(include="object").columns:
            frame[column] = frame[column].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )
        if "game_date" in frame.columns:
            frame["game_date"] = pd.to_datetime(frame["game_date"], errors="coerce")
    return sheets


def require_sheets(sheets: dict[str, pd.DataFrame]) -> None:
    missing = EXPECTED_SHEETS.difference(sheets)
    if missing:
        raise ValueError(f"Workbook is missing expected sheets: {sorted(missing)}")


def drop_team_aggregates(players: pd.DataFrame) -> pd.DataFrame:
    """Remove Basketball-Reference-style multi-team aggregate rows."""
    if "team_abbr" not in players.columns:
        return players.copy()
    return players.loc[players["team_abbr"].ne("2TM")].copy()

