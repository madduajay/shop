"""Copied baseline tests run only in isolated fixtures, without external requests."""
import os
import socket
import inspect
import sys
import hmac
import pytest

os.environ['THREAD3_PORT'] = '8545'
if '--thread3-live-model' not in sys.argv:
    os.environ.pop('OPENAI_API_KEY', None)
os.environ['LANGSMITH_TRACING'] = 'false'


def pytest_addoption(parser):
    parser.addoption('--thread3-live-sockets', action='store_true', default=False,
                     help='Run isolated loopback socket checks in an authorized execution context; Chrome remains blocked')
    parser.addoption('--thread3-live-browser', action='store_true', default=False,
                     help='Run Chrome with an explicitly approved, validated temporary Thread3 TLS fixture')
    parser.addoption('--thread3-live-model', action='store_true', default=False,
                     help='Use an explicitly authorized process-only OpenAI key; requires a request cap')
    parser.addoption('--thread3-model-max-requests', type=int, default=0,
                     help='Explicit whole-session cap, 1..50; failed requests count')


def pytest_configure(config):
    config.thread3_model_budget = None
    config.thread3_model_addresses = set()
    if not config.getoption('--thread3-live-model'):
        return
    from live_model_tests import ModelBudget
    from gpt_chat import MODEL
    if not os.environ.get('OPENAI_API_KEY'):
        raise pytest.UsageError('Live-model tests require a key supplied securely to this process')
    if any(os.environ.get(k) for k in ('OPENAI_BASE_URL', 'OPENAI_API_BASE', 'OPENAI_PROXY')):
        raise pytest.UsageError('Live-model tests cannot use endpoint or proxy overrides')
    if os.environ.get('PAP_GPT_MODEL', MODEL) != MODEL:
        raise pytest.UsageError('Live-model tests require the documented default model')
    try:
        import httpx
        ledger = os.environ.get('THREAD3_SPEND_LEDGER')
        guarded = bool(ledger and getattr(httpx.AsyncClient.send, '_thread3_spend_ledger', None) == ledger)
        config.thread3_model_budget = ModelBudget(config.getoption('--thread3-model-max-requests'), MODEL,
            output_tokens=3000, input_bytes=1048576 if guarded else 131072,
            max_requests=1000 if guarded else 50)
    except ValueError as error:
        raise pytest.UsageError(str(error)) from error
    authorization = 'Bearer ' + os.environ['OPENAI_API_KEY']
    config.thread3_actual_model_request = lambda request: hmac.compare_digest(request.headers.get('authorization', ''), authorization)
    config.thread3_model_addresses = {r[4][0] for r in socket.getaddrinfo('api.openai.com', 443, type=socket.SOCK_STREAM)}


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    budget = getattr(config, 'thread3_model_budget', None)
    if budget is not None:
        terminalreporter.write_line(f'Live-model attempted requests: {budget.used}/{budget.limit}; max {budget.output_tokens} output tokens and {budget.input_bytes} request bytes each')


def pytest_collection_modifyitems(items):
    for item in items:
        source = inspect.getsource(item.obj)
        if 'uvicorn.Server' in source and not item.config.getoption('--thread3-live-sockets'):
            item.add_marker(pytest.mark.skip(reason='BLOCKED: sandbox denies local socket bind; Thread3 browser TLS trust also pending'))


@pytest.fixture(autouse=True)
def isolate_network(monkeypatch, request):
    from browser import Browser

    async def pending_tls(*args, **kwargs):
        pytest.skip('BLOCKED: rendered Chrome flow needs specifically approved Thread3 TLS trust; original credentials are prohibited')

    if request.config.getoption('--thread3-live-browser'):
        if not request.config.getoption('--thread3-live-sockets') or not os.getenv('THREAD3_TLS_DIR'):
            raise RuntimeError('Live Chrome needs the approved socket mode and dedicated Thread3 TLS fixture')
        from tls_fixture import validate
        validate(os.environ['THREAD3_TLS_DIR'])
    else:
        monkeypatch.setattr(Browser, 'launch', pending_tls)
    original = socket.socket.connect
    budget = request.config.thread3_model_budget
    if budget is not None:
        import httpx
        original_send = httpx.AsyncClient.send
        original_sync_send = httpx.Client.send

        async def send(client, message, **kwargs):
            if message.url.host == 'api.openai.com' and request.config.thread3_actual_model_request(message):
                budget.claim(message)
            return await original_send(client, message, **kwargs)

        def sync_send(client, message, **kwargs):
            if message.url.host == 'api.openai.com' and request.config.thread3_actual_model_request(message):
                budget.claim(message)
            return original_sync_send(client, message, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, 'send', send)
        monkeypatch.setattr(httpx.Client, 'send', sync_send)

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1'):
            if not (budget is not None and len(address) >= 2 and address[1] == 443 and address[0] in request.config.thread3_model_addresses):
                raise RuntimeError('External network disabled for Thread3 fixture tests')
        return original(sock, address)

    monkeypatch.setattr(socket.socket, 'connect', connect)
