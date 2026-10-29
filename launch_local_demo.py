"""Bounded synthetic command-mode demo. Never installs trust or loads a key."""
import argparse
import asyncio
import datetime
import json
import os
from pathlib import Path

# Remove ambient provider access before importing any application/model module.
os.environ.pop('OPENAI_API_KEY', None)
os.environ['LANGSMITH_TRACING'] = 'false'
os.environ['THREAD3_PORT'] = '8543'


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tls-dir', required=True)
    args = parser.parse_args()
    from tls_fixture import validate
    from cryptography import x509
    tls = validate(args.tls_dir)
    os.environ['THREAD3_TLS_DIR'] = str(tls)
    leaf = x509.load_pem_x509_certificate((tls / 'cert.pem').read_bytes())
    now = datetime.datetime.now(datetime.timezone.utc)
    duration = min(1800, (leaf.not_valid_after_utc - now).total_seconds() - 60)
    if duration < 300:
        raise RuntimeError('Demo needs at least five minutes of valid TLS remaining')
    import uvicorn
    from app import App
    app = App()
    await app.setup()
    assert not app.model.key
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8543,
        ssl_certfile=str(tls / 'cert.pem'), ssl_keyfile=str(tls / 'key.pem'),
        access_log=False, log_level='warning'))
    expires = now + datetime.timedelta(seconds=duration)
    state = {'pid': os.getpid(), 'mode': 'synthetic command fallback; no scripted provider or actual model',
        'paid_API_calls': 'disabled; ambient key removed before imports',
        'thread_url': 'https://atlas.localhost:8543/', 'forme_url': 'https://jacket.localhost:8543/shop',
        'bind': '127.0.0.1:8543', 'tls_directory': str(tls),
        'automatic_stop_utc': expires.isoformat(), 'state': 'temporary synthetic fixtures; originals untouched',
        'status': 'starting', 'system_trust_modified_by_launcher': False}
    record = Path(__file__).resolve().parent / 'audit/local-demo-process.json'
    record.write_text(json.dumps(state, indent=2))

    async def stop_on_deadline():
        await asyncio.sleep(duration)
        server.should_exit = True

    deadline = asyncio.create_task(stop_on_deadline())
    try:
        await server.serve()
    finally:
        deadline.cancel()
        await asyncio.gather(deadline, return_exceptions=True)
        await app.close()
        state['status'] = 'stopped'
        record.write_text(json.dumps(state, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
