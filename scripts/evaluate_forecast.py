"""Evaluate an immutable preseason snapshot using completed-season outcomes."""
import argparse
import json
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from nba_forecast.evaluation import evaluate_snapshot

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--outcomes', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate_snapshot(args.snapshot, pd.read_csv(args.outcomes))
    with args.report.open('x') as handle:
        json.dump(result, handle, indent=2)
    print(f'Evaluation saved to {args.report}')
