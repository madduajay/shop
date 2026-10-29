"""Actual GPT/Deep Agents behind authenticated API, without browser trust."""
import json
import os
import re
from pathlib import Path
import httpx
import pytest
from app import App, AGENT
from test_thread_auth import login
from spend_budget import SpendBudget, LABEL


@pytest.mark.asyncio
async def test_actual_graph_authenticated_api_archive_and_restart(tmp_path):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('Actual GPT with authorized shared spending gate required')
    database = tmp_path / 'api-live.sqlite'
    app = App()
    await app.setup(database)
    profiles = [app.memory.get(i) for i in range(1, 101)]
    gate = SpendBudget(os.environ['THREAD3_SPEND_LEDGER'])

    def calls():
        with gate.db() as db:
            return db.execute('SELECT count(*) FROM attempts WHERE label=?', (LABEL.get(),)).fetchone()[0]

    headers = None
    saved_cookies = None
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=AGENT) as one, \
                   httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=AGENT) as two:
            headers = await login(one, 1)
            other_headers = await login(two, 2)
            response = await one.post('/api/chat', headers=headers, json={'text': 'Show pending additions'})
            assert response.status_code == 200 and 'No items are waiting' in response.json()['reply']
            flow = next(f for group in app.clients.values() for f in group.values() if f.customer == 1)
            assert flow.deep_runner.model.__class__.__name__ == 'ChatOpenAI'
            assert flow.agent_task['status'] == 'completed'
            model_calls = calls()
            assert model_calls >= 3
            forged = await one.post('/api/chat', headers=headers, json={'text': 'Show pending additions', 'customer': 2})
            assert forged.status_code == 403 and calls() == model_calls
            assert (await two.post('/api/state', headers=other_headers, json={})).json()['messages'] == []
            trace = (await one.post('/api/trace', headers=headers, json={})).json()
            assert os.environ['OPENAI_API_KEY'] not in json.dumps(trace)
            cleared = await one.post('/api/clear', headers=headers, json={'confirm': True})
            assert cleared.status_code == 200
            archive = cleared.json()['archive']
            history = await one.post('/api/archives', headers=headers, json={'id': archive})
            assert history.status_code == 200 and 'No items are waiting' in json.dumps(history.json())
            assert calls() == model_calls, 'Reading or clearing archives must never replay model/tool actions'
            saved_cookies = one.cookies
            assert [app.memory.get(i) for i in range(1, 101)] == profiles
            assert not app.memory.orders()
    finally:
        await app.close()

    reopened = App()
    await reopened.setup(database)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=reopened), base_url=AGENT, cookies=saved_cookies) as client:
            state = await client.post('/api/state', headers=headers, json={})
            assert state.status_code == 200 and state.json()['customer'] == 1 and state.json()['messages'] == []
            history = await client.post('/api/archives', headers=headers, json={'id': archive})
            assert history.status_code == 200 and calls() == model_calls
            assert [reopened.memory.get(i) for i in range(1, 101)] == profiles
            assert not reopened.memory.orders()
        Path('audit/real-graph-api-recovery.json').write_text(json.dumps({
            'real_GPT_graph': True, 'authenticated_API': True, 'forged_identity_rejected': True,
            'separate_customer_isolated': True, 'archive_readonly_no_replay': True,
            'session_and_archive_survive_restart': True, 'all_profiles_preserved': True,
            'no_orders': True, 'model_requests': model_calls}, indent=2))
    finally:
        await reopened.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('scenario', ['read_preferences', 'hypothetical_write', 'watch_status'])
async def test_actual_model_readonly_and_consent_guards(tmp_path, scenario):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('Actual GPT with authorized shared spending gate required')
    from app import Flow
    app = App()
    await app.setup(tmp_path / (scenario + '.sqlite'))
    flow = Flow(app, 1)
    before = [app.memory.get(i) for i in range(1, 101)]
    queries = {
        'read_preferences': 'What is my saved Thread shirt size? Only read it; do not change it.',
        'hypothetical_write': 'Would changing my Thread shirt size to XL overwrite my current preference? Do not change it.',
        'watch_status': 'How many active availability alerts do I have?',
    }
    observed = []
    actual_structured = app.model.structured

    async def observe(instructions, payload, *args, **kwargs):
        observed.extend(fact for row in payload.get('tool_results', []) for fact in row.get('facts', []))
        return await actual_structured(instructions, payload, *args, **kwargs)

    app.model.structured = observe
    try:
        reply, cards = await flow.chat(queries[scenario])
        assert flow.deep_runner.model.__class__.__name__ == 'ChatOpenAI'
        exchanges = [e for e in flow.trace if e.get('kind') == 'model' and 'Deep Agents' in e.get('provenance', '')]
        assert exchanges and all(e.get('status') == 200 for e in exchanges)
        assert reply and not cards and not flow.signurl
        assert [app.memory.get(i) for i in range(1, 101)] == before
        assert not app.memory.orders() and not flow.watch_rows()
        assert not app.store.availability.db.execute('select data from watches').fetchall()
        assert not any(r['tool'] in {'update_preferences', 'confirm_checkout', 'add_to_bag'} for r in flow.agent_task['results'])
        if scenario == 'read_preferences':
            size = str(before[0]['shirt_size'])
            aliases = {'XS': 'extra small', 'S': 'small', 'M': 'medium', 'L': 'large', 'XL': 'extra large', 'XXL': 'extra extra large'}
            assert re.search(r'\b(?:' + re.escape(size) + '|' + re.escape(aliases.get(size, size)) + r')\b', reply, re.I)
            assert any(f['source'] == 'Thread' and f['key'] == 'preferences' and
                f['value'].get('shirt_size') == before[0]['shirt_size'] for f in observed)
            assert flow.agent_task['status'] == 'completed'
        if scenario == 'watch_status':
            assert '0 active' in reply
            assert flow.agent_task['status'] == 'completed'
        Path('audit/real-readonly-' + scenario + '.json').write_text(json.dumps({
            'scenario': scenario, 'reply': reply, 'status': flow.agent_task['status'],
            'tools': [r['tool'] for r in flow.agent_task['results']],
            'real_graph_exchanges': len(exchanges), 'all_profiles_unchanged': True,
            'no_orders_or_watches': True, 'no_authentication_requested': True}, indent=2))
    finally:
        await app.close()
