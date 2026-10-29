import json
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from spend_budget import SpendBudget, MODEL, CONTEXT, INPUT_NANO, OUTPUT_NANO


def request(**changes):
    body = {'model': MODEL, 'store': False, 'max_tokens': 1200, 'messages': [{'role': 'user', 'content': 'synthetic'}]}
    body.update(changes)
    return httpx.Request('POST', 'https://api.openai.com/v1/chat/completions', json=body)


def response(incoming=1000, cached=500, outgoing=100):
    return httpx.Response(200, json={'model': MODEL, 'usage': {'prompt_tokens': incoming,
        'completion_tokens': outgoing, 'prompt_tokens_details': {'cached_tokens': cached}}})


def test_success_uses_provider_usage_cached_discount_and_shared_restart(tmp_path):
    path = tmp_path / 'budget.sqlite'
    budget = SpendBudget(path)
    attempt = budget.reserve(request())
    assert budget.summary()['total_committed_usd'] > .4
    budget.settle(attempt, response())
    assert budget.summary()['priced_measured_usage_usd'] == .00041
    assert SpendBudget(path).summary() == budget.summary()
    with pytest.raises(RuntimeError, match='already settled'):
        budget.settle(attempt, response())


def test_unknown_usage_or_transport_failure_never_releases_reservation(tmp_path):
    budget = SpendBudget(tmp_path / 'budget.sqlite')
    identity = budget.reserve(request())
    budget.settle(identity, httpx.Response(502, json={'error': 'synthetic'}))
    summary = budget.summary()
    assert summary['priced_measured_usage_usd'] == 0
    assert summary['unknown_or_outstanding_reserved_usd'] > .4
    assert summary['attempts'] == 1


def test_parallel_workers_cannot_reserve_over_total_50_dollars(tmp_path):
    path = tmp_path / 'budget.sqlite'
    SpendBudget(path)
    def attempt(_):
        try:
            SpendBudget(path).reserve(request())
            return True
        except RuntimeError:
            return False
    with ThreadPoolExecutor(max_workers=12) as workers:
        admitted = sum(workers.map(attempt, range(140)))
    summary = SpendBudget(path).summary()
    reserve = CONTEXT * INPUT_NANO + 1200 * OUTPUT_NANO
    assert admitted == 50_000_000_000 // reserve
    assert summary['total_committed_usd'] <= 50
    assert summary['remaining_usd'] < reserve / 1e9


@pytest.mark.parametrize('changes', [
    {'model': 'unapproved-model'}, {'store': True}, {'max_tokens': 4097},
    {'n': 2}, {'stream': True}, {'tools': [{'type': 'web_search'}]},
    {'messages': [{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': 'fixture'}}]}]},
])
def test_unpriced_or_unbounded_request_rejected_before_reservation(tmp_path, changes):
    budget = SpendBudget(tmp_path / 'budget.sqlite')
    with pytest.raises(RuntimeError):
        budget.reserve(request(**changes))
    assert budget.summary()['attempts'] == 0


def test_actual_key_cannot_be_sent_to_other_host_or_redirected(tmp_path, monkeypatch):
    import httpx
    from spend_budget import install
    original = httpx.Client.send
    async_original = httpx.AsyncClient.send
    try:
        budget = install('fixture-only-not-a-real-key', tmp_path / 'budget.sqlite')
        with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(307, headers={'Location': 'https://unapproved.invalid'}))) as client:
            with pytest.raises(RuntimeError, match='endpoints'):
                client.post('https://unapproved.invalid', headers={'Authorization': 'Bearer fixture-only-not-a-real-key'}, json={})
            r = request()
            r.headers['Authorization'] = 'Bearer fixture-only-not-a-real-key'
            assert client.send(r, follow_redirects=True).status_code == 307
        assert budget.summary()['attempts'] == 1
    finally:
        httpx.Client.send = original
        httpx.AsyncClient.send = async_original
