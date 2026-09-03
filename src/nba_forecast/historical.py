"""Historical data normalization from the public llimllib/nba_data dump."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


TEAM_MAP = {"BKN": "BRK", "CHA": "CHO", "PHX": "PHO"}
VALID_TEAM_ABBRS = {
    "ATL", "BOS", "BRK", "CHO", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHO", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
}


def _normalize_team(value: object) -> object:
    return TEAM_MAP.get(value, value)


def _season_label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def _load_player_season_rows(source_dir: str | Path) -> pd.DataFrame:
    base = Path(source_dir)
    data_dir = base / "data" if (base / "data").exists() else base
    columns = [
        "player_id", "player_name", "team_abbreviation", "year", "min", "pts",
        "plus_minus", "net_rating", "off_rating", "def_rating", "age",
    ]
    players = pd.read_parquet(data_dir / "playerstats.parquet", columns=columns)
    players["player_id"] = pd.to_numeric(players["player_id"], errors="coerce")
    players["season_end_year"] = pd.to_numeric(players["year"], errors="coerce")
    players["team_abbr"] = players["team_abbreviation"].map(_normalize_team)
    players = players[
        players["player_id"].notna()
        & players["season_end_year"].notna()
        & players["team_abbr"].isin(VALID_TEAM_ABBRS)
    ].copy()
    for column in ["min", "pts", "plus_minus", "net_rating", "off_rating", "def_rating", "age"]:
        players[column] = pd.to_numeric(players[column], errors="coerce")
    return players


def _weighted_player_history(players: pd.DataFrame) -> pd.DataFrame:
    """Aggregate prior-season player production across all teams played for."""
    working = players.copy()
    weight = working["min"].fillna(0).clip(lower=0)
    working["_weight"] = weight
    numeric = ["net_rating", "off_rating", "def_rating"]
    for column in numeric:
        working[f"_{column}_weighted"] = working[column].fillna(0) * weight
    result = working.groupby(["season_end_year", "player_id"], as_index=False).agg(
        prior_minutes=("min", "sum"),
        prior_points=("pts", "sum"),
        prior_plus_minus=("plus_minus", "sum"),
        prior_age=("age", "mean"),
        prior_weight=("_weight", "sum"),
        prior_net_rating_weighted=("_net_rating_weighted", "sum"),
        prior_off_rating_weighted=("_off_rating_weighted", "sum"),
        prior_def_rating_weighted=("_def_rating_weighted", "sum"),
    )
    for column in ["net_rating", "off_rating", "def_rating"]:
        result[f"prior_{column}"] = np.where(
            result["prior_weight"] > 0,
            result[f"prior_{column}_weighted"] / result["prior_weight"],
            np.nan,
        )
    return result.drop(columns=[
        "prior_weight",
        "prior_net_rating_weighted",
        "prior_off_rating_weighted",
        "prior_def_rating_weighted",
    ])


def _primary_player_teams(players: pd.DataFrame) -> pd.DataFrame:
    """Choose the team with the most minutes when a player changed teams."""
    return (
        players.groupby(["season_end_year", "player_id", "team_abbr"], as_index=False)["min"]
        .sum()
        .sort_values(["season_end_year", "player_id", "min"], ascending=[True, True, False])
        .drop_duplicates(["season_end_year", "player_id"])
        .rename(columns={"team_abbr": "prior_primary_team", "min": "prior_primary_team_minutes"})
    )


def build_historical_roster_features(source_dir: str | Path) -> pd.DataFrame:
    """Build season-level roster transition features from public player IDs.

    The public dump has reliable season aggregates but not a complete historical
    transaction ledger. These features therefore describe the target season's
    observed roster composition using only prior-season player production. They
    are a retrospective roster proxy, not a claim that every move was known
    before opening night.
    """
    players = _load_player_season_rows(source_dir)
    history = _weighted_player_history(players)
    primary_teams = _primary_player_teams(players)
    target = players[["season_end_year", "team_abbr", "player_id"]].drop_duplicates()
    target = target.rename(columns={"season_end_year": "target_season_end_year"})
    prior = history.copy()
    prior["target_season_end_year"] = prior["season_end_year"] + 1
    prior = prior.drop(columns=["season_end_year"])
    prior_team = primary_teams.copy()
    prior_team["target_season_end_year"] = prior_team["season_end_year"] + 1
    prior_team = prior_team.drop(columns=["season_end_year"])
    roster = target.merge(prior, on=["target_season_end_year", "player_id"], how="left")
    roster = roster.merge(prior_team[["target_season_end_year", "player_id", "prior_primary_team"]], on=["target_season_end_year", "player_id"], how="left")
    roster["prior_minutes"] = roster["prior_minutes"].fillna(0)
    roster["roster_status"] = np.select(
        [
            roster["prior_primary_team"].eq(roster["team_abbr"]),
            roster["prior_primary_team"].notna(),
        ],
        ["returning", "incoming"],
        default="new",
    )

    def summarize(group: pd.DataFrame) -> pd.Series:
        minutes = group["prior_minutes"].clip(lower=0)
        covered = minutes > 0
        denominator = float(minutes[covered].sum())
        returning_minutes = float(minutes[group["roster_status"].eq("returning")].sum())
        incoming_minutes = float(minutes[group["roster_status"].eq("incoming")].sum())
        summary = {
            "prior_roster_transition_player_count": int(len(group)),
            "prior_roster_returning_player_count": int(group["roster_status"].eq("returning").sum()),
            "prior_roster_incoming_player_count": int(group["roster_status"].eq("incoming").sum()),
            "prior_roster_new_player_count": int(group["roster_status"].eq("new").sum()),
            "prior_roster_player_match_rate": float(covered.mean()) if len(group) else np.nan,
            "prior_roster_continuity_minutes_share": returning_minutes / denominator if denominator else np.nan,
            "prior_roster_incoming_minutes_share": incoming_minutes / denominator if denominator else np.nan,
            "prior_roster_minutes_covered": denominator,
            "roster_feature_source": "season-level roster proxy",
        }
        for source, destination in [
            ("prior_net_rating", "prior_roster_expected_net_rating"),
            ("prior_off_rating", "prior_roster_expected_off_rating"),
            ("prior_def_rating", "prior_roster_expected_def_rating"),
        ]:
            valid = covered & group[source].notna()
            weight = minutes[valid]
            summary[destination] = float(np.average(group.loc[valid, source], weights=weight)) if valid.any() else np.nan
        top = group.sort_values("prior_minutes", ascending=False).head(8)
        top_minutes = top["prior_minutes"].clip(lower=0)
        for source, destination in [
            ("prior_net_rating", "prior_roster_top8_expected_net_rating"),
            ("prior_off_rating", "prior_roster_top8_expected_off_rating"),
            ("prior_def_rating", "prior_roster_top8_expected_def_rating"),
        ]:
            valid = top_minutes > 0
            valid &= top[source].notna()
            weight = top_minutes[valid]
            summary[destination] = float(np.average(top.loc[valid, source], weights=weight)) if valid.any() else np.nan
        summary["prior_roster_top8_projection_wins"] = (
            41.0 + 2.7 * summary["prior_roster_top8_expected_net_rating"]
            if pd.notna(summary["prior_roster_top8_expected_net_rating"])
            else np.nan
        )
        return pd.Series(summary)

    result = roster.groupby(["target_season_end_year", "team_abbr"], as_index=False).apply(summarize, include_groups=False).reset_index()
    result = result.rename(columns={"target_season_end_year": "season_end_year"})
    return result.drop(columns=["level_2", "index"], errors="ignore")


def load_public_history(source_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return team summaries, player aggregates, and team game logs."""
    base = Path(source_dir)
    data_dir = base / "data" if (base / "data").exists() else base
    summary_json = json.loads((data_dir / "team_summary.json").read_text(encoding="utf-8"))
    team_rows = []
    for end_year, teams in summary_json["data"].items():
        year = int(end_year)
        for abbreviation, values in teams.items():
            row = {"season_end_year": year, "season": _season_label(year), "team_abbr": _normalize_team(abbreviation)}
            row.update({str(key).lower(): value for key, value in values.items()})
            team_rows.append(row)
    teams = pd.DataFrame(team_rows)
    teams = teams.rename(columns={"w": "target_wins", "l": "target_losses", "team_name": "team_name"})
    teams["target_playoff_flag"] = np.nan

    players = pd.read_parquet(data_dir / "playerstats.parquet")
    players["season_end_year"] = pd.to_numeric(players["year"], errors="coerce")
    players["season"] = players["season_end_year"].map(lambda value: _season_label(int(value)) if pd.notna(value) else np.nan)
    players["team_abbr"] = players["team_abbreviation"].map(_normalize_team)

    games = pd.read_parquet(data_dir / "gamelogs.parquet")
    games["season_end_year"] = games["season_year"].str[:4].astype(int) + 1
    games["season"] = games["season_end_year"].map(_season_label)
    games["team_abbr"] = games["team_abbreviation"].map(_normalize_team)
    games["game_date"] = pd.to_datetime(games["game_date"], errors="coerce")
    return teams, players, games


