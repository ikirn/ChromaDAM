"""Add locally generated demo illustrations using the actual upload API."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app import app

with TestClient(app) as client:
    names={asset['name'] for asset in client.get('/api/assets').json()['items']}
    for path in sorted((ROOT/'samples').iterdir()):
        if path.name=='crimson-running-shoe.png' or path.name in names:
            continue
        response=client.post('/api/assets',files={'file':(path.name,path.read_bytes())})
        if response.status_code!=201:
            raise RuntimeError(response.text)
        asset=response.json()
        tags=['demo illustration',path.stem.replace('-',' ')]
        client.patch(f"/api/assets/{asset['id']}",json={'tags':tags})
        print(f"Added {asset['name']}: {asset['method']}",flush=True)
    health=client.get('/api/health').json()
    assert not health['ai']['errors'],health
    print(health,flush=True)
