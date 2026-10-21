"""Download the two upstream checkpoints into project-local data/models."""
import hashlib
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.ai import MODELS


def download(url, target, expected=None):
    if target.exists() and expected:
        if hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            print(f'{target.name}: already verified')
            return
    elif target.exists() and target.stat().st_size > 1_000_000:
        print(f'{target.name}: already downloaded')
        return
    tmp = target.with_suffix('.download')
    print(f'Downloading {target.name} ...', flush=True)
    try:
        digest = hashlib.sha256()
        with urllib.request.urlopen(url, timeout=120) as source, open(tmp, 'wb') as dest:
            while chunk := source.read(1024 * 1024):
                dest.write(chunk)
                digest.update(chunk)
        if expected and digest.hexdigest() != expected:
            raise RuntimeError(f'Checksum mismatch for {target.name}; download was not accepted.')
        os.replace(tmp, target)
        print(f'{target.name}: complete ({target.stat().st_size / 1024 / 1024:.1f} MB)', flush=True)
    finally:
        tmp.unlink(missing_ok=True)


if __name__ == '__main__':
    MODELS.mkdir(parents=True, exist_ok=True)
    download('https://raw.githubusercontent.com/ChaoningZhang/MobileSAM/f706ad9c4eb7f219c00d9050e46328518ffb65d2/weights/mobile_sam.pt', MODELS / 'mobile_sam.pt')
    import clip
    url = clip.clip._MODELS['ViT-B/32']
    download(url, MODELS / 'ViT-B-32.pt', url.split('/')[-2])
    print('Verifying model loading ...', flush=True)
    from backend.ai import load_sam, load_clip
    load_sam()
    load_clip()
    print('MobileSAM and CLIP are ready. Restart ChromaDAM if it is running.', flush=True)
