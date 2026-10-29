"""One cross-process USD gate; stores only token/cost metadata, never keys/prompts.

Pricing verified 2026-10-24 at https://developers.openai.com/api/docs/models/gpt-4.1-mini
Reserve the ENTIRE documented context window before every HTTP attempt, including
retries. Unknown usage keeps that reservation. Only measured usage releases it.
"""
import contextvars
from contextlib import contextmanager
import datetime
import hmac
import json
from pathlib import Path
import secrets
import sqlite3

MODEL = 'gpt-4.1-mini-2025-04-14'
CONTEXT = 1047576
INPUT_NANO = 400  # $0.40 / million tokens
CACHED_NANO = 100
OUTPUT_NANO = 1600
LIMIT_NANO = 50_000_000_000
LABEL = contextvars.ContextVar('thread3_budget_case', default='local-live-demo')


class SpendBudget:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS budget(limit_nano INTEGER NOT NULL)')
            db.execute('INSERT INTO budget SELECT ? WHERE NOT EXISTS(SELECT 1 FROM budget)', (LIMIT_NANO,))
            if db.execute('SELECT limit_nano FROM budget').fetchone()[0] != LIMIT_NANO:
                raise RuntimeError('Unexpected test spending limit')
            db.execute('''CREATE TABLE IF NOT EXISTS attempts(
                id TEXT PRIMARY KEY, label TEXT, created TEXT, status TEXT,
                reservation INTEGER, charged INTEGER, input_tokens INTEGER,
                cached_tokens INTEGER, output_tokens INTEGER, http_status INTEGER)''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.execute('PRAGMA busy_timeout=30000')
        try:
            yield db
        finally:
            db.close()

    def reserve(self, request):
        u = request.url
        if (request.method != 'POST' or u.scheme != 'https' or u.host != 'api.openai.com' or
                u.port not in (None, 443) or u.username or u.password or u.query or
                u.path not in ('/v1/responses', '/v1/chat/completions')):
            raise RuntimeError('Model request outside approved OpenAI endpoints')
        body = json.loads(request.content)
        fields = [body[k] for k in ('max_tokens', 'max_completion_tokens', 'max_output_tokens') if k in body]
        if (body.get('model') != MODEL or body.get('store') is not False or
                body.get('stream') or len(fields) != 1 or type(fields[0]) is not int or
                not 1 <= fields[0] <= 4096 or body.get('n', 1) != 1 or
                any(t.get('type') != 'function' for t in body.get('tools', []))):
            raise RuntimeError('Unbounded model, retention, output, or paid tool rejected')
        # The context limit also bounds text input cost. Images/audio are excluded.
        def text_only(value):
            if isinstance(value, dict):
                if value.get('type') in {'image_url', 'input_image', 'input_audio', 'audio', 'file', 'input_file'}:
                    return False
                return all(text_only(v) for v in value.values())
            return all(text_only(v) for v in value) if isinstance(value, list) else True
        if not text_only(body):
            raise RuntimeError('Only text/function model requests have authorized pricing')
        reservation = CONTEXT * INPUT_NANO + fields[0] * OUTPUT_NANO
        identity = secrets.token_hex(16)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            total = db.execute('SELECT coalesce(sum(charged),0) FROM attempts').fetchone()[0]
            if total + reservation > LIMIT_NANO:
                db.rollback()
                raise RuntimeError('Shared $50 test budget exhausted; no request sent')
            db.execute('INSERT INTO attempts VALUES(?,?,?,?,?,?,?,?,?,?)',
                (identity, LABEL.get(), datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'reserved_or_unknown', reservation, reservation, None, None, None, None))
            db.commit()
        return identity

    def settle(self, identity, response):
        try:
            body = response.json()
            usage = body['usage']
            incoming = usage.get('input_tokens', usage.get('prompt_tokens'))
            outgoing = usage.get('output_tokens', usage.get('completion_tokens'))
            details = usage.get('input_tokens_details', usage.get('prompt_tokens_details', {})) or {}
            cached = details.get('cached_tokens', 0)
            if (body.get('model') != MODEL or any(type(v) is not int for v in (incoming, outgoing, cached)) or
                    not 0 <= cached <= incoming <= CONTEXT or outgoing < 0):
                raise ValueError('Invalid usage')
            charged = (incoming - cached) * INPUT_NANO + cached * CACHED_NANO + outgoing * OUTPUT_NANO
        except (ValueError, KeyError, TypeError):
            return  # Keep worst-case reservation; never assume a failed call was free.
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT reservation,status FROM attempts WHERE id=?', (identity,)).fetchone()
            if row is None or row[1] != 'reserved_or_unknown':
                raise RuntimeError('Unknown or already settled attempt')
            if charged > row[0]:
                db.rollback()
                raise RuntimeError('Provider usage exceeded reserved maximum; stop testing')
            db.execute('UPDATE attempts SET status=?,charged=?,input_tokens=?,cached_tokens=?,output_tokens=?,http_status=? WHERE id=?',
                ('measured', charged, incoming, cached, outgoing, response.status_code, identity))
            db.commit()

    def summary(self):
        with self.db() as db:
            total, measured, unknown, calls = db.execute('''SELECT coalesce(sum(charged),0),
                coalesce(sum(CASE WHEN status='measured' THEN charged ELSE 0 END),0),
                coalesce(sum(CASE WHEN status!='measured' THEN charged ELSE 0 END),0),count(*) FROM attempts''').fetchone()
            tokens = db.execute('SELECT coalesce(sum(input_tokens),0),coalesce(sum(cached_tokens),0),coalesce(sum(output_tokens),0) FROM attempts').fetchone()
        return {'limit_usd': 50, 'priced_measured_usage_usd': measured / 1e9,
                'unknown_or_outstanding_reserved_usd': unknown / 1e9,
                'total_committed_usd': total / 1e9, 'remaining_usd': (LIMIT_NANO-total) / 1e9,
                'attempts': calls, 'input_tokens': tokens[0], 'cached_tokens': tokens[1],
                'output_tokens': tokens[2], 'actual_billed_cost': 'not available; usage-priced estimate only',
                'pricing_source': 'https://developers.openai.com/api/docs/models/gpt-4.1-mini'}


def install(key, path):
    """Wrap every real-key HTTPX attempt in this process; all workers share SQLite."""
    import httpx
    budget = SpendBudget(path)
    authorization = 'Bearer ' + key
    original = httpx.AsyncClient.send
    sync_original = httpx.Client.send

    def actual(request):
        return hmac.compare_digest(request.headers.get('authorization', ''), authorization)

    async def send(client, request, **kwargs):
        if not actual(request):
            return await original(client, request, **kwargs)  # Synthetic MockTransports use fixture keys.
        identity = budget.reserve(request)
        kwargs.update(follow_redirects=False, auth=None)
        response = await original(client, request, **kwargs)
        await response.aread()
        budget.settle(identity, response)
        return response

    def sync_send(client, request, **kwargs):
        if not actual(request):
            return sync_original(client, request, **kwargs)
        identity = budget.reserve(request)
        kwargs.update(follow_redirects=False, auth=None)
        response = sync_original(client, request, **kwargs)
        response.read()
        budget.settle(identity, response)
        return response

    httpx.AsyncClient.send = send
    httpx.Client.send = sync_send
    send._thread3_spend_ledger = budget.path
    return budget
