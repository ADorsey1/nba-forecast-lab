from datetime import datetime, timezone
import pandas as pd
import pytest
from nba_forecast.freshness import freshness, live_status, attach_market_priors

NOW = datetime(2026, 9, 6, tzinfo=timezone.utc)


@pytest.mark.parametrize('value,expected', [(None,'Unavailable'), ('bad','Unavailable'), ('2026-09-07','Invalid timestamp'), ('2026-09-02','Stale'), ('2026-09-06','Current')])
def test_freshness(value, expected):
    assert freshness(value, now=NOW) == expected


def test_live_availability_does_not_imply_current():
    rosters = pd.DataFrame({'team_abbr':['CHI']})
    assert live_status({'fetched_at_utc':'2026-09-06'}, rosters, now=NOW) == 'Partial / unverified'
    assert live_status({'fetched_at_utc':'2026-09-06'}, pd.DataFrame(), now=NOW) == 'Unavailable'


def frames():
    forecast = pd.DataFrame({'team_abbr':['CHI'], 'season':['2026-27']})
    market = forecast.assign(market_win_total=40, source='Dated source', source_date='2026-09-01')
    return forecast, market


def test_market_merge_preserves_provenance():
    forecast, market = frames()
    result = attach_market_priors(forecast, market, now=NOW)
    assert result.market_win_total.iloc[0] == 40
    assert result.market_source_date.iloc[0] == '2026-09-01'
    assert result.market_source.iloc[0] == 'Dated source'


@pytest.mark.parametrize('column,value', [('season','2025-26'), ('source_date','2026-01-01'), ('source_date','2026-09-07'), ('source_date',None), ('market_win_total',99), ('source','')])
def test_invalid_market_is_rejected(column, value):
    forecast, market = frames()
    market[column] = value
    with pytest.raises(ValueError):
        attach_market_priors(forecast, market, now=NOW)


def test_duplicate_and_missing_team_are_rejected():
    forecast, market = frames()
    with pytest.raises(ValueError):
        attach_market_priors(forecast, pd.concat([market, market]), now=NOW)
    with pytest.raises(ValueError):
        attach_market_priors(forecast.assign(team_abbr='BOS'), market, now=NOW)