def _aggregate_prior_players(players: pd.DataFrame) -> pd.DataFrame:
    numeric = ["min", "pts", "plus_minus", "ts_pct", "usg_pct", "net_rating", "off_rating", "def_rating", "age"]
    available = [column for column in numeric if column in players.columns]
    working = players.dropna(subset=["team_abbr", "season_end_year"]).copy()
    for column in available:
        working[column] = pd.to_numeric(working[column], errors="coerce")
    grouped = working.groupby(["team_abbr", "season_end_year"], as_index=False).agg(
        prior_roster_player_count=("player_id", "nunique"),
        prior_roster_minutes=("min", "sum"),
        prior_player_points=("pts", "sum"),
        prior_player_plus_minus=("plus_minus", "sum"),
        prior_avg_age=("age", "mean"),
        prior_avg_ts_pct=("ts_pct", "mean"),
        prior_avg_usg_pct=("usg_pct", "mean"),
        prior_avg_player_net_rating=("net_rating", "mean"),
        prior_avg_player_off_rating=("off_rating", "mean"),
        prior_avg_player_def_rating=("def_rating", "mean"),
    )
    top3 = working.sort_values(["team_abbr", "season_end_year", "min"], ascending=[True, True, False]).groupby(
        ["team_abbr", "season_end_year"], as_index=False
    ).head(3).groupby(["team_abbr", "season_end_year"], as_index=False).agg(
        prior_top3_minutes=("min", "sum"),
        prior_top3_points=("pts", "sum"),
        prior_top3_plus_minus=("plus_minus", "sum"),
        prior_top3_net_rating=("net_rating", "mean"),
    )
    grouped = grouped.merge(top3, on=["team_abbr", "season_end_year"], how="left")
    return grouped


