"""Archive the exact published forecast and evaluate it only against completed outcomes."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .teams import TEAMS


PREDICTIONS = ['holistic_predicted_wins', 'independent_predicted_wins', 'roster_aware_predicted_wins', 'market_win_total']


def archive_forecast(root: Path, *, now: datetime | None = None) -> dict:
    """Never infer historical publication dates from reconstructed season files."""
    now = now or datetime.now(timezone.utc)
    path = root / 'processed/next_season_forecast.csv'
    frame = pd.read_csv(path)
    manifest = json.loads((root/'raw/live/source_manifest.json').read_text())
    schedule = pd.read_csv(root/'raw/live/current_schedule.csv')
    history = pd.read_csv(root/'processed/historical_training.csv', usecols=['season_end_year'])
    first_game = pd.to_datetime(schedule.game_date, errors='coerce', utc=True).min()
    fetched = pd.to_datetime(manifest.get('fetched_at_utc'), errors='coerce', utc=True)
    market_dates = pd.to_datetime(frame.get('market_source_date', pd.Series(dtype=str)), errors='coerce', utc=True)
    reasons = []
    if pd.isna(first_game) or first_game <= pd.Timestamp(now):
        reasons.append('Publication is not verified before the first scheduled game')
    if fetched is None or pd.isna(fetched) or fetched > pd.Timestamp(now):
        reasons.append('Live feature observation time is missing or after publication')
    if manifest.get('season') != frame.season.iloc[0]:
        reasons.append('Live context season does not match forecast season')
    if not history.season_end_year.lt(int(frame.season_end_year.iloc[0])).all():
        reasons.append('Training contains target-season outcomes')
    if not frame.get('roster_feature_source', pd.Series('', index=frame.index)).fillna('').str.contains('live roster', case=False).all():
        reasons.append('Roster evidence is retrospective or unavailable')
    if len(market_dates) != len(frame) or market_dates.isna().any() or market_dates.gt(pd.Timestamp(now)).any():
        reasons.append('Market observation dates are unavailable or after publication')
    record = {
        'schema_version': 1,
        'recorded_at_utc': now.isoformat(),
        'season': frame.season.iloc[0],
        'first_game_utc': None if pd.isna(first_game) else first_game.isoformat(),
        'features_observed_at_utc': None if fetched is None or pd.isna(fetched) else fetched.isoformat(),
        'forecast_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'preseason_eligible': not reasons,
        'ineligibility_reasons': reasons,
        'validation_status': 'Awaiting completed-season outcomes; ensemble accuracy is not yet measured',
    }
    with (root/'processed/forecast_record.json').open('x') as handle:
        json.dump(record, handle, indent=2)
    return record


def evaluate_snapshot(root: Path, outcomes: pd.DataFrame) -> dict:
    """Require a genuine pre-season record and all 30 completed team outcomes."""
    record = json.loads((root/'processed/forecast_record.json').read_text())
    path = root/'processed/next_season_forecast.csv'
    if hashlib.sha256(path.read_bytes()).hexdigest() != record['forecast_sha256']:
        raise ValueError('Archived forecast changed after recording')
    if not record.get('preseason_eligible'):
        raise ValueError('Snapshot is not eligible for preseason evaluation')
    recorded = pd.to_datetime(record['recorded_at_utc'], utc=True)
    start = pd.to_datetime(record['first_game_utc'], utc=True)
    observed = pd.to_datetime(record['features_observed_at_utc'], utc=True)
    if not observed <= recorded < start:
        raise ValueError('Forecast timestamps violate the preseason cutoff')
    required = {'team_abbr','season','actual_wins','season_completed_at_utc'}
    if not required.issubset(outcomes.columns):
        raise ValueError('Outcomes need team, season, actual_wins and season_completed_at_utc')
    if len(outcomes) != 30 or set(outcomes.team_abbr) != TEAMS or outcomes.duplicated(['team_abbr','season']).any():
        raise ValueError('Exactly 30 unique completed team outcomes are required')
    if not outcomes.season.eq(record['season']).all():
        raise ValueError('Outcome season mismatch')
    completed = pd.to_datetime(outcomes.season_completed_at_utc, errors='coerce', utc=True)
    if completed.isna().any() or not completed.gt(start).all() or completed.gt(pd.Timestamp.now(tz='UTC')).any():
        raise ValueError('Season completion time is invalid or in the future')
    wins = pd.to_numeric(outcomes.actual_wins, errors='coerce')
    if not wins.between(0,82).all() or not wins.mod(1).eq(0).all() or wins.sum() != 1230:
        raise ValueError('Completed 82-game season must have valid integer wins totaling 1230')
    forecast = pd.read_csv(path)
    joined = forecast.merge(outcomes, on=['team_abbr','season'], validate='one_to_one')
    scores = {}
    for column in PREDICTIONS:
        if column in joined and joined[column].notna().all():
            error = pd.to_numeric(joined[column], errors='raise') - pd.to_numeric(joined.actual_wins, errors='raise')
            scores[column] = {'mae':float(error.abs().mean()), 'rmse':float(np.sqrt((error**2).mean()))}
    simulation = pd.read_csv(root/'processed/next_season_simulation.csv')
    intervals = simulation.merge(outcomes[['team_abbr','actual_wins']], on='team_abbr', validate='one_to_one')
    coverage = intervals.actual_wins.between(intervals.wins_p10, intervals.wins_p90).mean()
    return {'season':record['season'], 'forecast_recorded_at_utc':record['recorded_at_utc'], 'team_count':len(joined), 'scores':scores, 'p10_p90_empirical_coverage':float(coverage), 'note':'One completed season is limited evidence; compare multiple preregistered seasons before claiming calibration.'}
