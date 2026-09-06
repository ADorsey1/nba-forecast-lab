"""Session-only roster experiments; published forecasts are never modified."""
from pathlib import Path
import numpy as np
import pandas as pd


def player_pool(rosters: pd.DataFrame, history_path: Path) -> pd.DataFrame:
    pool = rosters[['player_id', 'player_name', 'team_abbr']].copy()
    pool['player_id'] = pool.player_id.astype(str).str.replace(r'\.0$', '', regex=True)
    pool = pool.drop_duplicates('player_id').reset_index(drop=True)
    pool['minutes'] = 12.0
    pool['impact'] = 0.0
    pool['availability'] = 100.0
    pool['evidence'] = 'Neutral assumption — no matched history'
    if history_path.exists():
        history = pd.read_parquet(history_path, columns=['player_id','year','min','gp','net_rating'])
        history = history[pd.to_numeric(history.year, errors='coerce').eq(pd.to_numeric(history.year, errors='coerce').max())].copy()
        history['player_id'] = history.player_id.astype(str).str.replace(r'\.0$', '', regex=True)
        history = history.sort_values('min', ascending=False).drop_duplicates('player_id').set_index('player_id')
        for i, row in pool.iterrows():
            if row.player_id in history.index:
                h = history.loc[row.player_id]
                pool.loc[i, 'minutes'] = float(np.clip(h['min'] / max(h.gp, 1), 0, 48)) if pd.notna(h['min']) else 12.0
                pool.loc[i, 'impact'] = float(np.clip(h.net_rating, -20, 20)) if pd.notna(h.net_rating) else 0.0
                pool.loc[i, 'evidence'] = 'Latest historical season; on-court net rating'
    return pool


def projection(baseline: pd.DataFrame, scenario: pd.DataFrame, forecast: pd.DataFrame, sensitivity: float = 2.7) -> pd.DataFrame:
    """Anchor to published wins and translate rotation changes into illustrative deltas.

    Allocate 240 team minutes proportionally when overbooked, fill shortfalls
    with neutral replacement minutes, and keep minutes fixed during absences.
    On-court ratings are proxies, not causal player impact or retrained models.
    """
    def ratings(frame):
        if frame.player_id.duplicated().any():
            raise ValueError('A player may belong to only one team.')
        for column, low, high in [('minutes',0,48),('impact',-20,20),('availability',0,100)]:
            if not pd.to_numeric(frame[column], errors='coerce').between(low,high).all():
                raise ValueError(f'Invalid {column}')
        f = frame.copy()
        totals = f.groupby('team_abbr').minutes.transform('sum').clip(lower=240)
        f['contribution'] = f.minutes / totals * f.impact * f.availability / 100
        return f.groupby('team_abbr').contribution.sum()
    before, after = ratings(baseline), ratings(scenario)
    result = forecast[['team_abbr','holistic_predicted_wins']].copy()
    result['rotation_delta'] = result.team_abbr.map(after).fillna(0) - result.team_abbr.map(before).fillna(0)
    result['scenario_wins'] = (result.holistic_predicted_wins + sensitivity * result.rotation_delta).clip(0,82)
    result['change'] = result.scenario_wins - result.holistic_predicted_wins
    return result.sort_values('scenario_wins', ascending=False).reset_index(drop=True)
