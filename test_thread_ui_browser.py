"""Rendered Thread UI -> authenticated API -> real graph -> isolated persistence."""
import asyncio
import json
from pathlib import Path
import os
import shutil
import pytest
import uvicorn
from app import App
from graph_fixtures import ScriptModel, call, plan, finish


@pytest.mark.asyncio
async def test_rendered_thread_graph_archive_restore_and_identity(tmp_path, request):
    if not request.config.getoption('--thread3-live-browser'):
        pytest.skip('BLOCKED: Thread UI regression requires approved TLS and real Chrome')
    app = App()
    await app.setup(tmp_path / 'thread-ui.sqlite')
    before = [app.memory.get(i) for i in range(1, 101)]
    queue = call('queued_additions', {'action': 'show', 'index': 0})
    app.deep_model = ScriptModel(script=[plan('read pending additions'), queue, queue, finish()])
    app.model.key = 'synthetic-not-a-key'
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
        assert server.started
        chrome = os.environ.get('THREAD3_CHROME') or next((p for p in ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', shutil.which('google-chrome'), shutil.which('chromium'), shutil.which('chromium-browser')) if p and Path(p).is_file()), '')
        assert Path(chrome).is_file()
        process = await asyncio.create_subprocess_exec(shutil.which('node'),
            str(Path(__file__).with_name('test_thread_ui.cjs')), chrome,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env={k:v for k,v in os.environ.items() if k!='OPENAI_API_KEY'})
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 120)
        finally:
            if process.returncode is None:
                process.terminate()
                await process.wait()
        assert process.returncode == 0, stderr.decode()
        report = json.loads(stdout)
        assert report['second_identity_isolated'] and report['reload_restore']
        assert app.deep_model.position == 4  # Archives/reload never replay graph effects.
        assert [app.memory.get(i) for i in range(1, 101)] == before
        assert not app.memory.orders()
        Path('audit/thread-ui-browser-result.json').write_text(json.dumps(report, indent=2))
    finally:
        await app.close()
        server.should_exit = True
        await asyncio.wait_for(serving, 10)
