"""Bounded, backend-only RFC 9449 nonce memory per HTTP client and security context.

Authorization-server and resource-server nonce spaces are separate, even when
both roles share an origin. Never log values or send them to another origin.
"""
from __future__ import annotations

from collections import OrderedDict
from urllib.parse import urlsplit
from weakref import WeakKeyDictionary
import httpx

_CACHE: WeakKeyDictionary = WeakKeyDictionary()
_LIMIT = 512


def nonce_key(role: str, url: str, tenant: str, subject: str, issuer: str) -> tuple:
    parsed = urlsplit(url)
    return (role, parsed.scheme.lower(), parsed.hostname, parsed.port or 443, tenant, subject, issuer)


def get_nonce(http: httpx.AsyncClient, key: tuple) -> str | None:
    table = _CACHE.get(http)
    if table is None:
        return None
    value = table.get(key)
    if value is not None:
        table.move_to_end(key)
    return value


def remember_nonce(http: httpx.AsyncClient, key: tuple, response: httpx.Response) -> str | None:
    values = response.headers.get_list('dpop-nonce')
    if len(values) != 1:
        return None
    value = values[0]
    # RFC 9449 nonce syntax uses visible ASCII except double quote and backslash.
    if not value or len(value) > 4096 or any(ord(c) < 33 or ord(c) > 126 or c in '\\"' for c in value):
        return None
    table = _CACHE.setdefault(http, OrderedDict())
    table[key] = value
    table.move_to_end(key)
    while len(table) > _LIMIT:
        table.popitem(last=False)
    return value
