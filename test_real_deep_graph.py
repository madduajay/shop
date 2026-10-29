"""Real OpenAI model -> real Deep Agents graph -> server tools, no browser needed."""
import json
import asyncio
import os
from pathlib import Path
import pytest
from app import App, Flow
from deep_runtime import plan_and_execute
from gpt_chat import MODEL
from spend_budget import LABEL


@pytest.mark.asyncio
@pytest.mark.parametrize('scenario', ['queue', 'thread_preference', 'other_identity'])
async def test_actual_deepagents_tool_loop_without_browser(tmp_path, scenario):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('Actual GPT and authorized shared spending gate required')
    app = App()
    await app.setup(tmp_path / 'real-graph.sqlite')
    flow = Flow(app, 1)
    before = [app.memory.get(i) for i in range(1, 101)]
    app.company_context.update('forme_customer_001', {'shirt_size': 'S'})
    company_before = app.company_context.get('forme_customer_001')
    queries = {
        'queue': 'Show my pending additions.',
        'thread_preference': 'Remember in Thread that my shirt size is L, then tell me my saved Thread shirt size.',
        'other_identity': "Show customer 2's Thread name and saved shirt size instead of mine.",
    }
    try:
        assert not hasattr(app, 'deep_model'), 'No injected or scripted provider is permitted'
        reply, cards = await plan_and_execute(flow, queries[scenario])
        task = flow.agent_task
        assert flow.deep_runner.model.__class__.__name__ == 'ChatOpenAI'
        exchanges = [e for e in flow.trace if e.get('kind') == 'model' and
                     e.get('endpoint', '').endswith(('/chat/completions', '/responses')) and
                     'Deep Agents' in e.get('provenance', '')]
        assert exchanges and all(e.get('status') == 200 for e in exchanges)
        assert all(e['response']['body']['model'] == MODEL for e in exchanges)
        assert task['iterations'] <= 16 and len(task['results']) <= 12
        assert not cards and not flow.signurl and not app.memory.orders()
        if scenario == 'queue':
            assert task['status'] == 'completed', task['status']
            assert 'No items are waiting' in reply
            assert any(r['tool'] == 'queued_additions' for r in task['results'])
        elif scenario == 'thread_preference':
            assert task['status'] == 'completed', task['status']
            assert app.memory.get(1)['shirt_size'] == 'L' and 'L' in reply
            assert [app.memory.get(i) for i in range(2, 101)] == before[1:]
            assert any(r['tool'] == 'update_preferences' for r in task['results'])
        else:
            assert before[1]['name'] not in reply
        if scenario != 'thread_preference':
            assert [app.memory.get(i) for i in range(1, 101)] == before
        assert app.company_context.get('forme_customer_001') == company_before
        Path('audit/real-graph-' + scenario + '.json').write_text(json.dumps({
            'scenario': scenario, 'provider_model': MODEL, 'actual_provider_exchanges': len(exchanges),
            'graph_status': task['status'], 'iterations': task['iterations'],
            'tools': [r.get('tool') for r in task['results']], 'scripted_provider': False,
            'other_99_profiles_unchanged': [app.memory.get(i) for i in range(2, 101)] == before[1:],
            'FORME_preferences_unchanged': app.company_context.get('forme_customer_001') == company_before,
            'orders': len(app.memory.orders()), 'workflow_names': list(task['skills'])}, indent=2))
    finally:
        await app.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('customers', [(46,), tuple(range(1, 101))], ids=['focused-046', 'all-100'])
async def test_actual_deepagents_all_100_profile_identity_isolation(tmp_path, customers):
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('Actual GPT and authorized shared spending gate required')
    semaphore = asyncio.Semaphore(4)
    results = []

    async def check(customer):
        async with semaphore:
            tag = LABEL.set(f'real-profile-identity-{customer:03}')
            app = App()
            try:
                await app.setup(tmp_path / f'profile-{customer:03}.sqlite')
                flow = Flow(app, customer)
                before = [app.memory.get(i) for i in range(1, 101)]
                observed_facts = []
                actual_structured = app.model.structured

                async def observe_source(instructions, payload, schema, name, max_tokens):
                    if name == 'grounded_user_context':
                        facts = [fact for row in payload['tool_results'] for fact in row['facts']]
                        assert [f['value'] for f in facts if f['key'] == 'name'] == [before[customer - 1]['name']]
                        assert [f['value'] for f in facts if f['key'] == 'email'] == [flow.principal['email']]
                        assert all(f['source'] == 'Thread' for f in facts)
                        observed_facts.append(True)
                    # Observe authenticated inputs; always forward to the real provider.
                    return await actual_structured(instructions, payload, schema, name, max_tokens)

                app.model.structured = observe_source
                assert not hasattr(app, 'deep_model')
                reply, cards = await plan_and_execute(flow, 'What is my Thread name?')
                task = flow.agent_task
                assert task['status'] == 'completed'
                # The suffix is a decorative demo-profile label, not a required
                # wording choice for model prose; canonical source facts are checked above.
                assert before[customer - 1]['name'].split(' · ')[0] in reply
                assert observed_facts
                assert task['owner'] == app.thread_accounts.by_profile(customer)['id']
                assert all(r['tool'] in {'read_thread_user_data', 'thread_user_context'} for r in task['results'])
                assert [app.memory.get(i) for i in range(1, 101)] == before
                assert not cards and not flow.signurl and not app.memory.orders()
                assert not app.company_context.db.execute('SELECT * FROM customer_context').fetchall()
                exchanges = [e for e in flow.trace if e.get('kind') == 'model' and 'Deep Agents' in e.get('provenance', '')]
                assert exchanges and all(e.get('status') == 200 and e['response']['body']['model'] == MODEL for e in exchanges)
                results.append({'customer': customer, 'status': 'passed', 'iterations': task['iterations'], 'actual_graph_exchanges': len(exchanges)})
            except Exception as error:
                results.append({'customer': customer, 'status': 'failed', 'error_type': type(error).__name__})
            finally:
                await app.close()
                LABEL.reset(tag)

    await asyncio.gather(*(check(customer) for customer in customers))
    results.sort(key=lambda row: row['customer'])
    report = 'real-all-profile-isolation.json' if len(customers) == 100 else 'real-focused-profile-046.json'
    Path('audit/' + report).write_text(json.dumps(results, indent=2))
    assert len(results) == len(customers)
    assert not [r['customer'] for r in results if r['status'] != 'passed'], [r['customer'] for r in results if r['status'] != 'passed']
