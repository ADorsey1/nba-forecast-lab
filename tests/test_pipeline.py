from pathlib import Path

import pytest

from nba_forecast.features import build_team_model_features
from nba_forecast.historical import build_historical_roster_features, build_historical_training_table
from nba_forecast.io import drop_team_aggregates, load_workbook
from nba_forecast import live
from nba_forecast.models import build_baseline_forecasts
from nba_forecast.simulation import simulate_outcomes
from nba_forecast.team_colors import TEAM_COLORS, get_team_theme
from nba_forecast.training import expanding_backtest


WORKBOOK = Path("nba_forecast_data_2025_26 (1).xlsx")
PUBLIC_SOURCE = Path("data/raw/llimllib_nba_data")


def test_aggregate_player_row_is_removed():
    sheets = load_workbook(WORKBOOK)
    players = drop_team_aggregates(sheets["players_season_stats"])
    assert "2TM" not in set(players["team_abbr"])


def test_team_feature_grain_is_one_row_per_team_season():
    sheets = load_workbook(WORKBOOK)
    features = build_team_model_features(sheets)
    assert len(features) == 30
    assert not features.duplicated(["team_abbr", "season"]).any()


def test_baseline_and_simulation_outputs_have_expected_shape():
    sheets = load_workbook(WORKBOOK)
    features = build_team_model_features(sheets)
    forecasts = build_baseline_forecasts(features)
    simulations = simulate_outcomes(forecasts, simulations=500)
    assert len(forecasts) == 30
    assert len(simulations) == 30
    assert simulations["wins_p10"].between(0, 82).all()
    assert simulations["wins_p90"].between(0, 82).all()


def test_roster_transition_features_have_team_season_grain():
    transitions = build_historical_roster_features(PUBLIC_SOURCE)
    assert len(transitions) == len(transitions[["season_end_year", "team_abbr"]].drop_duplicates())
    assert transitions["team_abbr"].nunique() == 30
    assert transitions["season_end_year"].max() >= 2026
    continuity = transitions["prior_roster_continuity_minutes_share"].dropna()
    assert continuity.between(0, 1).all()


def test_roster_aware_backtest_is_available():
    training = build_historical_training_table(PUBLIC_SOURCE)
    predictions, metrics = expanding_backtest(training)
    assert len(predictions) > 0
    assert "roster_aware_predicted_wins" in predictions.columns
    assert metrics["roster_aware_mae"] is not None


def test_team_colorways_cover_all_nba_teams_with_readable_text():
    expected_teams = {
        "ATL", "BOS", "BRK", "CHO", "CLE", "DAL", "DEN", "DET", "GSW", "HOU",
        "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK", "OKC",
        "ORL", "PHI", "PHO", "POR", "SAC", "SAS", "TOR", "UTA", "WAS", "CHI",
    }
    assert set(TEAM_COLORS) == expected_teams
    for team in expected_teams:
        theme = get_team_theme(team)
        assert theme["display"]
        assert theme["display_text"] in {"#08131f", "#ffffff"}


def test_default_theme_stays_dark_and_team_theme_changes_full_surface_system():
    default = get_team_theme(None)
    knicks = get_team_theme("NYK")
    assert default["background"] == "#08131f"
    assert default["button"] == "#ff7345"
    assert knicks["background"] == "#f8fafc"
    assert knicks["surface"] == "#ffffff"
    assert knicks["display"] == "#006BB6"
    assert knicks["button"] == "#F58426"
    assert knicks["button_text"] == "#08131f"


def test_live_json_response_size_is_bounded(monkeypatch):
    class OversizedResponse:
        content = b"x" * (live.MAX_JSON_RESPONSE_BYTES + 1)

        def raise_for_status(self):
            return None

    monkeypatch.setattr(live.requests, "get", lambda *args, **kwargs: OversizedResponse())
    with pytest.raises(live.requests.RequestException, match="exceeded"):
        live._get_json("https://example.test/data.json")
