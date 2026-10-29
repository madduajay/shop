"""Cleanup control flow only: all native security calls are mocked."""
from types import SimpleNamespace
import subprocess
import run_trusted_browser_tests as operation


def test_timeout_does_not_skip_fallback_or_independent_verification(tmp_path, monkeypatch):
    calls = []

    def security(*args):
        calls.append(args[0])
        if args[0] == 'remove-trusted-cert':
            raise subprocess.TimeoutExpired('fixture', 90)
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr(operation, 'security', security)
    monkeypatch.setattr(operation, 'present', lambda: False)
    report = {}
    assert operation.cleanup(tmp_path, report, lambda: None)
    assert calls == ['remove-trusted-cert', 'delete-certificate', 'dump-trust-settings']
    assert report['cleanup_errors'] == [{'step': 'remove_trust', 'type': 'TimeoutExpired'}]
    assert report['phase'] == 'cleaned_up'


def test_remaining_certificate_is_never_reported_clean(tmp_path, monkeypatch):
    monkeypatch.setattr(operation, 'security', lambda *args: SimpleNamespace(returncode=0, stdout='', stderr=''))
    monkeypatch.setattr(operation, 'present', lambda: True)
    report = {}
    assert not operation.cleanup(tmp_path, report, lambda: None)
    assert report['phase'] == 'CLEANUP_REQUIRES_ATTENTION'


def test_failed_queries_are_uncertain_not_absent(tmp_path, monkeypatch):
    def unavailable(*args):
        raise RuntimeError('fixture read unavailable')

    monkeypatch.setattr(operation, 'security', unavailable)
    monkeypatch.setattr(operation, 'present', unavailable)
    report = {}
    assert not operation.cleanup(tmp_path, report, lambda: None)
    assert report['certificate_absent_after_cleanup'] is None
    assert report['trust_name_absent_after_cleanup'] is None
    assert len(report['cleanup_errors']) == 4
