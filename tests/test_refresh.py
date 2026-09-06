import importlib.util
import json
from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/refresh_forecast.py'
spec = importlib.util.spec_from_file_location('refresh_forecast', SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def inputs(tmp_path):
    workbook = tmp_path / 'workbook.xlsx'
    workbook.touch()
    source = tmp_path / 'history'
    source.mkdir()
    for name in ('team_summary.json', 'playerstats.parquet', 'gamelogs.parquet'):
        (source / name).touch()
    return workbook, source


def test_command_works_from_other_directory(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT), '--help'], cwd=tmp_path, capture_output=True)
    assert result.returncode == 0
    assert b'--data-root' in result.stdout


def test_failure_reports_nonzero_and_persists_status(tmp_path):
    assert runner.refresh(input_path=tmp_path/'missing', public_source=tmp_path, data_root=tmp_path) == 1
    assert json.loads((tmp_path/'refresh_status.json').read_text())['status'] == 'failed'


def test_refresh_uses_portable_paths_and_propagates_failure(tmp_path, monkeypatch):
    workbook, source = inputs(tmp_path)
    calls = []
    def invoke(command, **kwargs):
        calls.append((command, kwargs))
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(runner.subprocess, 'run', invoke)
    assert runner.refresh(input_path=workbook, public_source=source, data_root=tmp_path) == 1
    command, options = calls[0]
    assert command[0] == sys.executable
    assert options['cwd'] == runner.ROOT
    assert str(tmp_path/'raw/live') in command


def test_check_does_not_launch_refresh(tmp_path, monkeypatch):
    workbook, source = inputs(tmp_path)
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(AssertionError('Unexpected refresh')))
    assert runner.refresh(input_path=workbook, public_source=source, data_root=tmp_path, check=True) == 0
