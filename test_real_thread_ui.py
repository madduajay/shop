"""Normal-TLS rendered Thread UI exercises the genuine GPT-backed graph."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import pytest
import uvicorn
from app import App
from gpt_chat import MODEL
from spend_budget import SpendBudget, LABEL


@pytest.mark.asyncio
async def test_rendered_thread_ui_with_actual_model(tmp_path, request):
    if not os.environ.get('OPENAI_API_KEY') or not request.config.getoption('--thread3-live-browser'):
        pytest.skip('Actual GPT plus approved browser TLS required')
    app = App()
    await app.setup(tmp_path / 'real-ui.sqlite')
    before = [app.memory.get(i) for i in range(1, 101)]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8545,
        ssl_certfile=str(app.tls / 'cert.pem'), ssl_keyfile=str(app.tls / 'key.pem'),
        access_log=False, log_level='critical'))
    serving = asyncio.create_task(server.serve())
    try:
        for _ in range(100):
            if server.started:
                break
            if serving.done():
                await serving
            await asyncio.sleep(.05)
        assert server.started and not hasattr(app, 'deep_model')
        chrome = os.getenv('THREAD3_CHROME') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        process = await asyncio.create_subprocess_exec(shutil.which('node'),
            str(Path(__file__).with_name('test_thread_ui.cjs')), chrome, 'actual-provider',
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env={k:v for k,v in os.environ.items() if k != 'OPENAI_API_KEY'})
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 120)
        finally:
            if process.returncode is None:
                process.terminate()
                await process.wait()
        assert process.returncode == 0, stderr.decode()
        report = json.loads(stdout)
        assert report['actual_provider_requested'] and not report['real_deepagents_via_scripted_provider']
        assert report['second_identity_isolated'] and report['reload_restore']
        assert [app.memory.get(i) for i in range(1, 101)] == before
        assert not app.memory.orders()
        # The UI archives then clears the flow; inspect its durable graph evidence.
        records = list(app.graph_saver.list(None))
        tasks = [r.checkpoint['channel_values'].get('task') for r in records]
        tasks = [t for t in tasks if t]
        assert any(t['status'] == 'completed' and any(r['tool'] == 'queued_additions' for r in t['results']) for t in tasks)
        gate = SpendBudget(os.environ['THREAD3_SPEND_LEDGER'])
        with gate.db() as db:
            calls = db.execute('SELECT count(*) FROM attempts WHERE label=? AND status=? AND http_status=200',
                (LABEL.get(), 'measured')).fetchone()[0]
        assert calls >= 3
        report.update(provider_model=MODEL, actual_model_calls=calls,
            completed_graph_with_business_tool=True, all_profiles_unchanged=True, no_orders=True)
        Path('audit/real-thread-ui-result.json').write_text(json.dumps(report, indent=2))
    finally:
        await app.close()
        server.should_exit = True
        await asyncio.wait_for(serving, 10)