def _aggregate_prior_games(games: pd.DataFrame) -> pd.DataFrame:
    games = games.sort_values(["team_abbr", "season_end_year", "game_date"])
    grouped = games.groupby(["team_abbr", "season_end_year"], group_keys=False)
    recent = grouped.tail(20)
    result = grouped.agg(
        prior_games_observed=("game_id", "nunique"),
        prior_game_net_rating_mean=("net_rating", "mean"),
        prior_game_off_rating_mean=("off_rating", "mean"),
        prior_game_def_rating_mean=("def_rating", "mean"),
        prior_game_pace_mean=("pace", "mean"),
    ).reset_index()
    recent_result = recent.groupby(["team_abbr", "season_end_year"], as_index=False).agg(
        prior_last20_net_rating=("net_rating", "mean"),
        prior_last20_win_rate=("wl", lambda values: (values == "W").mean()),
    )
    return result.merge(recent_result, on=["team_abbr", "season_end_year"], how="left")


def build_historical_training_table(source_dir: str | Path) -> pd.DataFrame:
    teams, players, games = load_public_history(source_dir)
    player_features = _aggregate_prior_players(players)
    game_features = _aggregate_prior_games(games)
    roster_features = build_historical_roster_features(source_dir)

    current = teams.copy()
    current["prior_season_end_year"] = current["season_end_year"] - 1
    prior_team = teams[["team_abbr", "season_end_year", "target_wins", "off_rating", "def_rating", "net_rating", "pace"]].copy()
    prior_team = prior_team.rename(columns={
        "season_end_year": "prior_season_end_year",
        "target_wins": "prior_wins",
        "off_rating": "prior_off_rating",
        "def_rating": "prior_def_rating",
        "net_rating": "prior_net_rating",
        "pace": "prior_pace",
    })
    current = current.merge(prior_team, on=["team_abbr", "prior_season_end_year"], how="left")
    current = current.merge(player_features.rename(columns={"season_end_year": "prior_season_end_year"}), on=["team_abbr", "prior_season_end_year"], how="left")
    current = current.merge(game_features.rename(columns={"season_end_year": "prior_season_end_year"}), on=["team_abbr", "prior_season_end_year"], how="left")
    current_player = player_features.rename(columns={"season_end_year": "season_end_year"}).rename(
        columns={column: column.replace("prior_", "current_", 1) for column in player_features.columns if column.startswith("prior_")}
    )
    current_game = game_features.rename(columns={"season_end_year": "season_end_year"}).rename(
        columns={column: column.replace("prior_", "current_", 1) for column in game_features.columns if column.startswith("prior_")}
    )
    current = current.merge(current_player, on=["team_abbr", "season_end_year"], how="left")
    current = current.merge(current_game, on=["team_abbr", "season_end_year"], how="left")
    current = current.merge(roster_features, on=["team_abbr", "season_end_year"], how="left")
    current["prior_net_rating_proxy_wins"] = (41.0 + 2.7 * current["prior_net_rating"]).clip(0, 82)
    current["target_playoff_flag"] = np.nan
    return current.sort_values(["season_end_year", "team_abbr"]).reset_index(drop=True)


