# NBA Forecast

League-wide NBA forecasting pipeline and analytical app.

This repository turns the supplied workbook and an optional public historical dump into a reproducible team-season modeling dataset, creates transparent baselines, estimates scenario ranges, and exposes the results through a small Streamlit app. It is deliberately structured so new seasons and data providers can be added without changing the core data contract.

## Current scope

The supplied workbook contains one `2025-26` season. When `data/raw/llimllib_nba_data` is present, the current run also trains on public team, player, and game-log history from 2009-10 onward. The roster-aware backtest uses a clearly labeled season-roster proxy because the public dump does not provide a complete historical transaction ledger.

Important safeguards:

- Raw workbook data is never edited in place.
- The `2TM` player aggregate is excluded from team joins.
- Final-season outcomes remain targets, not model inputs.
- Feature names distinguish prior-season signals from current-season context.
- Missing fields are preserved and reported rather than silently imputed.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "src"
python -m nba_forecast.cli --input "nba_forecast_data_2025_26 (1).xlsx" --output data/processed
streamlit run app/streamlit_app.py
```

The pipeline automatically uses `data/raw/llimllib_nba_data` when the public historical dump is present. Pass `--public-source` to use a different local copy.

## Login setup

The app requires a configured username and password before showing forecasts or live context. Generate a local secrets file interactively so the password never appears in shell history:

```powershell
& ".venv\Scripts\python.exe" scripts\setup_auth.py
```

The setup script writes `.streamlit/secrets.toml`, which is ignored by Git. For a hosted deployment, add the same `[auth]` values through the host's secrets manager. See `.streamlit/secrets.toml.example` for the expected shape. This is a lightweight app gate for a private portfolio deployment, not a replacement for an identity provider in a multi-user production system.

## Pipeline outputs

- `audit_report.json`: sheet-level row counts, missingness, key checks, and warnings
- `team_model_features.csv`: one row per team-season with targets and engineered predictors
- `baseline_forecasts.csv`: league-average and prior-rating forecasts
- `simulation_summary.csv`: Monte Carlo win ranges and playoff-proxy probabilities
- `historical_training.csv`: prior-season-only team features and win targets
- `backtest_predictions.csv`: expanding-window out-of-time predictions
- `backtest_metrics.json`: aggregate backtest MAE and RMSE
- `next_season_forecast.csv`: final-fit forecast for the next season in the public data
- `roster_transition_features.csv`: player-ID-based season roster transition proxy with prior production and continuity metrics
- `next_season_simulation.csv`: future-season uncertainty ranges, using schedule simulation when available and an explicitly labeled fallback otherwise
- `data_quality_report.json`: machine-readable data contract checks for team grain, roster keys, schedule duplicates, and artifact completeness
- `data/raw/live/current_rosters.csv`: current NBA.com roster snapshot
- `data/raw/live/current_injuries.csv`: current ESPN injury snapshot
- `data/raw/live/current_transactions.csv`: recent NBA player movement snapshot
- `data/raw/live/transaction_ledger.csv`: deduplicated cumulative movement ledger
- `data/raw/live/live_team_context.csv`: team-level live context merged into the forecast

## Refresh live context

The live layer can be refreshed before a forecast run:

```powershell
$env:PYTHONPATH = "src"
& ".venv\Scripts\python.exe" -m nba_forecast.cli --input "nba_forecast_data_2025_26 (1).xlsx" --output data/processed --public-source data/raw/llimllib_nba_data --refresh-live
```

The live context is timestamped and source-labeled. It is used as current-season diagnostic context; the historical win model is not silently retrained on future information. Schedule-aware simulation uses published games when available and fills unresolved NBA Cup-dependent games with neutral average-opponent draws.

### Optional historical source

The historical training extension uses the public `llimllib/nba_data` dump. It is intentionally kept outside this repository because it is a separate Git repository. To restore it after cloning:

```powershell
New-Item -ItemType Directory -Force -Path data/raw | Out-Null
git clone --filter=blob:none --no-checkout https://github.com/llimllib/nba_data.git data/raw/llimllib_nba_data
git -C data/raw/llimllib_nba_data sparse-checkout init --no-cone
git -C data/raw/llimllib_nba_data sparse-checkout set data/team_summary.json data/team_summary.parquet data/playerstats.parquet data/gamelogs.parquet data/player_game_logs.parquet data/metadata.json
git -C data/raw/llimllib_nba_data checkout
```

The Recent Moves page reads the cumulative, deduplicated transaction ledger. It updates automatically when the scheduled refresh script runs, but the Streamlit page itself does not poll live providers on every page load. A manual `--refresh-live` run is available when an immediate update is needed. The app keeps the navy/orange league-wide theme by default and applies an accessibility-checked full-site team theme when a team is focused, including the page background, cards, navigation, controls, charts, and tables.

The next-season forecast now exposes separate `independent_predicted_wins` and `roster_aware_predicted_wins` columns. The independent model uses prior team, player, and game-log features. The roster-aware model adds a player-ID-based season-roster transition proxy. Because the public historical dump does not include a complete historical transaction ledger, that proxy is explicitly labeled as retrospective season-roster evidence rather than a perfect preseason snapshot. A separate `live_roster_projection_wins` field is a minutes- and availability-weighted current-rotation diagnostic.

The next-season ensemble also includes an external market prior from the dated win-total snapshot in `data/raw/external_market_wintotals.csv`. Its weight is explicit in the pipeline: 25% historical form, 25% current-roster talent, and 50% market prior. This is reported as a benchmark-informed ensemble, not as a purely independent model.

See `SECURITY.md` for the local security controls, secret scan, provider response limits, and requirements for a future hosted deployment.

For automatic Windows refreshes, schedule `scripts/refresh_forecast.ps1` in Task Scheduler. A daily schedule during the offseason and a six-hour schedule during the regular season are reasonable defaults. The script refreshes rosters, injuries, transactions, the cumulative transaction ledger, and forecast artifacts in one run.

## Next data milestone

Replace the retrospective season-roster proxy with historical opening-night roster snapshots and a complete offseason transaction ledger. Then calibrate player aging, projected minutes, lineup fit, and game-level probabilities against those snapshots.
