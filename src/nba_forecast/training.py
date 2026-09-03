"""Expanding-window training and evaluation for wins forecasts."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


FEATURES = [
    "prior_wins", "prior_off_rating", "prior_def_rating", "prior_net_rating", "prior_pace",
    "prior_roster_player_count", "prior_roster_minutes", "prior_player_points",
    "prior_player_plus_minus", "prior_avg_age", "prior_avg_ts_pct", "prior_avg_usg_pct",
    "prior_avg_player_net_rating", "prior_avg_player_off_rating", "prior_avg_player_def_rating",
    "prior_top3_minutes", "prior_top3_points", "prior_top3_plus_minus", "prior_top3_net_rating",
    "prior_games_observed", "prior_game_net_rating_mean", "prior_game_off_rating_mean",
    "prior_game_def_rating_mean", "prior_game_pace_mean", "prior_last20_net_rating",
    "prior_last20_win_rate",
]
ROSTER_TRANSITION_FEATURES = [
    "prior_roster_transition_player_count",
    "prior_roster_returning_player_count",
    "prior_roster_incoming_player_count",
    "prior_roster_new_player_count",
    "prior_roster_player_match_rate",
    "prior_roster_continuity_minutes_share",
    "prior_roster_incoming_minutes_share",
    "prior_roster_minutes_covered",
    "prior_roster_expected_net_rating",
    "prior_roster_expected_off_rating",
    "prior_roster_expected_def_rating",
    "prior_roster_top8_expected_net_rating",
    "prior_roster_top8_expected_off_rating",
    "prior_roster_top8_expected_def_rating",
    "prior_roster_top8_projection_wins",
]
ROSTER_AWARE_FEATURES = FEATURES + ROSTER_TRANSITION_FEATURES


def _model(features: list[str]) -> Pipeline:
    return Pipeline([
        ("preprocess", ColumnTransformer([
            ("numeric", Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]), features,)
        ], remainder="drop")),
        ("ridge", Ridge(alpha=10.0)),
    ])


def expanding_backtest(training: pd.DataFrame, min_train_seasons: int = 5) -> tuple[pd.DataFrame, dict[str, float | int | None]]:
    data = training.dropna(subset=["target_wins"]).copy()
    seasons = sorted(data["season_end_year"].unique())
    predictions = []
    for season in seasons:
        prior_seasons = [value for value in seasons if value < season]
        if len(prior_seasons) < min_train_seasons:
            continue
        train = data[data["season_end_year"].isin(prior_seasons)]
        test = data[data["season_end_year"].eq(season)]
        active_features = [feature for feature in FEATURES if feature in train.columns and train[feature].notna().any()]
        independent_model = _model(active_features)
        independent_model.fit(train[active_features], train["target_wins"])
        independent_predicted = independent_model.predict(test[active_features])
        roster_features = [feature for feature in ROSTER_AWARE_FEATURES if feature in train.columns and train[feature].notna().any()]
        roster_model = _model(roster_features)
        roster_model.fit(train[roster_features], train["target_wins"])
        roster_predicted = roster_model.predict(test[roster_features])
        roster_proxy = pd.to_numeric(
            test["prior_roster_top8_projection_wins"],
            errors="coerce",
        ) if "prior_roster_top8_projection_wins" in test.columns else pd.Series(np.nan, index=test.index)
        roster_aware = np.where(roster_proxy.notna(), roster_proxy, roster_predicted)
        predictions.append(test[["team_abbr", "season", "season_end_year", "target_wins"]].assign(
            predicted_wins=np.clip(independent_predicted, 0, 82),
            roster_aware_predicted_wins=np.clip(roster_aware, 0, 82),
            roster_transition_model_predicted_wins=np.clip(roster_predicted, 0, 82),
            test_season=season,
        ))

    if not predictions:
        return pd.DataFrame(), {"test_rows": 0, "mae": None, "rmse": None}
    result = pd.concat(predictions, ignore_index=True)
    errors = result["predicted_wins"] - result["target_wins"]
    roster_errors = result["roster_aware_predicted_wins"] - result["target_wins"]
    transition_errors = result["roster_transition_model_predicted_wins"] - result["target_wins"]
    metrics = {
        "test_rows": int(len(result)),
        "mae": round(float(errors.abs().mean()), 3),
        "rmse": round(float(np.sqrt(np.mean(errors**2))), 3),
        "roster_aware_mae": round(float(roster_errors.abs().mean()), 3),
        "roster_aware_rmse": round(float(np.sqrt(np.mean(roster_errors**2))), 3),
        "roster_transition_model_mae": round(float(transition_errors.abs().mean()), 3),
        "roster_transition_model_rmse": round(float(np.sqrt(np.mean(transition_errors**2))), 3),
    }
    return result, metrics


def fit_next_season_forecast(training: pd.DataFrame, next_season: pd.DataFrame) -> pd.DataFrame:
    data = training.dropna(subset=["target_wins"]).copy()
    active_features = [feature for feature in FEATURES if feature in data.columns and data[feature].notna().any()]
    independent_model = _model(active_features)
    independent_model.fit(data[active_features], data["target_wins"])
    roster_features = [feature for feature in ROSTER_AWARE_FEATURES if feature in data.columns and data[feature].notna().any()]
    roster_model = _model(roster_features)
    roster_model.fit(data[roster_features], data["target_wins"])
    result = next_season[["team_abbr", "season", "season_end_year"]].copy()
    result["predicted_wins"] = np.clip(independent_model.predict(next_season[active_features]), 0, 82)
    roster_model_predicted = np.clip(roster_model.predict(next_season[roster_features]), 0, 82)
    roster_proxy = pd.to_numeric(
        next_season["prior_roster_top8_projection_wins"],
        errors="coerce",
    ) if "prior_roster_top8_projection_wins" in next_season.columns else pd.Series(np.nan, index=next_season.index)
    result["roster_aware_predicted_wins"] = np.clip(np.where(roster_proxy.notna(), roster_proxy, roster_model_predicted), 0, 82)
    result["roster_transition_model_predicted_wins"] = roster_model_predicted
    result["model_name"] = "expanding-ridge: independent + roster-aware rotation proxy"
    return result.sort_values("predicted_wins", ascending=False).reset_index(drop=True)
