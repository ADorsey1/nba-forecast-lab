"""Command-line entry point for the NBA forecast pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .audit import profile_workbook
from .features import build_team_model_features
from .historical import build_historical_training_table, build_live_roster_features, build_next_season_frame
from .io import load_workbook, require_sheets
from .live import fetch_live_context
from .models import baseline_metrics, build_baseline_forecasts
from .quality import build_data_quality_report
from .simulation import simulate_outcomes, simulate_schedule_outcomes
from .training import expanding_backtest, fit_next_season_forecast


def run(input_path: str | Path, output_dir: str | Path, public_source: str | Path | None = None, refresh_live: bool = False) -> dict[str, str]:
    sheets = load_workbook(input_path)
    require_sheets(sheets)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    audit = profile_workbook(sheets)
    features = build_team_model_features(sheets)
    forecasts = build_baseline_forecasts(features)
    simulations = simulate_outcomes(forecasts)

    with (output / "audit_report.json").open("w", encoding="utf-8") as handle:
        json.dump(audit, handle, indent=2, default=str)
    features.to_csv(output / "team_model_features.csv", index=False)
    forecasts.to_csv(output / "baseline_forecasts.csv", index=False)
    simulations.to_csv(output / "simulation_summary.csv", index=False)
    sheets["sources_and_dictionary"].to_csv(output / "data_dictionary.csv", index=False)
    with (output / "baseline_metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(baseline_metrics(forecasts), handle, indent=2)
    outputs = {"features": str(output / "team_model_features.csv"), "forecasts": str(output / "baseline_forecasts.csv"), "simulations": str(output / "simulation_summary.csv")}

    source = Path(public_source) if public_source else Path("data/raw/llimllib_nba_data")
    live_dir = Path("data/raw/live")
    if refresh_live or not (live_dir / "live_team_context.csv").exists():
        fetch_live_context(live_dir)
    if source.exists():
        historical = build_historical_training_table(source)
        next_season = build_next_season_frame(historical)
        live_roster_path = live_dir / "current_rosters.csv"
        if live_roster_path.exists():
            live_roster_features = build_live_roster_features(source, live_roster_path, live_dir / "current_injuries.csv")
            live_feature_columns = [column for column in live_roster_features.columns if column != "team_abbr"]
            next_season = next_season.drop(columns=live_feature_columns, errors="ignore").merge(live_roster_features, on="team_abbr", how="left")
        backtest, backtest_stats = expanding_backtest(historical)
        next_forecast = fit_next_season_forecast(historical, next_season)
        roster_projection_columns = [
            "team_abbr",
            "live_roster_expected_net_rating",
            "live_roster_projected_minutes",
            "live_roster_matched_players",
            "live_roster_injured_players",
            "live_roster_projection_wins",
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
            "roster_feature_source",
        ]
        available_roster_projection_columns = [column for column in roster_projection_columns if column in next_season.columns]
        next_forecast = next_forecast.merge(next_season[available_roster_projection_columns], on="team_abbr", how="left")
        next_forecast["independent_predicted_wins"] = next_forecast["predicted_wins"]
        if "roster_aware_predicted_wins" not in next_forecast.columns:
            next_forecast["roster_aware_predicted_wins"] = next_forecast["predicted_wins"]
        market_path = Path("data/raw/external_market_wintotals.csv")
        if market_path.exists():
            market = pd.read_csv(market_path)
            next_forecast = next_forecast.merge(market[["team_abbr", "market_win_total"]], on="team_abbr", how="left")
        if "market_win_total" not in next_forecast.columns:
            next_forecast["market_win_total"] = np.nan
        live_context_path = live_dir / "live_team_context.csv"
        if live_context_path.exists():
            live_context = pd.read_csv(live_context_path)
            next_forecast = next_forecast.merge(live_context, on="team_abbr", how="left")
            next_forecast["live_context_status"] = next_forecast.apply(
                lambda row: "live roster/injury/transaction context attached; schedule unavailable"
                if not bool(row.get("live_schedule_source_available", False))
                else "live roster/injury/transaction/schedule context attached",
                axis=1,
            )
            roster_component = next_forecast.get("roster_aware_predicted_wins", next_forecast["predicted_wins"])
            next_forecast["holistic_predicted_wins"] = np.where(
                roster_component.notna() & next_forecast["market_win_total"].notna(),
                0.25 * next_forecast["independent_predicted_wins"] + 0.25 * roster_component + 0.50 * next_forecast["market_win_total"],
                next_forecast["predicted_wins"],
            ).clip(0, 82)
            next_forecast["model_name"] = "holistic ensemble: form + roster + market prior"
            next_forecast["conference"] = np.where(next_forecast["team_abbr"].isin({"ATL", "BOS", "BRK", "CHO", "CHI", "CLE", "DET", "IND", "MIA", "MIL", "NYK", "ORL", "PHI", "TOR", "WAS"}), "East", "West")
            schedule_path = live_dir / "current_schedule.csv"
            schedule = pd.read_csv(schedule_path) if schedule_path.exists() and schedule_path.stat().st_size > 10 else pd.DataFrame()
            if not schedule.empty:
                next_simulation = simulate_schedule_outcomes(next_forecast, schedule)
            else:
                proxy_input = next_forecast.assign(best_available_baseline=next_forecast["holistic_predicted_wins"])
                next_simulation = simulate_outcomes(proxy_input)
                next_simulation["simulation_note"] = "Independent-win fallback; schedule provider unavailable."
        historical.to_csv(output / "historical_training.csv", index=False)
        transition_columns = [
            "season_end_year",
            "team_abbr",
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
            "roster_feature_source",
        ]
        historical[[column for column in transition_columns if column in historical.columns]].to_csv(output / "roster_transition_features.csv", index=False)
        backtest.to_csv(output / "backtest_predictions.csv", index=False)
        next_forecast.to_csv(output / "next_season_forecast.csv", index=False)
        next_simulation.to_csv(output / "next_season_simulation.csv", index=False)
        live_rosters = pd.read_csv(live_dir / "current_rosters.csv") if (live_dir / "current_rosters.csv").exists() else pd.DataFrame()
        live_injuries = pd.read_csv(live_dir / "current_injuries.csv") if (live_dir / "current_injuries.csv").exists() else pd.DataFrame()
        live_moves = pd.read_csv(live_dir / "transaction_ledger.csv") if (live_dir / "transaction_ledger.csv").exists() else pd.DataFrame()
        live_schedule = pd.read_csv(live_dir / "current_schedule.csv") if (live_dir / "current_schedule.csv").exists() else pd.DataFrame()
        manifest_path = live_dir / "source_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        quality = build_data_quality_report(features, historical, next_forecast, live_rosters, live_injuries, live_moves, live_schedule, manifest)
        with (output / "data_quality_report.json").open("w", encoding="utf-8") as handle:
            json.dump(quality, handle, indent=2, default=str)
        with (output / "backtest_metrics.json").open("w", encoding="utf-8") as handle:
            json.dump(backtest_stats, handle, indent=2)
        outputs.update({
            "historical": str(output / "historical_training.csv"),
            "roster_transitions": str(output / "roster_transition_features.csv"),
            "backtest": str(output / "backtest_predictions.csv"),
            "next_forecast": str(output / "next_season_forecast.csv"),
            "next_simulation": str(output / "next_season_simulation.csv"),
            "data_quality": str(output / "data_quality_report.json"),
        })
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to source .xlsx workbook")
    parser.add_argument("--output", default="data/processed", help="Output directory")
    parser.add_argument("--public-source", default=None, help="Path to cloned llimllib/nba_data repository")
    parser.add_argument("--refresh-live", action="store_true", help="Refresh current rosters, injuries, schedules, and transactions")
    args = parser.parse_args()
    for label, path in run(args.input, args.output, args.public_source, args.refresh_live).items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
