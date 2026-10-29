"""Non-browser transport/reconnect checks; rendered SSE reruns remain separate."""
import time
from types import SimpleNamespace
import pytest
from app import App, Flow
from availability_webhook import AvailabilityWebhook, EXT


async def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(AvailabilityWebhook, 'start', lambda self: None)
    app = App()
    await app.setup(tmp_path / 'sse.sqlite')
    flow = Flow(app, 1)
    return app, flow


@pytest.mark.asyncio
@pytest.mark.parametrize('delivery', [None, 'legacy_sse', EXT])
async def test_only_legacy_sse_watch_requests_restart_authorization(tmp_path, monkeypatch, delivery):
    app, flow = await fixture(tmp_path, monkeypatch)
    effects = []
    watch = {'consent': 'a' * 32, 'status': 'active', 'expires_at': time.time() + 600}
    if delivery:
        watch['delivery'] = delivery
    app.watch_memory.save(1, watch)

    async def open_browser():
        effects.append('open')
        flow.token = SimpleNamespace(signed_in=False, scopes=())

    async def signin():
        effects.append('signin')
        flow.signurl = 'synthetic-local-authorization'

    flow.open = open_browser
    flow.signin = signin
    try:
        answer = await flow.poll_watches()
        if delivery == EXT:
            assert answer is None and effects == [] and flow.signurl is None
        else:
            assert 'Reconnect FORME' in answer
            assert flow.pending_read == 'watch_reconnect' and effects == ['open', 'signin']
        assert app.watch_memory.rows(2) == []
    finally:
        await app.close()


@pytest.mark.asyncio
async def test_existing_sse_token_without_scope_requests_reconnect(tmp_path, monkeypatch):
    app, flow = await fixture(tmp_path, monkeypatch)
    app.watch_memory.save(1, {'consent': 'b' * 32, 'status': 'active', 'expires_at': time.time() + 600, 'reconnect_required': True})
    flow.token = SimpleNamespace(signed_in=True, scopes=('orders:read',))
    calls = []

    async def signin():
        calls.append('signin')

    flow.signin = signin
    try:
        answer = await flow.poll_watches()
        assert 'Reconnect FORME' in answer and calls == ['signin']
        assert flow.pending_read == 'watch_reconnect'
        assert not app.watch_memory.rows(1)[0].get('reconnect_required')
    finally:
        await app.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('webhook_enabled', [False, True])
async def test_watch_transport_selection_controls_callback_registration(tmp_path, monkeypatch, webhook_enabled):
    app, flow = await fixture(tmp_path, monkeypatch)
    app.webhook_enabled = webhook_enabled
    flow.token = SimpleNamespace()
    flow.who = {}
    flow.conversation_endpoint = app.shop.config.conversations_endpoint
    watch = {'consent': 'c' * 32, 'status': 'consented', 'filters': {}}
    app.watch_memory.save(1, watch)
    introductions = []

    async def start(endpoint, message, **kwargs):
        introductions.append(message)
        return SimpleNamespace(conversation_id='synthetic_conversation')

    async def send(*args, **kwargs):
        return SimpleNamespace(conversation_id='synthetic_conversation', events=[SimpleNamespace(message=SimpleNamespace(role='company', data={'forme_availability': {'action': 'subscribed', 'watch': {'id': 'synthetic_watch'}}}))])

    flow.conversation_client = lambda: SimpleNamespace(start=start, send=send)
    try:
        result = await flow.watch_message(watch)
        assert result['id'] == 'synthetic_watch'
        if webhook_enabled:
            assert watch['delivery'] == EXT
            assert introductions[0].data['thread_webhook']['url'] == app.webhook.url
        else:
            assert 'delivery' not in watch
            assert introductions[0].data is None
    finally:
        await app.close()
