import pytest
from nba_forecast.teams import EAST, WEST, TEAMS, conference_for


def test_current_league_conferences():
    assert len(EAST) == len(WEST) == 15
    assert len(TEAMS) == 30
    assert not EAST & WEST
    assert conference_for('CHI') == 'East'
    assert conference_for('LAL') == 'West'
    with pytest.raises(ValueError):
        conference_for('INVALID')
