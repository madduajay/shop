import asyncio
import json
from types import SimpleNamespace
import pytest
from app import App, Flow
from checkpoints import DurableSaver
from deep_runtime import Runner, safe, BLOCKED_TOOLS, validate_schema
from graph_fixtures import ScriptModel, call, plan, finish


async def fixture(tmp_path, script, execute=None, customer=1):
    app = App()
    await app.setup(tmp_path / 'fixture.sqlite')
    app.deep_model = ScriptModel(script=script)
    app.model.key = 'fixture-only-never-sent'

    async def compose(instructions, payload, *args):
        return {'sections': [{'source': row['source'], 'text': json.dumps({fact['key']: fact['value'] for fact in row['facts']}), 'evidence_ids': [fact['id'] for fact in row['facts']]} for row in payload['tool_results']]}

    app.model.structured = compose
    f = Flow(app, customer)
    if execute:
        f.execute_tool_calls = execute
    return app, f


@pytest.mark.asyncio
async def test_loaded_workflow_cannot_be_mistaken_for_executed_write(tmp_path):
    update = call('update_preferences', {'source': 'Thread', 'updates': [{'field': 'shirt_size', 'value': 'L'}]})
    read = call('read_user_preferences', {'source': 'Thread'})
    app, flow = await fixture(tmp_path, [plan('save shirt size'), update, read])
    before = app.memory.get(1)
    try:
        await flow.plan_and_execute('Remember my shirt size is L')
        assert app.deep_model.advertised[2] == ['update_preferences']
        assert flow.agent_task['status'] == 'incomplete'
        assert flow.agent_task['results'] == []
        assert app.memory.get(1) == before
        assert app.graph_saver.db.execute('SELECT count(*) FROM effect_claims').fetchone()[0] == 0
    finally:
        await app.close()


async def cleanup(app):
    await app.http.aclose()
    if hasattr(app, 'graph_saver'):
        app.graph_saver.close()


@pytest.mark.asyncio
async def test_public_catalog_refinement_cannot_read_stale_bag_context(tmp_path):
    import time
    executed = []

    async def execute(*args):
        executed.append(True)
        return 'Unexpected bag access', []

    app, flow = await fixture(tmp_path, [plan('refine tie price'), call('read_forme_bag')], execute)
    flow.catalog_snapshot = {'filters': {'category': 'ties', 'expires_at': str(int(time.time() + 60))}}
    flow.last_read = 'bag'
    try:
        await flow.plan_and_execute('under $80')
        assert app.deep_model.advertised[1] == ['catalog_search']
        assert not executed and flow.agent_task['status'] == 'incomplete'
        assert not flow.agent_task['results']
        flow.deep_runner.task['request'] = 'Show pending additions'
        assert flow.deep_runner.business_scope() is None
        flow.deep_runner.task['request'] = 'Find white shirts and add the first one to my bag'
        assert flow.deep_runner.business_scope() is None
        flow.deep_runner.task['request'] = 'find me a cummerbund'
        assert flow.deep_runner.business_scope() == {'catalog_search'}
        flow.deep_runner.task['request'] = 'checkout'
        assert flow.deep_runner.business_scope() == {'checkout_review'}
    finally:
        await app.close()


@pytest.mark.asyncio
async def test_real_deepagents_identity_and_conditional_tools(tmp_path):
    app, f = await fixture(tmp_path, [plan(), call('read_thread_user_data'), call('read_thread_user_data'), finish()])
    try:
        reply, cards = await f.plan_and_execute('Who am I?')
        assert 'Alex Morgan' in reply
        assert f.agent_task['status'] == 'completed'
        assert f.deep_runner.graph.name == 'Thread3'
        assert f.agent_task['results'][0]['tool'] == 'read_thread_user_data'
        advertised = app.deep_model.advertised
        assert advertised[0] == ['plan_request']
        assert 'finish_request' not in advertised[1]
        assert 'finish_request' in advertised[-1]
        assert not set().union(*(set(names) for names in advertised)) & BLOCKED_TOOLS
    finally:
        await cleanup(app)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['complete', 'repeat', 'failure', 'premature', 'unavailable', 'bounded'])
async def test_evidence_completion_and_duplicate_effects(tmp_path, mode):
    executed = []

    async def execute(*args):
        executed.append(True)
        if mode in ('failure', 'unavailable'):
            raise ValueError('uncertain effect')
        return 'Verified fixture identity.', []

    script = [plan()]
    if mode == 'premature':
        script += [finish('old_card_id')]
    if mode == 'bounded':
        script += [finish('old_card_id'), finish('old_card_id')]
    else:
        script += [call('read_thread_user_data'), call('read_thread_user_data')]
        script += [call('read_thread_user_data')] if mode == 'repeat' else [finish(status='unavailable' if mode == 'failure' else 'satisfied')]
        if mode == 'unavailable':
            script += [finish(status='unavailable')]
    app, f = await fixture(tmp_path, script, execute)
    try:
        reply, cards = await f.plan_and_execute('Who am I?')
        assert len(executed) == (0 if mode == 'bounded' else 1)
        assert f.agent_task['status'] == {'repeat': 'paused_after_duplicate', 'failure': 'incomplete', 'unavailable': 'incomplete', 'bounded': 'incomplete'}.get(mode, 'completed')
        assert f.agent_task['iterations'] <= 7
    finally:
        await cleanup(app)


