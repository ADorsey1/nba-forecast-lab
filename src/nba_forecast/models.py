"""Transparent baselines and evaluation helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


def build_baseline_forecasts(features: pd.DataFrame) -> pd.DataFrame:
    result = features[["team_abbr", "season", "target_wins"]].copy()
    result["league_average_wins"] = 41.0
    result["prior_net_rating_wins"] = features["prior_net_rating_proxy_wins"]
    result["best_available_baseline"] = result["prior_net_rating_wins"].fillna(result["league_average_wins"])
    return result


def baseline_metrics(forecasts: pd.DataFrame) -> dict[str, float | None]:
    if forecasts.empty or forecasts["target_wins"].isna().all():
        return {"mae": None, "rmse": None}
    errors = forecasts["best_available_baseline"] - forecasts["target_wins"]
    return {"mae": round(float(errors.abs().mean()), 3), "rmse": round(float(np.sqrt(np.mean(errors**2))), 3)}

