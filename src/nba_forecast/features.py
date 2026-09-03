"""Feature construction for one row per team-season."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .io import drop_team_aggregates


def _weighted_mean(frame: pd.DataFrame, value: str, weight: str) -> pd.Series:
    valid = frame[value].notna() & frame[weight].notna() & frame[weight].gt(0)
    working = frame.loc[valid, ["team_abbr", "season", value, weight]]
    weighted = working[value] * working[weight]
    grouped = working.groupby(["team_abbr", "season"])[weight].sum()
    sums = weighted.groupby([working["team_abbr"], working["season"]]).sum()
    return sums.div(grouped.replace(0, np.nan))


def build_team_model_features(sheets: dict[str, pd.DataFrame]) -> pd.DataFrame:
    teams = sheets["team_season_stats"].copy()
    players = drop_team_aggregates(sheets["players_season_stats"])
    contracts = sheets["player_contracts"].copy()
    prior = sheets["team_model_features"].copy()
    key = ["team_abbr", "season"]

    result = teams[key + ["wins", "seed", "playoffs_result", "net_rtg", "off_rtg", "def_rtg"]].rename(
        columns={
            "wins": "target_wins",
            "seed": "target_seed",
            "playoffs_result": "target_playoff_result",
            "net_rtg": "current_net_rtg_diagnostic",
            "off_rtg": "current_off_rtg_diagnostic",
            "def_rtg": "current_def_rtg_diagnostic",
        }
    )

    prior_columns = [
        "team_abbr", "season", "team_net_rtg_prev_season", "team_off_rtg_prev_season",
        "team_def_rtg_prev_season", "pace_prev_season", "strength_of_schedule",
    ]
    result = result.merge(prior[prior_columns], on=key, how="left")

    player_agg = players.groupby(key, as_index=False).agg(
        roster_player_count=("player_id", "nunique"),
        avg_age=("age", "mean"),
        total_player_games=("g", "sum"),
        total_player_minutes=("mp", "sum"),
        total_ws=("ws", "sum"),
        total_vorp=("vorp", "sum"),
        avg_ts_pct=("ts_pct", "mean"),
        avg_per=("per", "mean"),
        avg_bpm=("bpm", "mean"),
    )
    result = result.merge(player_agg, on=key, how="left")

    weighted_age = _weighted_mean(players, "age", "mp").rename("minutes_weighted_age")
    result = result.merge(weighted_age.rename_axis(key).reset_index(), on=key, how="left")

    ranked = players.assign(
        minutes_value=players["mp"].fillna(0),
        usage_value=players["usg_pct"].fillna(0),
    )
    ranked["minutes_share"] = ranked["minutes_value"] / ranked.groupby(key)["minutes_value"].transform("sum").replace(0, np.nan)
    ranked["usage_share"] = ranked["usage_value"] / ranked.groupby(key)["usage_value"].transform("sum").replace(0, np.nan)
    ranked = ranked.sort_values(key + ["minutes_value"], ascending=[True, True, False])
    top3 = ranked.groupby(key).head(3).groupby(key)["minutes_share"].sum().rename("top_3_players_minutes_share")
    top5 = ranked.sort_values(key + ["usage_value"], ascending=[True, True, False]).groupby(key).head(5).groupby(key)["usage_share"].sum().rename("top_5_players_usage_share")
    result = result.merge(top3.rename_axis(key).reset_index(), on=key, how="left")
    result = result.merge(top5.rename_axis(key).reset_index(), on=key, how="left")

    if {"player_id", "salary"}.issubset(contracts.columns):
        salary = contracts.groupby(key, as_index=False).agg(
            salary_total_observed=("salary", "sum"),
            salary_player_count=("player_id", "nunique"),
        )
        top3_salary = contracts.sort_values(key + ["salary"], ascending=[True, True, False]).groupby(key).head(3).groupby(key)["salary"].sum().rename("salary_top_3_observed")
        salary = salary.merge(top3_salary.rename_axis(key).reset_index(), on=key, how="left")
        salary["salary_top_3_share_observed"] = salary["salary_top_3_observed"] / salary["salary_total_observed"].replace(0, np.nan)
        result = result.merge(salary, on=key, how="left")

    result["target_playoff_flag"] = result["target_playoff_result"].ne("Missed Playoffs").astype(int)
    result["prior_net_rating_proxy_wins"] = (41.0 + 2.7 * result["team_net_rtg_prev_season"]).clip(0, 82)
    return result.sort_values(key).reset_index(drop=True)

