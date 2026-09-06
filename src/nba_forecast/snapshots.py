"""Publish immutable datasets using one atomic pointer; readers pin one generation."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

import pandas as pd

from .teams import TEAMS, conference_for


class SnapshotError(ValueError):
    """A dataset cannot safely be served or published."""


TABLES = {
    'player_ratings': ('processed/player_ratings.csv', {'player_id', 'player_name', 'team_abbr', 'minutes', 'impact', 'availability', 'evidence'}),
    'features': ('processed/team_model_features.csv', {'team_abbr', 'season'}),
    'forecasts': ('processed/baseline_forecasts.csv', {'team_abbr'}),
    'simulations': ('processed/simulation_summary.csv', {'team_abbr'}),
    'next_forecast': ('processed/next_season_forecast.csv', {'team_abbr', 'season', 'predicted_wins', 'holistic_predicted_wins'}),
    'next_simulation': ('processed/next_season_simulation.csv', {'team_abbr', 'expected_wins', 'wins_p10', 'wins_p90', 'simulation_note'}),
    'rosters': ('raw/live/current_rosters.csv', {'team_abbr', 'player_name', 'player_id'}),
    'injuries': ('raw/live/current_injuries.csv', {'team_abbr', 'player_name', 'injury_status', 'estimated_return_date', 'comment'}),
    'moves': ('raw/live/transaction_ledger.csv', {'team_abbr', 'transaction_date', 'transaction_type', 'description'}),
}


def read_snapshot(root: Path) -> dict:
    """Validate files before exposing a coherent dataset to the app."""
    try:
        result = {}
        for key, (relative, required) in TABLES.items():
            frame = pd.read_csv(root / relative)
            if not required.issubset(frame.columns):
                raise SnapshotError(f'{relative}: missing required columns')
            result[key] = frame
        ratings = result['player_ratings']
        if ratings.empty or ratings.player_id.duplicated().any():
            raise SnapshotError('Player ratings must contain unique players')
        for column, low, high in [('minutes', 0, 48), ('impact', -20, 20), ('availability', 0, 100)]:
            if not pd.to_numeric(ratings[column], errors='coerce').between(low, high).all():
                raise SnapshotError(f'Invalid player ratings: {column}')
        ratings['player_id'] = ratings.player_id.astype(str).str.replace(r'\.0$', '', regex=True)
        forecast = result['next_forecast']
        simulation = result['next_simulation']
        if 'conference' in forecast and not forecast.conference.eq(forecast.team_abbr.map(conference_for)).all():
            raise SnapshotError('Forecast conference mapping is inconsistent')
        if len(forecast) != 30 or set(forecast.team_abbr) != TEAMS or forecast.season.nunique() != 1:
            raise SnapshotError('Forecast must contain 30 unique teams in one season')
        if len(simulation) != 30 or simulation.team_abbr.nunique() != 30 or set(simulation.team_abbr) != set(forecast.team_abbr):
            raise SnapshotError('Simulation teams must match forecast teams')
        for key, columns in [('next_forecast', ['predicted_wins', 'holistic_predicted_wins']), ('next_simulation', ['expected_wins', 'wins_p10', 'wins_p90'])]:
            for column in columns:
                if not pd.to_numeric(result[key][column], errors='coerce').between(0, 82).all():
                    raise SnapshotError(f'{key}: invalid {column}')
        if (simulation.wins_p10 > simulation.wins_p90).any():
            raise SnapshotError('Invalid simulation interval')
        result['manifest'] = json.loads((root / 'raw/live/source_manifest.json').read_text())
        result['quality'] = json.loads((root / 'processed/data_quality_report.json').read_text())
        result['metrics'] = json.loads((root / 'processed/backtest_metrics.json').read_text())
        if not all(isinstance(result[key], dict) for key in ('manifest', 'quality', 'metrics')):
            raise SnapshotError('Snapshot metadata must be objects')
        if result['quality'].get('status') != 'pass' or result['quality'].get('error_count') != 0:
            raise SnapshotError('Data quality checks failed')
        record_path = root / 'processed/forecast_record.json'
        result['forecast_record'] = json.loads(record_path.read_text()) if record_path.exists() else {}
        result['snapshot_root'] = str(root)
        return result
    except (OSError, ValueError, KeyError, TypeError) as error:
        if isinstance(error, SnapshotError):
            raise
        raise SnapshotError('Dataset files are missing or malformed') from error


def resolve_snapshot(data_root: Path) -> Path:
    """Read the pointer once; legacy bundled snapshots remain usable initially."""
    pointer = data_root / 'current.json'
    if not pointer.exists():
        return data_root
    try:
        generation = json.loads(pointer.read_text())['generation']
        if not isinstance(generation, str) or not generation or Path(generation).name != generation or generation in ('.', '..'):
            raise ValueError('Invalid generation')
        root = data_root / 'releases' / generation
        if not root.is_dir():
            raise ValueError('Generation not found')
        return root
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SnapshotError('Published snapshot pointer is invalid') from error


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.pointer-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def publish_snapshot(data_root: Path, build) -> Path:
    """Build and validate off-line; a failed build never changes the active pointer."""
    releases = data_root / 'releases'
    releases.mkdir(parents=True, exist_ok=True)
    generation = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid4().hex[:12]
    stage = Path(tempfile.mkdtemp(prefix='.staging-', dir=releases))
    try:
        build(stage)
        read_snapshot(stage)
        target = releases / generation
        stage.rename(target)
        atomic_json(data_root / 'current.json', {
            'generation': generation,
            'published_at_utc': datetime.now(timezone.utc).isoformat(),
        })
        return target
    finally:
        if stage.exists():
            shutil.rmtree(stage)