def build_next_season_frame(training: pd.DataFrame) -> pd.DataFrame:
    latest = training[training["season_end_year"].eq(training["season_end_year"].max())].copy()
    result = latest[["team_abbr"]].copy()
    team_feature_map = {
        "prior_wins": "target_wins",
        "prior_off_rating": "off_rating",
        "prior_def_rating": "def_rating",
        "prior_net_rating": "net_rating",
        "prior_pace": "pace",
    }
    for destination, source in team_feature_map.items():
        result[destination] = latest[source].to_numpy()
    current_features = [column for column in training.columns if column.startswith("current_")]
    for source in current_features:
        result[source.replace("current_", "prior_", 1)] = latest[source].to_numpy()
    for source in [column for column in training.columns if column.startswith("prior_")]:
        if source not in result:
            result[source] = latest[source].to_numpy()
    result["prior_net_rating_proxy_wins"] = (41.0 + 2.7 * result["prior_net_rating"]).clip(0, 82)
    result["season_end_year"] = latest["season_end_year"] + 1
    result["season"] = result["season_end_year"].map(_season_label)
    result["target_wins"] = np.nan
    return result


def build_live_roster_features(source_dir: str | Path, roster_path: str | Path, injuries_path: str | Path | None = None) -> pd.DataFrame:
    """Map the latest player statistics onto the current roster snapshot."""
    base = Path(source_dir)
    data_dir = base / "data" if (base / "data").exists() else base
    players = pd.read_parquet(data_dir / "playerstats.parquet")
    roster = pd.read_csv(roster_path)
    players["player_id"] = pd.to_numeric(players["player_id"], errors="coerce")
    players["team_abbr"] = players["team_abbreviation"].map(_normalize_team)
    roster["player_id"] = pd.to_numeric(roster["player_id"], errors="coerce")
    latest_year = pd.to_numeric(players["year"], errors="coerce").max()
    players = players[pd.to_numeric(players["year"], errors="coerce").eq(latest_year)].copy()
    matched = roster.merge(
        players[["player_id", "min", "gp", "pts", "plus_minus", "ts_pct", "usg_pct", "net_rating", "off_rating", "def_rating", "age"]],
        on="player_id",
        how="left",
        suffixes=("", "_history"),
    )
    latest_primary_team = (
        players.groupby(["player_id", "team_abbr"], as_index=False)["min"]
        .sum()
        .sort_values(["player_id", "min"], ascending=[True, False])
        .drop_duplicates("player_id")
        .rename(columns={"team_abbr": "prior_primary_team"})
    )
    matched = matched.merge(latest_primary_team[["player_id", "prior_primary_team"]], on="player_id", how="left")
    matched["roster_transition_status"] = np.select(
        [
            matched["prior_primary_team"].eq(matched["team_abbr"]),
            matched["prior_primary_team"].notna(),
        ],
        ["returning", "incoming"],
        default="new",
    )
    matched["availability_rate"] = (pd.to_numeric(matched["gp"], errors="coerce") / 82).clip(0, 1)
    matched["expected_minutes"] = pd.to_numeric(matched["min"], errors="coerce").fillna(0) * matched["availability_rate"].fillna(0)
    matched["injury_availability_factor"] = 1.0
    if injuries_path and Path(injuries_path).exists():
        injuries = pd.read_csv(injuries_path)
        injury_factors = {"out": 0.0, "inactive": 0.0, "doubtful": 0.2, "questionable": 0.5, "day-to-day": 0.8, "probable": 0.9}
        injuries["player_key"] = injuries["player_name"].astype(str).str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
        matched["player_key"] = matched["player_name"].astype(str).str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
        injuries["injury_availability_factor"] = injuries["injury_status"].astype(str).str.lower().map(injury_factors).fillna(0.75)
        injury_lookup = injuries.groupby(["team_abbr", "player_key"], as_index=False)["injury_availability_factor"].min()
        matched = matched.drop(columns=["injury_availability_factor"]).merge(injury_lookup, on=["team_abbr", "player_key"], how="left")
        matched["injury_availability_factor"] = matched["injury_availability_factor"].fillna(1.0)
    matched["expected_minutes"] = matched["expected_minutes"] * matched["injury_availability_factor"]
    result = matched.groupby("team_abbr", as_index=False).agg(
        prior_roster_player_count=("player_id", "nunique"),
        prior_roster_minutes=("min", "sum"),
        prior_player_points=("pts", "sum"),
        prior_player_plus_minus=("plus_minus", "sum"),
        prior_avg_age=("age_history", "mean"),
        prior_avg_ts_pct=("ts_pct", "mean"),
        prior_avg_usg_pct=("usg_pct", "mean"),
        prior_avg_player_net_rating=("net_rating", "mean"),
        prior_avg_player_off_rating=("off_rating", "mean"),
        prior_avg_player_def_rating=("def_rating", "mean"),
    )
    top3 = matched.sort_values(["team_abbr", "min"], ascending=[True, False]).groupby("team_abbr", as_index=False).head(3).groupby("team_abbr", as_index=False).agg(
        prior_top3_minutes=("min", "sum"),
        prior_top3_points=("pts", "sum"),
        prior_top3_plus_minus=("plus_minus", "sum"),
        prior_top3_net_rating=("net_rating", "mean"),
    )
    result = result.merge(top3, on="team_abbr", how="left")
    def summarize_transition(group: pd.DataFrame) -> pd.Series:
        minutes = pd.to_numeric(group["min"], errors="coerce").fillna(0).clip(lower=0)
        covered = minutes > 0
        denominator = float(minutes[covered].sum())
        summary = {
            "prior_roster_transition_player_count": int(len(group)),
            "prior_roster_returning_player_count": int(group["roster_transition_status"].eq("returning").sum()),
            "prior_roster_incoming_player_count": int(group["roster_transition_status"].eq("incoming").sum()),
            "prior_roster_new_player_count": int(group["roster_transition_status"].eq("new").sum()),
            "prior_roster_player_match_rate": float(covered.mean()) if len(group) else np.nan,
            "prior_roster_continuity_minutes_share": float(minutes[group["roster_transition_status"].eq("returning")].sum() / denominator) if denominator else np.nan,
            "prior_roster_incoming_minutes_share": float(minutes[group["roster_transition_status"].eq("incoming")].sum() / denominator) if denominator else np.nan,
            "prior_roster_minutes_covered": denominator,
            "roster_feature_source": "live roster plus latest player history",
        }
        for source, destination in [
            ("net_rating", "prior_roster_expected_net_rating"),
            ("off_rating", "prior_roster_expected_off_rating"),
            ("def_rating", "prior_roster_expected_def_rating"),
        ]:
            expected_minutes = group["expected_minutes"].fillna(0).clip(lower=0)
            valid = expected_minutes > 0
            valid &= group[source].notna()
            weight = expected_minutes[valid]
            summary[destination] = float(np.average(group.loc[valid, source], weights=weight)) if valid.any() else np.nan
        top = group.sort_values("expected_minutes", ascending=False).head(8)
        top_minutes = top["expected_minutes"].fillna(0).clip(lower=0)
        for source, destination in [
            ("net_rating", "prior_roster_top8_expected_net_rating"),
            ("off_rating", "prior_roster_top8_expected_off_rating"),
            ("def_rating", "prior_roster_top8_expected_def_rating"),
        ]:
            valid = top_minutes > 0
            valid &= top[source].notna()
            weight = top_minutes[valid]
            summary[destination] = float(np.average(top.loc[valid, source], weights=weight)) if valid.any() else np.nan
        summary["prior_roster_top8_projection_wins"] = (
            41.0 + 2.7 * summary["prior_roster_top8_expected_net_rating"]
            if pd.notna(summary["prior_roster_top8_expected_net_rating"])
            else np.nan
        )
        return pd.Series(summary)

    transition = matched.groupby("team_abbr", as_index=False).apply(summarize_transition, include_groups=False).reset_index(drop=True)
    result = result.merge(transition, on="team_abbr", how="left")
    top_rotation = matched.sort_values(["team_abbr", "expected_minutes"], ascending=[True, False]).groupby("team_abbr", as_index=False).head(8)
    rotation = top_rotation.groupby("team_abbr", as_index=False).apply(
        lambda group: pd.Series({
            "live_roster_expected_net_rating": np.average(group["net_rating"].fillna(0), weights=group["expected_minutes"] + 1),
            "live_roster_projected_minutes": group["expected_minutes"].sum(),
            "live_roster_matched_players": int(group["net_rating"].notna().sum()),
            "live_roster_injured_players": int((group["injury_availability_factor"] < 1).sum()),
        }),
        include_groups=False,
    ).reset_index(drop=True)
    rotation["live_roster_projection_wins"] = (41.0 + 2.7 * rotation["live_roster_expected_net_rating"]).clip(0, 82)
    result = result.merge(rotation, on="team_abbr", how="left")
    return result
