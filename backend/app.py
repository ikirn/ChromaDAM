import io
import json
import re
import shutil
import threading
import uuid
import warnings
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from . import ai, store
from .colors import color_share, contrast, extract_palette, hex_rgb

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 20 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 25_000_000
MUTATION_LOCK = threading.RLock()


@asynccontextmanager
async def lifespan(app):
    store.init()
    (ai.DATA / 'assets').mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title='ChromaDAM API', version='1.0.0', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=ROOT / 'frontend'), name='static')


@app.get('/')
def home():
    return FileResponse(ROOT / 'frontend' / 'index.html')


def required(asset_id, private=False):
    asset = store.get(asset_id, private)
    if asset is None:
        raise HTTPException(404, 'Asset not found.')
    return asset


@app.get('/api/health')
def health():
    with store.connection() as conn:
        counts = conn.execute('SELECT COUNT(*), SUM(embedding IS NOT NULL), SUM(favorite) FROM assets').fetchone()
    return {'status': 'ok', 'ai': ai.status(), 'assets': counts[0], 'indexed': counts[1] or 0,
            'favorites': counts[2] or 0, 'max_upload_mb': 20}


@app.get('/media/{asset_id}/{kind}')
def media(asset_id: str, kind: Literal['original.png', 'cutout.png']):
    required(asset_id)
    return FileResponse(ai.DATA / 'assets' / asset_id / kind, media_type='image/png')


def analyze(image, folder, point=None, k=5):
    mask, method, score = ai.segment(image, point)
    palette = extract_palette(np.asarray(image.convert('RGB')), mask, k)
    rgba = np.asarray(image.convert('RGBA')).copy()
    rgba[:, :, 3] = np.where(mask, rgba[:, :, 3], 0)
    Image.fromarray(rgba).save(folder / 'cutout.png')
    return palette, method, round(float(mask.mean()) * 100, 2), score


