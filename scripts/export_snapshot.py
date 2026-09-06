"""Export a validated runtime release into the portable, git-tracked bundle."""
from pathlib import Path
import argparse
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from nba_forecast.snapshots import TABLES, read_snapshot, resolve_snapshot


def export(data_root: Path) -> None:
    source = resolve_snapshot(data_root)
    read_snapshot(source)
    files = {relative for relative, _ in TABLES.values()} | {
        'raw/live/source_manifest.json', 'raw/live/current_transactions.csv',
        'raw/live/current_schedule.csv', 'raw/live/live_team_context.csv',
        'processed/data_quality_report.json', 'processed/backtest_metrics.json',
        'processed/forecast_record.json',
    }
    if source.resolve() != data_root.resolve():
        for relative in sorted(files):
            target = data_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, target)
    read_snapshot(data_root)
    print(f'Validated portable bundle: {len(files)} files')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=ROOT / 'data')
    export(parser.parse_args().data_root.resolve())
