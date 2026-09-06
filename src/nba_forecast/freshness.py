"""Explicit UTC freshness policies and season-safe market inputs."""
from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd

LIVE_MAX_AGE_HOURS = 24
MARKET_MAX_AGE_DAYS = 30


def freshness(timestamp: object, *, now: datetime | None = None, max_age_hours: float = LIVE_MAX_AGE_HOURS) -> str:
    parsed = pd.to_datetime(timestamp, errors='coerce', utc=True)
    if parsed is None or pd.isna(parsed):
        return 'Unavailable'
    age = (pd.Timestamp(now or datetime.now(timezone.utc)) - parsed).total_seconds() / 3600
    if age < 0:
        return 'Invalid timestamp'
    return 'Current' if age <= max_age_hours else 'Stale'


def live_status(manifest: dict, rosters: pd.DataFrame, *, now: datetime | None = None) -> str:
    if rosters.empty:
        return 'Unavailable'
    state = freshness(manifest.get('fetched_at_utc'), now=now)
    if state != 'Current':
        return state
    availability = manifest.get('availability', {})
    if not availability or not all(availability.get(key) is True for key in ('rosters', 'injuries', 'schedule', 'transactions')):
        return 'Partial / unverified'
    return 'Current'


def attach_market_priors(forecast: pd.DataFrame, market: pd.DataFrame, *, allow_stale: bool = False, now: datetime | None = None) -> pd.DataFrame:
    """Validate priors; explicit stale fallback retains a labeled historical benchmark."""
    required = {'team_abbr', 'season', 'market_win_total', 'source', 'source_date'}
    if not required.issubset(market.columns):
        raise ValueError('Market priors require team, season, value, source and source_date')
    if market.duplicated(['team_abbr', 'season']).any():
        raise ValueError('Duplicate team-season market priors')
    if forecast.season.nunique() != 1 or not market.season.eq(forecast.season.iloc[0]).all():
        raise ValueError('Market prior season does not match forecast season')
    dates = market.source_date.map(lambda value: freshness(value, now=now, max_age_hours=24 * MARKET_MAX_AGE_DAYS))
    if not dates.isin(['Current', 'Stale'] if allow_stale else ['Current']).all():
        raise ValueError('Market prior date is missing, future, or older than 30 days')
    if not pd.to_numeric(market.market_win_total, errors='coerce').between(0, 82).all():
        raise ValueError('Market win totals must be numeric and between 0 and 82')
    if market.source.fillna('').str.strip().eq('').any():
        raise ValueError('Market source must be identified')
    inputs = market[list(sorted(required))].rename(columns={'source':'market_source', 'source_date':'market_source_date'})
    inputs['market_status'] = dates.map({'Current': 'Current', 'Stale': 'Stale benchmark'})
    result = forecast.merge(inputs, on=['team_abbr', 'season'], how='left', validate='one_to_one')
    if result.market_win_total.isna().any():
        raise ValueError('Market prior is missing a forecast team')
    return result