@app.post('/api/assets', status_code=201)
def upload(file: UploadFile = File(...), k: int = Query(5, ge=3, le=5)):
    raw = file.file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, 'Image exceeds the 20 MB limit.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(raw))
            if image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise HTTPException(415, 'Upload a JPEG, PNG, or WebP image.')
            image.load()
            image = ImageOps.exif_transpose(image).convert('RGBA')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(415, 'Invalid image or image exceeds 25 megapixels.')
    if min(image.size) < 16:
        raise HTTPException(422, 'Image must be at least 16 pixels on each side.')
    # Analysis resolution is capped for predictable laptop memory and CPU usage.
    image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    asset_id = uuid.uuid4().hex
    folder = ai.DATA / 'assets' / asset_id
    folder.mkdir(parents=True)
    try:
        image.save(folder / 'original.png')
        palette, method, coverage, score = analyze(image, folder, k=k)
        vector = ai.embedding(image=image.convert('RGB'))
        name = Path((file.filename or 'Untitled image').replace('\\', '/')).name[:160]
        with store.connection() as conn:
            conn.execute('''INSERT INTO assets (id,name,tags,created,width,height,bytes,palette,method,coverage,sam_score,embedding)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                         (asset_id, name, '[]', datetime.now(timezone.utc).isoformat(), *image.size,
                          len(raw), json.dumps(palette), method, coverage, score,
                          json.dumps(vector) if vector is not None else None))
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return required(asset_id)


COLOR_NAMES = {'red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'purple', 'pink', 'brown', 'black', 'white', 'gray'}


def parse_query(q, color, minimum):
    pattern = r'(?:at\s+least\s+)?(\d+(?:\.\d+)?)\s*%\s*(red|orange|yellow|green|cyan|blue|purple|pink|brown|black|white|gray)\b'
    match = re.search(pattern, q, re.I)
    if match:
        if not color:
            color = match[2].lower()
            minimum = float(match[1])
        q = (q[:match.start()] + q[match.end():]).strip(' +,')
    if minimum > 100:
        raise HTTPException(422, 'Color percentage must be between 0 and 100.')
    return q, color, minimum


@app.get('/api/assets')
def search(q: str = Query('', max_length=500), color: str = '', min_percentage: float = Query(0, ge=0, le=100),
           tolerance: float = Query(25, ge=1, le=80), favorite: bool = False, similar_to: str = '',
           sort: Literal['newest', 'oldest', 'name'] = 'newest'):
    q, color, min_percentage = parse_query(q.strip(), color.strip(), min_percentage)
    if color.startswith('#'):
        try:
            hex_rgb(color)
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    elif color and color not in COLOR_NAMES:
        raise HTTPException(422, 'Choose a supported color family or six-digit hex code.')
    query_vector = None
    mode = 'browse'
    if similar_to:
        query_vector = required(similar_to, True)['embedding']
        if query_vector is None:
            raise HTTPException(409, 'This asset has no CLIP embedding. Install AI models and rebuild the index.')
        mode = 'image similarity'
    elif q:
        query_vector = ai.embedding(text=q)
        mode = 'CLIP semantic' if query_vector is not None else 'keyword fallback'
    with store.connection() as conn:
        rows = conn.execute('SELECT * FROM assets ORDER BY created DESC').fetchall()
    items = []
    unindexed = 0
    for row in rows:
        a = store.serialize(row, True)
        if favorite and not a['favorite'] or a['id'] == similar_to:
            continue
        share = color_share(a['palette'], color, tolerance)
        if color and (share <= 0 or share + .0001 < min_percentage):
            continue
        a['matched_percentage'] = round(share, 2) if color else None
        vector = a.pop('embedding')
        if query_vector is not None:
            if vector is None:
                unindexed += 1
                continue
            a['similarity'] = round(float(np.dot(query_vector, vector)), 4)
        elif q:
            haystack = (a['name'] + ' ' + ' '.join(a['tags'] or [])).lower()
            if not all(word in haystack for word in q.lower().split()):
                continue
        items.append(a)
    if query_vector is not None:
        items.sort(key=lambda a: a['similarity'], reverse=True)
    elif sort == 'name':
        items.sort(key=lambda a: a['name'].lower())
    elif sort == 'oldest':
        items.reverse()
    return {'items': items, 'total': len(items), 'mode': mode, 'unindexed': unindexed,
            'filters': {'query': q, 'color': color, 'min_percentage': min_percentage, 'tolerance': tolerance}}


@app.get('/api/assets/{asset_id}')
def detail(asset_id: str):
    return required(asset_id)


class AssetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=160)
    tags: list[str] | None = Field(None, max_length=30)
    favorite: bool | None = None


@app.patch('/api/assets/{asset_id}')
def update(asset_id: str, body: AssetUpdate):
    with MUTATION_LOCK:
        asset = required(asset_id)
        name = body.name.strip() if body.name is not None else asset['name']
        if not name:
            raise HTTPException(422, 'Name cannot be blank.')
        tags = [tag.strip()[:80] for tag in body.tags if tag.strip()] if body.tags is not None else asset['tags']
        fav = body.favorite if body.favorite is not None else asset['favorite']
        with store.connection() as conn:
            conn.execute('UPDATE assets SET name=?, tags=?, favorite=? WHERE id=?', (name, json.dumps(tags), int(fav), asset_id))
    return required(asset_id)


class SegmentInput(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    k: int = Field(5, ge=3, le=5)


@app.post('/api/assets/{asset_id}/segment')
def refine(asset_id: str, body: SegmentInput):
    with MUTATION_LOCK:
        asset = required(asset_id)
        folder = ai.DATA / 'assets' / asset_id
        with Image.open(folder / 'original.png') as image:
            palette, method, coverage, score = analyze(image, folder, (body.x * (image.width - 1), body.y * (image.height - 1)), body.k)
        with store.connection() as conn:
            conn.execute('UPDATE assets SET palette=?, method=?, coverage=?, sam_score=? WHERE id=?',
                         (json.dumps(palette), method, coverage, score, asset_id))
    return required(asset_id)


@app.delete('/api/assets/{asset_id}', status_code=204)
def delete(asset_id: str):
    with MUTATION_LOCK:
        required(asset_id)
        with store.connection() as conn:
            conn.execute('DELETE FROM assets WHERE id=?', (asset_id,))
        shutil.rmtree(ai.DATA / 'assets' / asset_id, ignore_errors=True)
    return Response(status_code=204)


@app.post('/api/reindex')
def reindex():
    if not ai.status()['clip_ready']:
        raise HTTPException(409, 'CLIP weights unavailable. Run install-ai.cmd, then restart ChromaDAM.')
    count = 0
    with MUTATION_LOCK:
        with store.connection() as conn:
            rows = conn.execute('SELECT id FROM assets WHERE embedding IS NULL').fetchall()
        for row in rows:
            with Image.open(ai.DATA / 'assets' / row['id'] / 'original.png') as image:
                vector = ai.embedding(image=image.convert('RGB'))
            if vector is None:
                raise HTTPException(503, ai.status()['errors'].get('clip', 'CLIP encoding failed.'))
            with store.connection() as conn:
                conn.execute('UPDATE assets SET embedding=? WHERE id=?', (json.dumps(vector), row['id']))
            count += 1
    return {'indexed': count}


@app.get('/api/contrast')
def audit(foreground: str, background: str):
    try:
        return contrast(foreground, background)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get('/api/assets/{asset_id}/export')
def export(asset_id: str, format: Literal['json', 'tailwind', 'css'] = 'json'):
    asset = required(asset_id)
    colors = {f'subject-{i + 1}': p['hex'] for i, p in enumerate(asset['palette'])}
    if format == 'json':
        body = json.dumps({'name': asset['name'], 'colors': colors, 'palette': asset['palette'],
                           'method': asset['method'], 'percentage_basis': 'selected foreground pixels'}, indent=2)
        ext, media_type = 'json', 'application/json'
    elif format == 'tailwind':
        body = '// Tailwind CSS v3 configuration. For v4 use the CSS export.\nmodule.exports = ' + json.dumps({'theme': {'extend': {'colors': colors}}}, indent=2) + ';\n'
        ext, media_type = 'config.cjs', 'text/javascript'
    else:
        body = '/* Tailwind CSS v4 theme tokens */\n@theme {\n' + ''.join(f'  --color-{key}: {value};\n' for key, value in colors.items()) + '}\n'
        ext, media_type = 'css', 'text/css'
    return Response(body, media_type=media_type, headers={'Content-Disposition': f'attachment; filename="chromadam-{asset_id[:8]}.{ext}"'})
