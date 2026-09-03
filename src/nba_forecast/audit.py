"""Data quality profiling for the NBA workbook."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .io import drop_team_aggregates


def _column_profile(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records = []
    for column in frame.columns:
        series = frame[column]
        records.append(
            {
                "column": column,
                "dtype": str(series.dtype),
                "rows": int(len(series)),
                "null_count": int(series.isna().sum()),
                "null_rate": round(float(series.isna().mean()), 4) if len(series) else 0.0,
                "distinct_count": int(series.nunique(dropna=True)),
            }
        )
    return records


def profile_workbook(sheets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    report: dict[str, Any] = {"sheets": {}, "warnings": []}
    for name, frame in sheets.items():
        report["sheets"][name] = {
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
            "column_profile": _column_profile(frame),
        }

    teams = sheets.get("team_season_stats", pd.DataFrame())
    players = drop_team_aggregates(sheets.get("players_season_stats", pd.DataFrame()))
    if not teams.empty and {"team_abbr", "season"}.issubset(teams.columns):
        key_duplicates = int(teams.duplicated(["team_abbr", "season"]).sum())
        report["team_key"] = {
            "rows_after_load": int(len(teams)),
            "unique_teams": int(teams["team_abbr"].nunique()),
            "unique_seasons": sorted(teams["season"].dropna().unique().tolist()),
            "duplicate_team_season_rows": key_duplicates,
        }
    if not players.empty and {"player_id", "season"}.issubset(players.columns):
        report["player_key"] = {
            "rows_after_2tm_removal": int(len(players)),
            "unique_players": int(players["player_id"].nunique()),
            "unique_teams": int(players["team_abbr"].nunique()),
        }

    sparse_fields = []
    for name, details in report["sheets"].items():
        for column in details["column_profile"]:
            if column["null_rate"] > 0.2:
                sparse_fields.append(f"{name}.{column['column']} ({column['null_rate']:.0%} null)")
    report["warnings"].extend(
        [
            "Only one season is present; this is insufficient for out-of-time model validation.",
            "Player game logs are partial and do not represent every rotation player.",
            "Contract coverage is limited; salary-derived features should be treated as incomplete.",
        ]
    )
    report["sparse_fields"] = sparse_fields
    return report