@pytest.mark.asyncio
async def test_checkout_cannot_be_forged(tmp_path):
    executed = []

    async def execute(*args):
        executed.append(True)
        return 'Order FM-fake', []

    app, f = await fixture(tmp_path, [plan('purchase'), call('confirm_checkout')], execute)
    try:
        reply, _ = await f.plan_and_execute('I might buy it tomorrow')
        assert 'Nothing was purchased' in reply
        assert not executed and f.agent_task['status'] == 'blocked'
    finally:
        await cleanup(app)


@pytest.mark.asyncio
async def test_waiting_for_explicit_watch_consent_stops_graph(tmp_path):
    executed = []

    async def execute(*args):
        executed.append(True)
        f.watch_transition = {'phase': 'waiting_user', 'consent': 'synthetic-offer'}
        return 'Would you like a notification?', []

    app, f = await fixture(tmp_path, [plan('find ties'), call('catalog_search'), call('catalog_search'), call('availability_notifications', {'action': 'subscribe', 'event_id': ''})], execute)
    try:
        reply, _ = await f.plan_and_execute('Find ties')
        assert len(executed) == 1 and reply == 'Would you like a notification?'
        assert f.agent_task['status'] == 'waiting_user'
    finally:
        await cleanup(app)


@pytest.mark.asyncio
async def test_authorization_resume_does_not_repeat_business_tool(tmp_path):
    executed = []

    async def execute(*args):
        executed.append(True)
        f.signurl = 'https://jacket.localhost:8545/signin?ticket=secret-fixture'
        return 'Authorize FORME.', []

    app, f = await fixture(tmp_path, [plan('read bag'), call('read_forme_bag'), call('read_forme_bag'), finish()], execute)
    try:
        await f.plan_and_execute('Show my FORME bag')
        assert f.agent_task['status'] == 'blocked' and len(executed) == 1
        f.signurl = None
        reply, _ = await f.continue_agent_task('Your bag is empty.', [])
        assert f.agent_task['status'] == 'completed' and len(executed) == 1
        assert 'Your bag is empty' in reply
    finally:
        await cleanup(app)


@pytest.mark.asyncio
async def test_reopen_checkpoints_and_effect_claims(tmp_path):
    app, f = await fixture(tmp_path, [plan(), call('read_thread_user_data'), call('read_thread_user_data'), finish()])
    try:
        await f.plan_and_execute('Who am I?')
        task = f.agent_task
        config = {'configurable': {'thread_id': task['owner'] + ':' + task['id']}}
        dbpath = tmp_path / 'fixture-graph.sqlite'
        saved = app.graph_saver.get_tuple(config)
        app.graph_saver.close()
        app.graph_saver = DurableSaver(dbpath)
        restored = app.graph_saver.get_tuple(config)
        assert saved.checkpoint == restored.checkpoint
        assert restored.checkpoint['channel_values']['task']['status'] == 'completed'
        assert not app.graph_saver.claim(task['owner'], task['id'], task['results'][0]['signature'])
        assert app.graph_saver.claim('other-owner', task['id'], task['results'][0]['signature'])
        assert not app.graph_saver.get_tuple({'configurable': {'thread_id': 'other-owner:' + task['id']}})
    finally:
        await cleanup(app)


@pytest.mark.asyncio
async def test_crashed_claim_blocks_reexecution(tmp_path):
    executed = []

    async def execute(*args):
        executed.append(True)
        return 'Verified.', []

    app, f = await fixture(tmp_path, [plan(), call('read_thread_user_data'), call('read_thread_user_data'), finish()], execute)
    try:
        saver = DurableSaver(tmp_path / 'claims.sqlite')
        runner = Runner(f, saver, app.deep_model)
        runner.task = {'id': 'request', 'owner': 'owner', 'request': 'Who am I?', 'status': 'running', 'requirements': ['read identity'], 'skills': {'identity-preferences': {}}, 'results': [], 'elapsed': 0}
        runner.started = __import__('time').monotonic()
        assert saver.claim('owner', 'request', 'read_thread_user_data{}')
        result = await runner.execute({'id': 'tool', **call('read_thread_user_data')})
        assert result['status'] == 'uncertain' and not executed
        saver.close()
    finally:
        await cleanup(app)


@pytest.mark.asyncio
async def test_model_turn_limit_without_business_execution(tmp_path):
    app, f = await fixture(tmp_path, [plan(), call('read_file', {'file_path': '/etc/passwd'})])
    try:
        await f.plan_and_execute('Read identity')
        assert f.agent_task['iterations'] == 16
        assert f.agent_task['status'] == 'limit'
        assert not f.agent_task['results']
    finally:
        await cleanup(app)


