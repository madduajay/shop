"""Durable local graph checkpoints and effect claims; no pickle or live clients."""
import base64
import json
import sqlite3
import threading
from langgraph.checkpoint.memory import InMemorySaver


def encode(value):
    if isinstance(value, bytes):
        return {'bytes': base64.b64encode(value).decode()}
    if isinstance(value, tuple):
        return {'tuple': [encode(v) for v in value]}
    if isinstance(value, dict):
        return {'map': [[encode(k), encode(v)] for k, v in value.items()]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise TypeError('Checkpoint snapshot contains a live object')


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if isinstance(value, dict):
        if 'bytes' in value:
            return base64.b64decode(value['bytes'])
        if 'tuple' in value:
            return tuple(decode(v) for v in value['tuple'])
        return {decode(k): decode(v) for k, v in value['map']}
    return value


class DurableSaver(InMemorySaver):
    """Persist the pinned LangGraph memory saver's typed records transactionally."""

    def __init__(self, path):
        super().__init__()
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS graph_snapshot(id INTEGER PRIMARY KEY, data TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS effect_claims(owner TEXT, request TEXT, signature TEXT, status TEXT, result TEXT, PRIMARY KEY(owner, request, signature))')
        row = self.db.execute('SELECT data FROM graph_snapshot WHERE id=1').fetchone()
        if row:
            storage, writes, blobs = decode(json.loads(row[0]))
            for thread, namespaces in storage.items():
                for ns, checkpoints in namespaces.items():
                    self.storage[thread][ns].update(checkpoints)
            self.writes.update(writes)
            self.blobs.update(blobs)
        self.db.commit()

    def sync(self):
        data = json.dumps(encode([dict(self.storage), dict(self.writes), dict(self.blobs)]))
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO graph_snapshot VALUES(1,?)', (data,))

    def put(self, *args, **kwargs):
        with self.lock:
            result = super().put(*args, **kwargs)
            self.sync()
            return result

    def put_writes(self, *args, **kwargs):
        with self.lock:
            super().put_writes(*args, **kwargs)
            self.sync()

    def delete_thread(self, thread_id):
        with self.lock:
            super().delete_thread(thread_id)
            self.sync()

    def claim(self, owner, request, signature):
        with self.lock, self.db:
            return self.db.execute('INSERT OR IGNORE INTO effect_claims VALUES(?,?,?,\'claimed\',NULL)', (owner, request, signature)).rowcount == 1

    def resolve(self, owner, request, signature, result):
        with self.lock, self.db:
            self.db.execute('UPDATE effect_claims SET status=\'recorded\',result=? WHERE owner=? AND request=? AND signature=?', (json.dumps(result), owner, request, signature))

    def latest_task(self, owner):
        rows = [row for row in self.list(None) if row.config['configurable']['thread_id'].startswith(owner + ':') and row.checkpoint['channel_values'].get('task')]
        if not rows:
            return None
        return max(rows, key=lambda row: row.checkpoint['id']).checkpoint['channel_values']['task']

    def close(self):
        self.db.close()
