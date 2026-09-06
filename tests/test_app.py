"""Public dashboard acceptance checks (no login secrets required)."""
from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_public_dashboard_does_not_load_auth():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app/streamlit_app.py').run(timeout=30)
    assert not app.exception
    assert any("Forecast the league." in item.value for item in app.markdown)
    assert not any(widget.label in {'Username', 'Password'} for widget in app.text_input)
    assert not any(widget.label in {'Sign in', 'Sign out', 'Refresh'} for widget in app.button)


def test_home_shell_exposes_snapshot_panel_and_primary_paths():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app/streamlit_app.py').run(timeout=30)
    assert not app.exception
    assert any('hero-panel' in item.value for item in app.markdown)
    assert {button.label for button in app.button} >= {'Open forecast →', 'Compare standings', 'Track roster moves'}


def test_unavailable_snapshot_has_friendly_error(tmp_path, monkeypatch):
    monkeypatch.setenv('NBA_FORECAST_DATA_ROOT', str(tmp_path))
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app/streamlit_app.py').run(timeout=30)
    assert not app.exception
    assert 'temporarily unavailable' in app.error[0].value


def test_standings_put_chicago_in_east():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app/streamlit_app.py').run(timeout=30)
    app.button(key='top_nav_Standings').click().run()
    conference = next(widget for widget in app.radio if widget.label == 'Conference')
    conference.set_value('East').run()
    assert not app.exception
    east = app.dataframe[0].value
    assert len(east) == 15
    assert 'CHI' in set(east['team'])
    conference = next(widget for widget in app.radio if widget.label == 'Conference')
    conference.set_value('West').run()
    assert not app.exception
    west = app.dataframe[0].value
    assert len(west) == 15
    assert 'CHI' not in set(west['team'])


def test_diagnostics_distinguishes_ensemble_from_backtest():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app/streamlit_app.py').run(timeout=30)
    app.button(key='top_nav_Diagnostics').click().run()
    assert not app.exception
    assert any('no measured forward accuracy' in item.value for item in app.warning)
    assert any('retrospective' in item.value for item in app.caption)
