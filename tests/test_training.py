"""Model tests with explicit synthetic data; external integration stays separate."""
import pandas as pd
from nba_forecast.training import expanding_backtest


def test_future_targets_cannot_change_earlier_backtest_predictions():
    rows = [{'team_abbr': team, 'season':f'{year-1}-{str(year)[-2:]}', 'season_end_year':year, 'target_wins':40 + index + year % 3, 'prior_wins':38 + index + year % 2} for year in range(2010, 2018) for index, team in enumerate(['CHI','BOS','LAL'])]
    data = pd.DataFrame(rows)
    first, _ = expanding_backtest(data, min_train_seasons=3)
    changed = data.copy()
    changed.loc[changed.season_end_year == 2017, 'target_wins'] = 70
    second, _ = expanding_backtest(changed, min_train_seasons=3)
    earlier = first.season_end_year < 2017
    pd.testing.assert_series_equal(first.loc[earlier,'predicted_wins'], second.loc[earlier,'predicted_wins'])
    assert len(first) > 0
