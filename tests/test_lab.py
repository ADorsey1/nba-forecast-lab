from pathlib import Path
import pandas as pd
import pytest
from nba_forecast.lab import projection
from streamlit.testing.v1 import AppTest


def fixture():
    roster=pd.DataFrame([dict(player_id='a',player_name='A',team_abbr='PHI',minutes=30.,impact=8.,availability=100.),dict(player_id='b',player_name='B',team_abbr='BOS',minutes=30.,impact=0.,availability=100.)])
    forecast=pd.DataFrame(dict(team_abbr=['PHI','BOS'],holistic_predicted_wins=[45.,50.]))
    return roster,forecast


def test_baseline_transfer_and_no_mutation():
    roster, forecast=fixture()
    assert projection(roster,roster,forecast).change.eq(0).all()
    scenario=roster.copy(); scenario.loc[0,'team_abbr']='BOS'
    out=projection(roster,scenario,forecast).set_index('team_abbr')
    assert out.loc['PHI','change'] < 0 < out.loc['BOS','change']
    assert roster.loc[0,'team_abbr']=='PHI'


def test_absence_and_invalid_input():
    roster, forecast=fixture(); scenario=roster.copy();scenario.loc[0,'availability']=0
    assert projection(roster,scenario,forecast).set_index('team_abbr').loc['PHI','change']<0
    scenario.loc[0,'minutes']=49
    with pytest.raises(ValueError): projection(roster,scenario,forecast)
    with pytest.raises(ValueError): projection(roster,pd.concat([roster,roster]),forecast)


def test_lab_navigation_and_fantasy_signing():
    app=AppTest.from_file(Path(__file__).resolve().parents[1] / 'app/streamlit_app.py').run(timeout=30)
    app.button(key='top_nav_Creative Lab').click().run(timeout=30)
    assert not app.exception
    before=app.session_state['lab_roster'].copy()
    next(x for x in app.text_input if x.label=='Player name').set_value('Test Prospect')
    next(x for x in app.button if x.label=='Add to lab team').click().run(timeout=30)
    assert not app.exception
    assert len(app.session_state['lab_roster'])==len(before)+1
    assert len(app.session_state['lab_base'])==len(before)


def test_portable_lab_without_history(tmp_path, monkeypatch):
    import shutil
    root = Path(__file__).resolve().parents[1]
    for folder in ['processed', 'raw/live']:
        shutil.copytree(root / 'data' / folder, tmp_path / folder)
    monkeypatch.setenv('NBA_FORECAST_DATA_ROOT', str(tmp_path))
    def no_history(*args, **kwargs):
        raise AssertionError('Deployed lab must not read parquet history')
    monkeypatch.setattr(pd, 'read_parquet', no_history)
    app = AppTest.from_file(root / 'app/streamlit_app.py').run(timeout=30)
    app.button(key='top_nav_Creative Lab').click().run(timeout=30)
    assert not app.exception
    baseline = app.session_state['lab_base']
    player = baseline.loc[baseline.impact.abs().idxmax()]
    scenario = baseline.copy()
    scenario.loc[scenario.player_id.eq(player.player_id), 'team_abbr'] = 'Free agents'
    result = projection(baseline, scenario, app.session_state['lab_forecast'])
    assert result.change.abs().max() > 0
