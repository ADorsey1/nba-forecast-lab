from datetime import datetime, timezone
import json

import pandas as pd
import pytest

from nba_forecast.evaluation import archive_forecast, evaluate_snapshot
from nba_forecast.teams import TEAMS


def fixture_snapshot(tmp_path):
    processed = tmp_path/'processed'
    live = tmp_path/'raw/live'
    processed.mkdir(parents=True)
    live.mkdir(parents=True)
    teams = sorted(TEAMS)
    forecast = pd.DataFrame({'team_abbr':teams, 'season':'2025-26', 'season_end_year':2026, 'holistic_predicted_wins':42, 'independent_predicted_wins':40, 'roster_aware_predicted_wins':41, 'market_win_total':43, 'market_source_date':'2025-09-01', 'roster_feature_source':'live roster plus latest player history'})
    forecast.to_csv(processed/'next_season_forecast.csv', index=False)
    pd.DataFrame({'team_abbr':teams, 'wins_p10':35, 'wins_p90':45}).to_csv(processed/'next_season_simulation.csv', index=False)
    pd.DataFrame({'season_end_year':[2024,2025]}).to_csv(processed/'historical_training.csv', index=False)
    pd.DataFrame({'game_date':['2025-10-20']}).to_csv(live/'current_schedule.csv', index=False)
    (live/'source_manifest.json').write_text(json.dumps({'fetched_at_utc':'2025-09-01', 'season':'2025-26'}))
    outcomes = pd.DataFrame({'team_abbr':teams, 'season':'2025-26', 'actual_wins':41, 'season_completed_at_utc':'2026-06-30'})
    return outcomes


def test_scores_actual_published_ensemble_and_coverage(tmp_path):
    outcomes = fixture_snapshot(tmp_path)
    archive_forecast(tmp_path, now=datetime(2025,9,2,tzinfo=timezone.utc))
    result = evaluate_snapshot(tmp_path, outcomes)
    assert result['scores']['holistic_predicted_wins']['mae'] == 1
    assert result['scores']['market_win_total']['mae'] == 2
    assert result['p10_p90_empirical_coverage'] == 1


def test_late_publication_cannot_be_backdated(tmp_path):
    outcomes = fixture_snapshot(tmp_path)
    record = archive_forecast(tmp_path, now=datetime(2026,9,2,tzinfo=timezone.utc))
    assert not record['preseason_eligible']
    with pytest.raises(ValueError, match='eligible'):
        evaluate_snapshot(tmp_path, outcomes)
    with pytest.raises(FileExistsError):
        archive_forecast(tmp_path)


def test_modified_forecast_cannot_be_evaluated(tmp_path):
    outcomes = fixture_snapshot(tmp_path)
    archive_forecast(tmp_path, now=datetime(2025,9,2,tzinfo=timezone.utc))
    with (tmp_path/'processed/next_season_forecast.csv').open('a') as handle:
        handle.write('\n')
    with pytest.raises(ValueError, match='changed'):
        evaluate_snapshot(tmp_path, outcomes)


@pytest.mark.parametrize('change', ['wrong_season', 'future_results', 'missing_team', 'invalid_wins'])
def test_outcome_contract(tmp_path, change):
    outcomes = fixture_snapshot(tmp_path)
    archive_forecast(tmp_path, now=datetime(2025,9,2,tzinfo=timezone.utc))
    if change == 'wrong_season':
        outcomes['season'] = '2024-25'
    elif change == 'future_results':
        outcomes['season_completed_at_utc'] = '2099-06-30'
    elif change == 'missing_team':
        outcomes = outcomes.iloc[:-1]
    else:
        outcomes['actual_wins'] = 82
    with pytest.raises(ValueError):
        evaluate_snapshot(tmp_path, outcomes)


def test_retrospective_rosters_are_ineligible(tmp_path):
    fixture_snapshot(tmp_path)
    path = tmp_path/'processed/next_season_forecast.csv'
    frame = pd.read_csv(path).assign(roster_feature_source='retrospective season roster')
    frame.to_csv(path,index=False)
    assert not archive_forecast(tmp_path, now=datetime(2025,9,2,tzinfo=timezone.utc))['preseason_eligible']
