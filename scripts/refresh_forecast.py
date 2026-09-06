"""Portable refresh entry point. Exit nonzero and record status on any failure."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def refresh(*, input_path: Path, public_source: Path, data_root: Path, check: bool = False) -> int:
    status_path = data_root / 'refresh_status.json'
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'status': 'running'}
    try:
        if not input_path.is_file():
            raise FileNotFoundError(f'Workbook missing: {input_path}')
        source_data = public_source / 'data' if (public_source / 'data').is_dir() else public_source
        for name in ('team_summary.json', 'playerstats.parquet', 'gamelogs.parquet'):
            if not (source_data / name).is_file():
                raise FileNotFoundError(f'Historical source missing: {name}. Run scripts/setup_history.py first.')
        if check:
            print('Refresh inputs available.')
            return 0
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
        subprocess.run([
            sys.executable, '-m', 'nba_forecast.cli', '--input', str(input_path),
            '--output', str(data_root / 'processed'), '--public-source', str(public_source),
            '--live-dir', str(data_root / 'raw' / 'live'),
            '--market-path', str(ROOT / 'data' / 'raw' / 'external_market_wintotals.csv'),
            '--refresh-live',
        ], cwd=ROOT, env=env, check=True)
        status['status'] = 'success'
        return 0
    except (OSError, subprocess.CalledProcessError) as error:
        status.update(status='failed', error=str(error))
        print(f'Refresh failed: {error}', file=sys.stderr)
        return 1
    finally:
        if not check or status['status'] == 'failed':
            status['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
            temporary = status_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(status, indent=2) + '\n')
            temporary.replace(status_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'nba_forecast_data_2025_26 (1).xlsx')
    parser.add_argument('--public-source', type=Path, default=ROOT / 'data/raw/llimllib_nba_data')
    parser.add_argument('--data-root', type=Path, default=Path(os.environ.get('NBA_FORECAST_DATA_ROOT', ROOT / 'data')))
    parser.add_argument('--check', action='store_true', help='Validate required input files without fetching or running models')
    args = parser.parse_args()
    return refresh(input_path=args.input.resolve(), public_source=args.public_source.resolve(), data_root=args.data_root.resolve(), check=args.check)


if __name__ == '__main__':
    raise SystemExit(main())