def test_secret_scrubbing_and_live_object_rejection():
    result = safe({'access_token': 'abc', 'reply': 'https://jacket.localhost/signin?ticket=secret Bearer abc', 'rows': [{'password': 'pwd'}]})
    assert 'secret' not in json.dumps(result) and 'abc' not in json.dumps(result) and 'pwd' not in json.dumps(result)
    with pytest.raises(TypeError):
        safe({'browser': SimpleNamespace()})


@pytest.mark.parametrize('value', [True, 0, 11, '1'])
def test_strict_nested_schema_validation(value):
    with pytest.raises(ValueError):
        validate_schema({'quantity': value}, {'type': 'object', 'properties': {'quantity': {'type': 'integer', 'minimum': 1, 'maximum': 10}}, 'required': ['quantity'], 'additionalProperties': False})


@pytest.mark.asyncio
async def test_twelve_tool_effect_limit(tmp_path):
    executed = []

    async def execute(*args):
        executed.append(True)
        return 'Verified queue.', []

    actions = [call('queued_additions', {'action': 'show', 'index': i}) for i in range(13)]
    app, f = await fixture(tmp_path, [plan('read pending additions'), actions[0]] + actions, execute)
    try:
        await f.plan_and_execute('Show pending additions')
        assert len(executed) == 12 and f.agent_task['status'] == 'limit'
    finally:
        await cleanup(app)


@pytest.mark.asyncio
async def test_elapsed_limit_stops_after_verified_effect(tmp_path):
    executed = []

    async def execute(*args):
        executed.append(True)
        f.agent_task['elapsed'] = 91
        return 'Verified identity.', []

    app, f = await fixture(tmp_path, [plan(), call('read_thread_user_data'), call('read_thread_user_data'), finish()], execute)
    try:
        await f.plan_and_execute('Who am I?')
        assert len(executed) == 1 and f.agent_task['status'] == 'limit'
    finally:
        await cleanup(app)


@pytest.mark.asyncio
@pytest.mark.parametrize('customer', range(1, 101))
async def test_all_profile_graph_identity_and_preference_isolation(tmp_path, customer):
    update = call('update_preferences', {'source': 'Thread', 'updates': [{'field': 'shirt_size', 'value': 'XL'}]})
    app, f = await fixture(tmp_path, [plan('save explicit Thread preference'), update, update, finish()], customer=customer)
    try:
        before = [app.memory.get(n) for n in range(1, 101)]
        reply, _ = await f.plan_and_execute('Remember my Thread shirt size is XL')
        assert reply == 'Saved in Thread — shirt size: XL.'
        assert f.agent_task['status'] == 'completed'
        assert f.agent_task['owner'] == app.thread_accounts.by_profile(customer)['id']
        for n in range(1, 101):
            if n != customer:
                assert app.memory.get(n) == before[n - 1]
        assert app.company_context.get('forme_customer_%03d' % customer) is None
        # Attempting to resume another owner's copied checkpoint is rejected.
        f.agent_task['owner'] = 'wrong-owner'
        with pytest.raises(ValueError, match='owner mismatch'):
            await f.plan_and_execute('Resume', resume=True)
    finally:
        await cleanup(app)


@pytest.mark.asyncio
async def test_new_flow_recovers_pending_graph_without_replaying(tmp_path):
    executed = []

    async def execute(*args):
        executed.append(True)
        f.signurl = 'https://jacket.localhost:8545/signin?ticket=DO-NOT-CHECKPOINT'
        return 'Authorize FORME.', []

    app, f = await fixture(tmp_path, [plan('read bag'), call('read_forme_bag'), call('read_forme_bag'), finish()], execute)
    try:
        await f.plan_and_execute('Show my FORME bag')
        assert f.agent_task['status'] == 'blocked'
        app.graph_saver.close()
        app.graph_saver = DurableSaver(tmp_path / 'fixture-graph.sqlite')
        recovered = Flow(app, 1)
        assert recovered.agent_task['status'] == 'recovery_required'
        assert recovered.token is None and recovered.signurl is None
        assert 'DO-NOT-CHECKPOINT' not in (tmp_path / 'fixture-graph.sqlite').read_bytes().decode(errors='ignore')
        answer, _ = await recovered.plan_and_execute('Resume', resume=True)
        assert 'fresh review' in answer and len(executed) == 1
    finally:
        await cleanup(app)


@pytest.mark.asyncio
async def test_clear_conversation_cancels_graph_checkpoint(tmp_path):
    app, f = await fixture(tmp_path, [plan(), call('read_thread_user_data'), call('read_thread_user_data'), finish()])
    try:
        await f.plan_and_execute('Who am I?')
        owner = f.agent_task['owner']
        await f.clear_conversation()
        assert f.agent_task is None
        assert app.graph_saver.latest_task(owner)['status'] == 'cancelled'
        recovered = Flow(app, 1)
        assert not getattr(recovered, 'agent_task', None)
    finally:
        await cleanup(app)
