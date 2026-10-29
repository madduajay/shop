"""Authenticated HTTP UI entrypoint through real Deep Agents and provider parsing."""
import json
import re
import httpx
import pytest
from langchain_openai import ChatOpenAI
from app import App, AGENT
from graph_fixtures import call, plan, finish
from test_thread_auth import login


@pytest.mark.asyncio
async def test_authenticated_api_deepagents_provider_adapter(tmp_path):
    app = App()
    await app.setup(tmp_path / 'api.sqlite')
    app.model.key = 'fixture-only'
    queue = call('queued_additions', {'action': 'show', 'index': 0})
    script = [plan('read pending additions'), queue, queue, finish()]
    requests = []

    def respond(request):
        data = json.loads(request.content)
        requests.append(data)
        choice = script[len(requests) - 1]
        return httpx.Response(200, json={'id': 'fixture-completion', 'object': 'chat.completion', 'created': 0, 'model': 'gpt-4.1-mini', 'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'fixture_' + str(len(requests)), 'type': 'function', 'function': {'name': choice['name'], 'arguments': json.dumps(choice['args'])}}]}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond), trust_env=False) as provider:
        app.deep_model = ChatOpenAI(model='gpt-4.1-mini', api_key='fixture-only', http_async_client=provider, max_retries=0)
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=AGENT) as ui:
                headers = await login(ui)
                result = await ui.post('/api/chat', headers=headers, json={'text': 'Show pending additions'})
                assert result.status_code == 200 and result.json()['reply'] == 'No items are waiting to be added.'
                assert len(requests) == 4
                assert [tool['function']['name'] for tool in requests[0]['tools']] == ['plan_request']
                assert 'finish_request' not in {tool['function']['name'] for tool in requests[1]['tools']}
                assert 'finish_request' in {tool['function']['name'] for tool in requests[-1]['tools']}
                assert all(data.get('parallel_tool_calls') is False for data in requests)
                trace = (await ui.post('/api/trace', headers=headers, json={})).json()
                assert 'Deep Agents business tool' in json.dumps(trace)
                before = app.deep_model
                forged = await ui.post('/api/chat', headers=headers, json={'text': 'Show pending additions', 'customer': 2})
                assert forged.status_code == 403 and len(requests) == 4
                assert not app.memory.orders()
        finally:
            await app.http.aclose()
            app.graph_saver.close()
