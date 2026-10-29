"""Execute only the specifically approved temporary trust/test/cleanup operation."""
import datetime
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from tls_fixture import validate

ROOT = Path(__file__).resolve().parent
EXPECTED = '5de00475f0e727621fcaac0f00d5874509e87276b8b7b9b0eb0196e614e29d08'
NAME = 'Thread3 test CA cb05212b69d0'
KEYCHAIN = '/Users/ajaybabum/Library/Keychains/login.keychain-db'
REPORT = ROOT / 'audit/trusted-browser-operation.json'


def security(*args):
    return subprocess.run(['/usr/bin/security', *args], capture_output=True, text=True, timeout=90)


def present():
    result = security('find-certificate', '-a', '-c', NAME, '-p', KEYCHAIN)
    if result.returncode not in (0, 44):
        raise RuntimeError('Cannot verify keychain certificate presence: ' + str(result.returncode))
    blocks = re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', result.stdout, re.S)
    return any(x509.load_pem_x509_certificate(block.encode()).fingerprint(hashes.SHA256()).hex() == EXPECTED for block in blocks)


def cleanup(tls, report, save):
    """Try every exact-certificate cleanup/check even if an earlier step times out."""
    report['phase'] = 'removing_exact_approved_certificate'
    report['cleanup_errors'] = []
    save()
    operations = [
        ('remove_trust', ('remove-trusted-cert', str(tls / 'ca.pem'))),
        ('delete_certificate', ('delete-certificate', '-Z', EXPECTED, '-t', KEYCHAIN)),
    ]
    for name, args in operations:
        try:
            report[name + '_returncode'] = security(*args).returncode
        except Exception as error:
            report['cleanup_errors'].append({'step': name, 'type': type(error).__name__})
        save()
    try:
        report['certificate_absent_after_cleanup'] = not present()
    except Exception as error:
        report['certificate_absent_after_cleanup'] = None
        report['cleanup_errors'].append({'step': 'certificate_query', 'type': type(error).__name__})
    try:
        settings = security('dump-trust-settings')
        trust_text = settings.stdout + settings.stderr
        report['trust_query_confirmed'] = settings.returncode == 0 or 'No Trust Settings were found' in trust_text or 'No Trust Settings found' in trust_text
        report['trust_name_absent_after_cleanup'] = NAME not in trust_text
    except Exception as error:
        report['trust_query_confirmed'] = False
        report['trust_name_absent_after_cleanup'] = None
        report['cleanup_errors'].append({'step': 'trust_query', 'type': type(error).__name__})
    report['cleanup_verified'] = report['certificate_absent_after_cleanup'] is True and report['trust_query_confirmed'] and report['trust_name_absent_after_cleanup'] is True
    report['phase'] = 'cleaned_up' if report['cleanup_verified'] else 'CLEANUP_REQUIRES_ATTENTION'
    report['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save()
    return report['cleanup_verified']


def main():
    metadata = json.loads((ROOT / 'audit/pending-tls-confirmation.json').read_text())
    tls = validate(metadata['directory'])
    ca = x509.load_pem_x509_certificate((tls / 'ca.pem').read_bytes())
    if ca.fingerprint(hashes.SHA256()).hex() != EXPECTED:
        raise RuntimeError('Approved certificate fingerprint mismatch; no operation allowed')
    use_existing = '--use-existing-approved-trust' in sys.argv[1:]
    test_args = [arg for arg in sys.argv[1:] if arg != '--use-existing-approved-trust']
    already_present = present()
    if already_present and not use_existing:
        raise RuntimeError('Certificate already present; check prior operation outcome before retrying')
    if use_existing and not already_present:
        raise RuntimeError('The exact approved certificate is absent; no installation was requested')
    report = {'approved_certificate': EXPECTED, 'ca_name': NAME, 'tls_directory': str(tls),
              'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'phase': 'fingerprint_verified', 'keychain': KEYCHAIN, 'trust_policy': 'user SSL'}

    def save():
        REPORT.write_text(json.dumps(report, indent=2))

    def stop(signum, frame):
        raise KeyboardInterrupt('Stopping trusted test operation; cleanup required')

    signal.signal(signal.SIGTERM, stop)
    save()
    attempted = False
    try:
        attempted = True
        if use_existing:
            report['phase'] = 'verifying_existing_approved_SSL_trust'
            report['installation_attempted'] = False
            save()
        else:
            report['phase'] = 'installing_exact_approved_certificate'
            save()
            installed = security('add-trusted-cert', '-r', 'trustRoot', '-p', 'ssl', '-k', KEYCHAIN, str(tls / 'ca.pem'))
            report['installation_returncode'] = installed.returncode
            report['certificate_present_after_install'] = present()
            save()
            if installed.returncode or not report['certificate_present_after_install']:
                raise RuntimeError('Temporary certificate installation was not confirmed: ' + installed.stderr.strip())
        report['SSL_host_verification'] = {}
        for host in ('atlas.localhost', 'jacket.localhost'):
            result = security('verify-cert', '-c', str(tls / 'cert.pem'), '-p', 'ssl', '-n', host, '-k', KEYCHAIN, '-L')
            report['SSL_host_verification'][host] = {'returncode': result.returncode, 'result': result.stdout.strip(), 'diagnostic': result.stderr.strip()}
            save()
            if result.returncode:
                raise RuntimeError('Native SSL certificate verification failed for ' + host)
        env = dict(os.environ, THREAD3_TLS_DIR=str(tls), THREAD3_PORT='8545', LANGSMITH_TRACING='false')
        env.pop('OPENAI_API_KEY', None)
        report['phase'] = 'running_browser_suite'
        save()
        args = [sys.executable, '-m', 'pytest', '--thread3-live-sockets', '--thread3-live-browser',
                '-q', '--tb=short', '--junitxml=audit/browser-enabled-suite.xml', *test_args]
        with (ROOT / 'audit/browser-enabled-suite.log').open('w') as output:
            result = subprocess.run(args, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=900)
        report['tests_returncode'] = result.returncode
    except BaseException as error:
        report['operation_error'] = {'type': type(error).__name__, 'message': str(error)}
        save()
        raise
    finally:
        if attempted:
            if not cleanup(tls, report, save):
                raise RuntimeError('Exact certificate/trust cleanup could not be verified')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
