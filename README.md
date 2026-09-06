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

Python 3.12, macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

The app and Creative Lab work directly from the committed snapshot. Training history is needed only to generate a new snapshot:

```bash
python scripts/setup_history.py
python scripts/refresh_forecast.py
python scripts/export_snapshot.py
```

## Public access

The dashboard is public and read-only. Visitors do not need credentials, and existing local authentication secrets are not read by the app. Data refresh runs separately through a command-line job; the website exposes no refresh, upload, or administrative actions.

The interface includes a dark/light theme toggle, responsive navigation, site search, scroll progress, print-friendly styles, expandable FAQs, and copy-ready team summaries. UTM query parameters are captured only for the current session and displayed on Diagnostics for transparent campaign-context inspection.

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
- `data/raw/live/current_transactions.csv`: current NBA player movements plus dated signings reconciled from official team roster pages
- `data/raw/live/transaction_ledger.csv`: deduplicated cumulative movement ledger with source metadata
- `data/raw/live/live_team_context.csv`: team-level live context merged into the forecast

## Refresh live context

The live layer can be refreshed before a forecast run:

```powershell
$env:PYTHONPATH = "src"
& ".venv\Scripts\python.exe" -m nba_forecast.cli --input "nba_forecast_data_2025_26.xlsx" --output data/processed --public-source data/raw/llimllib_nba_data --refresh-live
```

The live context is timestamped and source-labeled. It is used as current-season diagnostic context; the historical win model is not silently retrained on future information. Schedule-aware simulation uses published games when available and fills unresolved NBA Cup-dependent games with neutral average-opponent draws.

### Historical source and scheduled updates

`python scripts/setup_history.py` installs the pinned public history used by the refresh worker. It is excluded from Git and is unnecessary for visitors or the Creative Lab.

The Recent Moves page reads the cumulative transaction ledger. The GitHub Actions refresh workflow attempts publication every six hours once enabled on the default branch. Failed jobs leave the previous bundle in place. Open dashboards check for local snapshot changes every minute; Creative Lab scenarios keep their initial baseline until reset. Team color schemes remain available across the site.

The next-season forecast now exposes separate `independent_predicted_wins` and `roster_aware_predicted_wins` columns. The independent model uses prior team, player, and game-log features. The roster-aware model adds a player-ID-based season-roster transition proxy. Because the public historical dump does not include a complete historical transaction ledger, that proxy is explicitly labeled as retrospective season-roster evidence rather than a perfect preseason snapshot. A separate `live_roster_projection_wins` field is a minutes- and availability-weighted current-rotation diagnostic.

The next-season ensemble also includes an external market prior from the dated win-total snapshot in `data/raw/external_market_wintotals.csv`. Its weight is explicit in the pipeline: 25% historical form, 25% current-roster talent, and 50% market prior. This is reported as a benchmark-informed ensemble, not as a purely independent model.

See `SECURITY.md` for the local security controls, secret scan, provider response limits, and requirements for a future hosted deployment.

For automatic Windows refreshes, schedule `scripts/refresh_forecast.ps1` in Task Scheduler. A daily schedule during the offseason and a six-hour schedule during the regular season are reasonable defaults. The script refreshes rosters, injuries, transactions, the cumulative transaction ledger, and forecast artifacts in one run.

## Next data milestone

Replace the retrospective season-roster proxy with historical opening-night roster snapshots and a complete offseason transaction ledger. Then calibrate player aging, projected minutes, lineup fit, and game-level probabilities against those snapshots.

## Publication and freshness policies

Use `python scripts/refresh_forecast.py` for portable refreshes. See [hosting and refresh](deploy/README.md) for Community Cloud setup and the optional Linux host. Failed updates preserve the last validated snapshot.

The dashboard labels context older than 24 hours as stale and distinguishes unavailable or unverified provider coverage. Market input rows require `team_abbr`, `season`, `market_win_total`, `source`, and `source_date`. A refresh rejects duplicate, wrong-season, future-dated, missing, or invalid market inputs. Inputs older than 30 days are retained as an explicitly labeled stale benchmark, preserving their original source date and ensemble weight while allowing live refreshes to continue. This benchmark is not current odds; update the CSV when new market totals are available.

## Forward evaluation

Historical component metrics do not validate the final 25/25/50 ensemble. Retrospective roster backtests and uncalibrated simulation ranges are labeled as such in the interface. Each new published generation records the actual forecast file hash, recording time, first scheduled game, feature observation time, and preseason eligibility. Existing reconstructed snapshots are not backdated.

After the season completes, provide a CSV with all 30 `team_abbr,season,actual_wins,season_completed_at_utc` rows. For an 82-game season, wins must total 1,230. Evaluate the immutable generation with:

```sh
.venv/bin/python scripts/evaluate_forecast.py --snapshot data/releases/GENERATION --outcomes completed_season.csv --report evaluation.json
```

The evaluator rejects late/unverified preseason records, changed forecasts, incomplete outcomes and season mismatches. It reports the ensemble and each available component's MAE/RMSE, plus empirical coverage of the simulation range. Synthetic test outcomes verify the arithmetic only; actual forecast skill remains unmeasured until eligible real outcomes exist. Protect archived generations and records with read-only storage/backups: hashes detect accidental forecast changes but are not a signature against an operator rewriting both files.

## Creative Lab

The Creative Lab is a browser-session sandbox. Visitors can move or trade current players, release players into a free-agent pool, create fantasy signings, edit rotation minutes, availability and net-rating assumptions, save up to ten comparisons, and export JSON or CSV. Published datasets remain read-only. Experiments pin their initial snapshot and require an explicit reset to use newer data.

Scenario wins equal published wins plus 2.7 (adjustable) times the change in minutes-weighted on-court net rating. Team minutes above 240 are normalized; missing or unavailable minutes use a neutral replacement. Player history uses the latest available season, with neutral assumptions explicitly labeled for unmatched players. This is an illustrative roster diagnostic, not a retrained model, causal player valuation, salary-cap validator or calibrated season simulation. Export before closing the session.

UI audit: branding/status overlap fixed with two-row navigation; mobile navigation wraps; dark team accents are lightened for readability; floating overlays removed; obsolete MENU copy corrected; reduced-motion preference respected. Published snapshot checks run every minute without reloading the browser or discarding lab state.

## License

Project code is MIT licensed; see [LICENSE](LICENSE). External datasets, provider content, and team marks retain their respective rights and terms.

Live providers are best-effort ESPN and NBA sources; coverage can be partial or unavailable. Basketball-Reference scraping is not used as a fallback. Schedule gaps are labeled and handled by the simulation fallback.
