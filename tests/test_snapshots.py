import json
from pathlib import Path
import shutil

import pytest

from nba_forecast.snapshots import SnapshotError, publish_snapshot, read_snapshot, resolve_snapshot

BUNDLED = Path(__file__).resolve().parents[1] / 'data'


def copy_bundle(stage):
    for folder in ('processed', 'raw/live'):
        shutil.copytree(BUNDLED / folder, stage / folder)


def test_success_publishes_complete_generation_and_pins_reader(tmp_path):
    first = publish_snapshot(tmp_path, copy_bundle)
    old_data = read_snapshot(resolve_snapshot(tmp_path))
    second = publish_snapshot(tmp_path, copy_bundle)
    assert first != second
    assert resolve_snapshot(tmp_path) == second
    assert Path(old_data['snapshot_root']) == first
    assert len(read_snapshot(first)['next_forecast']) == 30


@pytest.mark.parametrize('failure', ['exception', 'malformed', 'quality', 'missing'])
def test_failed_update_preserves_last_good_snapshot(tmp_path, failure):
    first = publish_snapshot(tmp_path, copy_bundle)
    before = (tmp_path / 'current.json').read_bytes()
    def broken(stage):
        copy_bundle(stage)
        if failure == 'exception':
            raise RuntimeError('Provider outage')
        if failure == 'malformed':
            (stage/'processed/next_season_forecast.csv').write_text('bad,data\n1,2\n')
        if failure == 'quality':
            (stage/'processed/data_quality_report.json').write_text('{"status":"error","error_count":1}')
        if failure == 'missing':
            (stage/'raw/live/source_manifest.json').unlink()
    with pytest.raises((SnapshotError, RuntimeError)):
        publish_snapshot(tmp_path, broken)
    assert (tmp_path/'current.json').read_bytes() == before
    assert resolve_snapshot(tmp_path) == first
    assert not list((tmp_path/'releases').glob('.staging-*'))


def test_invalid_pointer_is_rejected(tmp_path):
    (tmp_path/'current.json').write_text(json.dumps({'generation':'../escape'}))
    with pytest.raises(SnapshotError):
        resolve_snapshot(tmp_path)
