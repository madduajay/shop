"""Local live-GPT launch with shop-owned configuration and shared spending gate."""
import argparse
import asyncio
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import signal
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent
APPROVED_CA = '7fb2a4a6865a27742a38b66b086e8811782a82e25fbfe9ccc82a70feadc6e1f3'


def configured_key():
    """Read only the launch environment or this shop's .env; never other processes."""
    from dotenv import dotenv_values
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not key:
        # Do not search parent folders or expand references to other environment values.
        key = (dotenv_values(ROOT / '.env', interpolate=False).get('OPENAI_API_KEY') or '').strip()
    if not key:
        raise RuntimeError('Shop API key is missing. Set OPENAI_API_KEY in the launch '
                           'environment or in the shop .env file, then restart.')
    if not key.startswith('sk-') or any(c.isspace() for c in key):
        raise RuntimeError('Shop OPENAI_API_KEY is invalid; check its configuration.')
    return key


async def serve(args):
    key = configured_key()
    from tls_fixture import validate_pinned
    fingerprint = args.approved_ca_sha256
    os.environ['THREAD3_APPROVED_CA_SHA256'] = fingerprint
    tls = validate_pinned(args.tls_dir, fingerprint)
    for host in ('atlas.localhost', 'jacket.localhost'):
        result = subprocess.run(['security', 'verify-cert', '-c', str(tls / 'cert.pem'),
            '-c', str(tls / 'ca.pem'), '-p', 'ssl', '-n', host, '-L'],
            capture_output=True, timeout=15)
        if result.returncode:
            raise RuntimeError('Native SSL trust is not verified; live launch refused')
    state = ROOT / '.local-live-state'
    marker = state / 'purpose.json'
    if state.is_symlink() or not state.resolve().is_relative_to(ROOT):
        raise RuntimeError('Live state must remain inside the separate Thread3 project')
    if state.exists() and (not marker.is_file() or json.loads(marker.read_text()) != {'purpose': 'thread3-local-live-synthetic-state-v1'}):
        raise RuntimeError('State destination contains unrelated or unidentified work')
    state.mkdir(mode=0o700, exist_ok=True)
    marker.write_text(json.dumps({'purpose': 'thread3-local-live-synthetic-state-v1'}))
    from run_live_tests import LEDGER, Redactor
    from spend_budget import install, MODEL
    budget = install(key, LEDGER)
    os.environ.update(OPENAI_API_KEY=key, PAP_GPT_MODEL=MODEL,
        THREAD3_PORT=str(args.port), THREAD3_TLS_DIR=str(tls), LANGSMITH_TRACING='false')
    for name in ('OPENAI_BASE_URL', 'OPENAI_API_BASE', 'OPENAI_PROXY'):
        os.environ.pop(name, None)
    original_out, original_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = Redactor(original_out, key), Redactor(original_err, key)
    from cryptography import x509
    import uvicorn
    from app import App
    class LocalServer(uvicorn.Server):
        @contextmanager
        def capture_signals(self):
            # Finish the launcher's finally block instead of re-raising SIGTERM
            # before state/cost metadata and owned resources can be closed.
            def stop(signum, frame):
                if self.should_exit and signum == signal.SIGINT:
                    self.force_exit = True
                self.should_exit = True
            prior = {s: signal.signal(s, stop) for s in (signal.SIGINT, signal.SIGTERM)}
            try:
                yield
            finally:
                for sig, handler in prior.items():
                    signal.signal(sig, handler)
    app = App()
    await app.setup(state / 'thread3.sqlite')
    assert app.model.key and not hasattr(app, 'deep_model')
    server = LocalServer(uvicorn.Config(app, host='127.0.0.1', port=args.port,
        ssl_certfile=str(tls / 'cert.pem'), ssl_keyfile=str(tls / 'key.pem'),
        access_log=False, log_level='warning', timeout_graceful_shutdown=10))
    expires = x509.load_pem_x509_certificate((tls / 'cert.pem').read_bytes()).not_valid_after_utc
    metadata = {'pid': os.getpid(), 'mode': 'live GPT through genuine Deep Agents; no scripted fallback',
        'model': MODEL, 'key': 'shop OPENAI_API_KEY configuration; value never recorded',
        'thread_url': f'https://atlas.localhost:{args.port}/',
        'forme_url': f'https://jacket.localhost:{args.port}/shop',
        'bind': f'127.0.0.1:{args.port}', 'state_directory': str(state),
        'state': 'separate synthetic state retained across restarts; existing demos untouched',
        'tls_directory': str(tls), 'CA_sha256': fingerprint,
        'automatic_stop_utc': (expires - datetime.timedelta(seconds=60)).isoformat(),
        'system_trust_changed_by_launcher': False, 'spend_before': budget.summary(), 'status': 'starting'}
    record = ROOT / 'audit/live-demo-process.json'
    record.write_text(json.dumps(metadata, indent=2))

    async def deadline():
        await asyncio.sleep(max(0, (expires - datetime.datetime.now(datetime.timezone.utc)).total_seconds() - 60))
        server.should_exit = True

    timer = asyncio.create_task(deadline())
    try:
        metadata['status'] = 'serving'
        record.write_text(json.dumps(metadata, indent=2))
        await server.serve()
    finally:
        timer.cancel()
        await asyncio.gather(timer, return_exceptions=True)
        await app.close()
        os.environ.pop('OPENAI_API_KEY', None)
        metadata.update(status='stopped', spend_after=budget.summary())
        record.write_text(json.dumps(metadata, indent=2))
        sys.stdout.finish(); sys.stderr.finish()
        sys.stdout, sys.stderr = original_out, original_err


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tls-dir', required=True)
    parser.add_argument('--port', type=int, choices=[8545], default=8545)
    parser.add_argument('--serve-live', required=True, action='store_true')
    parser.add_argument('--approved-ca-sha256', default=APPROVED_CA,
        help='Exact CA fingerprint separately approved for native SSL trust; never installs trust')
    asyncio.run(serve(parser.parse_args()))
