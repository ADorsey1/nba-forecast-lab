"""Fetch the pinned public history commit without changing an existing checkout."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'data/history-source.json'


def setup(destination: Path) -> None:
    lock = json.loads(LOCK.read_text())
    if destination.exists():
        revision = subprocess.check_output(['git','-C',str(destination),'rev-parse','HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git','-C',str(destination),'status','--porcelain'], text=True).strip()
        if revision != lock['revision'] or dirty:
            raise ValueError('Existing history differs from the pinned clean commit; use a new --destination')
        for name in lock['files']:
            if not (destination/name).is_file():
                raise ValueError(f'Missing history file {name}; use a new --destination')
        print(f'Pinned history already available: {revision}')
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.history-', dir=destination.parent))
    try:
        subprocess.run(['git','init',str(stage)], check=True, capture_output=True)
        subprocess.run(['git','-C',str(stage),'remote','add','origin',lock['repository']], check=True)
        subprocess.run(['git','-C',str(stage),'config','remote.origin.promisor','true'], check=True)
        subprocess.run(['git','-C',str(stage),'config','remote.origin.partialclonefilter','blob:none'], check=True)
        subprocess.run(['git','-C',str(stage),'fetch','--depth=1','--filter=blob:none','origin',lock['revision']], check=True)
        subprocess.run(['git','-C',str(stage),'sparse-checkout','init','--no-cone'], check=True)
        subprocess.run(['git','-C',str(stage),'sparse-checkout','set','--no-cone','--stdin'], input='\n'.join('/'+name for name in lock['files'])+'\n', text=True, check=True)
        subprocess.run(['git','-C',str(stage),'checkout','--detach',lock['revision']], check=True)
        for name in lock['files']:
            if not (stage/name).is_file():
                raise ValueError(f'Pinned source is missing {name}')
        stage.rename(destination)
        print(f'Pinned history installed: {lock["revision"]}')
    finally:
        if stage.exists():
            shutil.rmtree(stage)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=ROOT/'data/raw/llimllib_nba_data')
    args = parser.parse_args()
    setup(args.destination.resolve())
