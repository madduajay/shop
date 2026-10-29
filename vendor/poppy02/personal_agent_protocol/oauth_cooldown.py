"""Per-reactor, per-issuer OAuth Retry-After gate; no credentials or persistence.

Reject early with a typed retry delay rather than sleeping or replaying a write.
Serialize sends so callers already queued behind a 429 observe its cooldown.
"""
from __future__ import annotations
import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from weakref import WeakKeyDictionary
import httpx
from .errors import PersonalAgentProtocolError
from .reactor import CLOCKS, first_contribution, parse_retry_after, send_bounded

@dataclass
class _Gate:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    until: datetime | None = None
    users: int = 0

_GATES: WeakKeyDictionary = WeakKeyDictionary()
_LIMIT = 512

async def send_oauth(reactor, http: httpx.AsyncClient, request: httpx.Request, *,
                     issuer: str, error_type: type[PersonalAgentProtocolError], max_bytes: int):
    clock = first_contribution(reactor, CLOCKS, 'clock')
    now = clock.now()
    table = _GATES.setdefault(reactor, {})
    gate = table.get(issuer)
    if gate is None:
        # Never evict an active cooldown or a lock with queued callers.
        for key, old in list(table.items()):
            if old.users == 0 and (old.until is None or old.until <= now):
                del table[key]
        if len(table) >= _LIMIT:
            raise error_type('rate_limited', 'OAuth cooldown capacity reached',
                             status_code=429, details={'retry_after': 1})
        gate = table[issuer] = _Gate()
    gate.users += 1
    try:
        async with gate.lock:
            now = clock.now()
            if gate.until is not None and gate.until > now:
                raise error_type('rate_limited', 'Company requested a pause before another OAuth request',
                                 status_code=429, details={'retry_after': math.ceil((gate.until-now).total_seconds())})
            response = await send_bounded(http, request, max_bytes=max_bytes)
            if response.status_code == 429:
                now = clock.now()
                try:
                    delay = parse_retry_after(response.headers.get('retry-after'), now)
                except (OverflowError, ValueError):
                    delay = float('inf')
                # Missing/malformed values still get conservative pacing; never silently
                # shorten a valid large value to the SDK's normal retry cap.
                delay = 1.0 if delay is None else max(0.0, delay)
                try:
                    until = now + timedelta(seconds=delay)
                except (OverflowError, ValueError):
                    until = datetime.max.replace(tzinfo=timezone.utc)
                gate.until = max(gate.until or now, until)
                raise error_type('rate_limited', 'Company requested a pause before another OAuth request',
                                 status_code=429, details={'retry_after': math.ceil((gate.until-now).total_seconds())})
            return response
    finally:
        gate.users -= 1
