"""Budget checks use in-memory HTTP requests; no provider connection or key."""
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from live_model_tests import ModelBudget


def message(url='https://api.openai.com/v1/responses', **changes):
    body = {'model': 'fixture-model', 'store': False, 'max_output_tokens': 250, 'input': 'synthetic'}
    body.update(changes)
    return httpx.Request('POST', url, json=body)


@pytest.mark.parametrize('url', [
    'http://api.openai.com/v1/responses',
    'https://api.openai.com:444/v1/responses',
    'https://api.openai.com.evil.test/v1/responses',
    'https://api.openai.com/v1/files',
    'https://api.openai.com/v1/responses?secret=fixture',
    'https://fixture@api.openai.com/v1/responses',
])
def test_rejects_unapproved_endpoint_before_counting(url):
    budget = ModelBudget(1, 'fixture-model')
    with pytest.raises(RuntimeError, match='endpoints'):
        budget.claim(message(url))
    assert budget.used == 0


@pytest.mark.parametrize('changes', [
    {'model': 'unapproved-model'}, {'store': True}, {'max_output_tokens': 1201},
    {'max_output_tokens': None}, {'stream': True}, {'n': 2},
])
def test_rejects_unapproved_model_retention_or_output(changes):
    with pytest.raises(RuntimeError, match='limits'):
        ModelBudget(1, 'fixture-model').claim(message(**changes))


def test_enforces_input_size_and_failed_attempt_budget():
    budget = ModelBudget(1, 'fixture-model', input_bytes=300)
    with pytest.raises(RuntimeError, match='byte cap'):
        budget.claim(message(input='x' * 301))
    budget.claim(message())  # Count before a transport can fail.
    with pytest.raises(RuntimeError, match='exhausted'):
        budget.claim(message())
    assert budget.used == 1


def test_concurrent_attempts_share_one_whole_session_cap():
    budget = ModelBudget(5, 'fixture-model')
    def attempt(_):
        try:
            budget.claim(message())
            return True
        except RuntimeError:
            return False
    with ThreadPoolExecutor(max_workers=8) as workers:
        assert sum(workers.map(attempt, range(20))) == 5
    assert budget.used == 5


@pytest.mark.parametrize('cap', [0, 51, -1, True])
def test_cap_must_be_explicit_and_bounded(cap):
    with pytest.raises(ValueError):
        ModelBudget(cap, 'fixture-model')


@pytest.mark.parametrize('condition', ['no_key', 'no_cap', 'endpoint_override', 'wrong_model'])
def test_invalid_live_configuration_never_resolves_provider(condition, monkeypatch):
    import conftest
    from types import SimpleNamespace
    from gpt_chat import MODEL
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-not-a-key')
    monkeypatch.setenv('PAP_GPT_MODEL', MODEL)
    for name in ('OPENAI_BASE_URL', 'OPENAI_API_BASE', 'OPENAI_PROXY'):
        monkeypatch.delenv(name, raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError('Invalid configuration must fail before network discovery')
    monkeypatch.setattr(conftest.socket, 'getaddrinfo', forbidden)
    if condition == 'no_key':
        monkeypatch.delenv('OPENAI_API_KEY')
    elif condition == 'endpoint_override':
        monkeypatch.setenv('OPENAI_BASE_URL', 'https://unapproved.example')
    elif condition == 'wrong_model':
        monkeypatch.setenv('PAP_GPT_MODEL', 'unapproved')
    options = {'--thread3-live-model': True, '--thread3-model-max-requests': 0 if condition == 'no_cap' else 5}
    with pytest.raises(pytest.UsageError):
        conftest.pytest_configure(SimpleNamespace(getoption=options.__getitem__))


@pytest.mark.asyncio
async def test_production_deep_model_factory_disables_retention_and_fits_budget(tmp_path, monkeypatch):
    import json
    from app import App, Flow
    from deep_runtime import plan_and_execute
    from graph_fixtures import call, plan, finish
    app = App()
    await app.setup(tmp_path / 'provider.sqlite')
    app.model.key = 'synthetic-not-a-key'
    budget = ModelBudget(5, app.model.model)
    queue = call('queued_additions', {'action': 'show', 'index': 0})
    script = [plan('read pending additions'), queue, queue, finish()]

    async def transport(self, request):
        budget.claim(request)
        choice = script[budget.used - 1]
        return httpx.Response(200, json={'id': 'fixture', 'object': 'chat.completion', 'created': 0,
            'model': app.model.model, 'choices': [{'index': 0, 'finish_reason': 'tool_calls',
            'message': {'role': 'assistant', 'content': None, 'tool_calls': [{'id': f'fixture_{budget.used}',
            'type': 'function', 'function': {'name': choice['name'], 'arguments': json.dumps(choice['args'])}}]}}]})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, 'handle_async_request', transport)
    try:
        flow = Flow(app, 1)
        await plan_and_execute(flow, 'Show pending additions')
        assert budget.used == 4
        assert flow.deep_runner.task['status'] == 'completed'
        assert not app.memory.orders()
    finally:
        await app.close()
