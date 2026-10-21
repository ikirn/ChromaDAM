import json
import sqlite3
from contextlib import contextmanager
from .ai import DATA


@contextmanager
def connection():
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATA / 'library.sqlite3', timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    with connection() as conn:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('''CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, tags TEXT NOT NULL, created TEXT NOT NULL,
            width INTEGER, height INTEGER, bytes INTEGER, palette TEXT, method TEXT,
            coverage REAL, sam_score REAL, embedding TEXT, favorite INTEGER DEFAULT 0)''')


def serialize(row, private=False):
    item = dict(row)
    for key in ('tags', 'palette', 'embedding'):
        item[key] = json.loads(item[key]) if item[key] else None
    item['favorite'] = bool(item['favorite'])
    item['image_url'] = f"/media/{item['id']}/original.png"
    item['cutout_url'] = f"/media/{item['id']}/cutout.png"
    if not private:
        item.pop('embedding', None)
    return item


def get(asset_id, private=False):
    with connection() as conn:
        row = conn.execute('SELECT * FROM assets WHERE id=?', (asset_id,)).fetchone()
    return serialize(row, private) if row else None
