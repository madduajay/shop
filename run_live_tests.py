"""Explicitly authorized key reuse in one process; shared $50 spending gate."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / 'audit/live-spend-20261024.sqlite'
ORIGINAL = '/Users/ajaybabum/Documents/Codex/2026-10-16/task/wardrobe'


def borrowed_key():
    listing = subprocess.run(['lsof', '-nP', '-iTCP:8443', '-sTCP:LISTEN', '-t'],
                             capture_output=True, text=True, check=False, timeout=10)
    for pid in set(listing.stdout.split()):
        if not pid.isdigit():
            continue
        command = subprocess.run(['ps', '-p', pid, '-o', 'command='],
                                 capture_output=True, text=True, check=False, timeout=10)
        if ORIGINAL not in command.stdout:
            continue
        environment = subprocess.run(['ps', 'eww', '-p', pid, '-o', 'command='],
                                     capture_output=True, text=True, check=False, timeout=10)
        found = re.search(r'(?:^|\s)OPENAI_API_KEY=([^\s]+)', environment.stdout)
        if found and found.group(1).startswith('sk-') and len(found.group(1)) > 20:
            return found.group(1)
    raise RuntimeError('Authorized original Thread key source is unavailable; no other source read')


class Redactor:
    def __init__(self, stream, key):
        self.stream, self.key, self.pending = stream, key, ''

    def clean(self, value):
        return re.sub(r'sk-[A-Za-z0-9_-]{8,}', '[redacted key]', str(value).replace(self.key, '[redacted key]'))

    def write(self, value):
        self.pending += value
        self.pending = self.pending.replace(self.key, '[redacted key]')
        # Keep a complete-key-sized tail so split writes cannot reveal the key.
        length = max(0, len(self.pending) - len(self.key))
        if length:
            self.stream.write(self.clean(self.pending[:length]))
            self.pending = self.pending[length:]
        return len(value)

    def flush(self):
        self.stream.flush()

    def finish(self):
        self.stream.write(self.clean(self.pending))
        self.pending = ''
        self.stream.flush()

    def __getattr__(self, name):
        return getattr(self.stream, name)


def main():
    arguments = sys.argv[1:]
    if '--thread3-live-model' not in arguments:
        raise RuntimeError('Live tests require their explicit opt-in flag')
    if '--thread3-live-browser' in arguments:
        directory = os.environ.get('THREAD3_TEST_TLS_DIR')
        fingerprint = os.environ.get('THREAD3_APPROVED_CA_SHA256')
        if not directory or not fingerprint:
            from launch_live_demo import APPROVED_CA
            metadata = json.loads((ROOT / 'audit/live-demo-process.json').read_text())
            fingerprint = APPROVED_CA
            if metadata['CA_sha256'] != fingerprint:
                raise RuntimeError('Current demo CA differs from the explicitly approved certificate')
            directory = metadata['tls_directory']
        os.environ['THREAD3_APPROVED_CA_SHA256'] = fingerprint
        from tls_fixture import validate_pinned
        tls = validate_pinned(directory, fingerprint)
        for host in ('atlas.localhost', 'jacket.localhost'):
            result = subprocess.run(['security', 'verify-cert', '-c', str(tls / 'cert.pem'),
                '-c', str(tls / 'ca.pem'),
                '-p', 'ssl', '-n', host, '-k', '/Users/ajaybabum/Library/Keychains/login.keychain-db', '-L'],
                capture_output=True, text=True, timeout=15)
            if result.returncode:
                raise RuntimeError('Already-approved native SSL authorization is still pending; no model call started')
        os.environ['THREAD3_TLS_DIR'] = str(tls)
    key = borrowed_key()
    stdout, stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = Redactor(stdout, key), Redactor(stderr, key)
    from spend_budget import install, MODEL, LABEL
    budget = install(key, LEDGER)
    os.environ['OPENAI_API_KEY'] = key
    os.environ['PAP_GPT_MODEL'] = MODEL
    os.environ['LANGSMITH_TRACING'] = 'false'
    os.environ['THREAD3_SPEND_LEDGER'] = str(LEDGER)
    for name in ('OPENAI_BASE_URL', 'OPENAI_API_BASE', 'OPENAI_PROXY'):
        os.environ.pop(name, None)
    import pytest

    class LiveAudit:
        def __init__(self):
            self.completed = []

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(self, item, call):
            result = yield
            report = result.get_result()
            if report.longrepr:
                report.longrepr = sys.stderr.clean(str(report.longrepr))
            report.sections = [(name, sys.stderr.clean(text)) for name, text in report.sections]

        def pytest_runtest_setup(self, item):
            LABEL.set(item.nodeid)

        def pytest_runtest_logreport(self, report):
            if report.when == 'call' or report.when == 'setup' and report.skipped:
                self.completed.append({'case': report.nodeid, 'outcome': report.outcome,
                    'duration_seconds': report.duration})
                (ROOT / 'audit/live-active-case-progress.json').write_text(json.dumps({
                    'completed_cases': self.completed, 'spend': budget.summary()}, indent=2))

        def pytest_sessionfinish(self, session, exitstatus):
            (ROOT / 'audit/live-spend-summary.json').write_text(json.dumps(budget.summary(), indent=2))

    try:
        sys.argv = ['pytest', *arguments]
        code = pytest.main(arguments, plugins=[LiveAudit()])
    finally:
        os.environ.pop('OPENAI_API_KEY', None)
        summary = budget.summary()
        (ROOT / 'audit/live-spend-summary.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps({'spending': summary}))
        sys.stdout.finish(); sys.stderr.finish()
        sys.stdout, sys.stderr = stdout, stderr
    return code


if __name__ == '__main__':
    raise SystemExit(main())
