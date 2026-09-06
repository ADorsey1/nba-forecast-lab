"""Data contract checks for the forecasting pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


EXPECTED_TEAM_COUNT = 30


def _check(
    name: str,
    passed: bool,
    observed: object,
    expected: object,
    severity: str = "error",
    detail: str = "",
) -> dict[str, object]:
    return {
        "name": name,
        "status": "pass" if passed else severity,
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }


def build_data_quality_report(
    features: pd.DataFrame,
    historical: pd.DataFrame | None = None,
    next_forecast: pd.DataFrame | None = None,
    rosters: pd.DataFrame | None = None,
    injuries: pd.DataFrame | None = None,
    moves: pd.DataFrame | None = None,
    schedule: pd.DataFrame | None = None,
    manifest: dict | None = None,
) -> dict[str, object]:
    """Return a serializable report for the current pipeline artifacts."""
    checks: list[dict[str, object]] = []
    feature_keys = features[["team_abbr", "season"]].drop_duplicates() if {"team_abbr", "season"}.issubset(features.columns) else pd.DataFrame()
    checks.append(_check(
        "feature_team_season_grain",
        len(feature_keys) == len(features),
        len(feature_keys),
        len(features),
        detail="Features should contain one row per team-season.",
    ))
    feature_teams = int(features["team_abbr"].nunique()) if "team_abbr" in features.columns else 0
    checks.append(_check("feature_team_count", feature_teams == EXPECTED_TEAM_COUNT, feature_teams, EXPECTED_TEAM_COUNT))

    if historical is not None and not historical.empty:
        historical_teams = int(historical["team_abbr"].nunique()) if "team_abbr" in historical.columns else 0
        historical_seasons = int(historical["season_end_year"].nunique()) if "season_end_year" in historical.columns else 0
        checks.append(_check("historical_team_count", historical_teams == EXPECTED_TEAM_COUNT, historical_teams, EXPECTED_TEAM_COUNT))
        checks.append(_check("historical_season_count", historical_seasons >= 5, historical_seasons, ">= 5", severity="warning"))

    if next_forecast is not None and not next_forecast.empty:
        forecast_teams = int(next_forecast["team_abbr"].nunique()) if "team_abbr" in next_forecast.columns else 0
        checks.append(_check("next_forecast_team_count", forecast_teams == EXPECTED_TEAM_COUNT, forecast_teams, EXPECTED_TEAM_COUNT))
        missing_wins = int(next_forecast["predicted_wins"].isna().sum()) if "predicted_wins" in next_forecast.columns else EXPECTED_TEAM_COUNT
        checks.append(_check("next_forecast_missing_wins", missing_wins == 0, missing_wins, 0))

    if rosters is not None and not rosters.empty:
        roster_teams = int(rosters["team_abbr"].nunique()) if "team_abbr" in rosters.columns else 0
        checks.append(_check("live_roster_team_count", roster_teams == EXPECTED_TEAM_COUNT, roster_teams, EXPECTED_TEAM_COUNT))
        roster_keys = rosters[["team_abbr", "player_id"]].drop_duplicates() if {"team_abbr", "player_id"}.issubset(rosters.columns) else rosters
        checks.append(_check("live_roster_duplicate_keys", len(roster_keys) == len(rosters), len(rosters) - len(roster_keys), 0))
    else:
        checks.append(_check("live_roster_available", False, 0, "> 0", severity="warning"))

    if injuries is not None:
        checks.append(_check("injury_snapshot_available", not injuries.empty, len(injuries), "> 0", severity="warning"))
    if moves is not None:
        checks.append(_check("transaction_ledger_available", not moves.empty, len(moves), "> 0", severity="warning"))
    if schedule is not None and not schedule.empty:
        if {"home_team", "away_team"}.issubset(schedule.columns):
            schedule_keys = schedule[["game_date", "home_team", "away_team"]].drop_duplicates()
        else:
            schedule_keys = schedule
        checks.append(_check("schedule_duplicate_games", len(schedule_keys) == len(schedule), len(schedule) - len(schedule_keys), 0))
        checks.append(_check("schedule_game_count", len(schedule_keys) >= 1000, len(schedule_keys), ">= 1000", severity="warning"))

    errors = sum(check["status"] == "error" for check in checks)
    warnings = sum(check["status"] == "warning" for check in checks)
    return {
        "status": "pass" if errors == 0 else "error",
        "error_count": errors,
        "warning_count": warnings,
        "checks": checks,
        "fetched_at_utc": (manifest or {}).get("fetched_at_utc"),
        "source_manifest": (manifest or {}).get("sources", {}),
        "artifact_paths": {
            "processed_dir": "data/processed",
            "live_dir": "data/raw/live",
        },
    }
