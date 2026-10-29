import json
import pytest
from cryptography import x509
from tls_fixture import prepare, validate, HOSTS


def test_thread3_certificate_is_temporary_constrained_and_private(tmp_path):
    root, manifest = prepare(tmp_path / 'tls')
    assert validate(root) == root.resolve()
    assert not manifest['trust_installed']
    assert not (root / 'ca-key.pem').exists()
    assert (root / 'key.pem').stat().st_mode & 0o077 == 0
    ca = x509.load_pem_x509_certificate((root / 'ca.pem').read_bytes())
    constraints = ca.extensions.get_extension_for_class(x509.NameConstraints).value
    assert {name.value for name in constraints.permitted_subtrees} == set(HOSTS)


def test_tls_fixture_rejects_shared_ca_or_changed_files(tmp_path):
    root, manifest = prepare(tmp_path / 'tls')
    manifest['ca_sha256'] = '0' * 64
    (root / 'thread3-tls.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='fingerprint mismatch'):
        validate(root)


def test_tls_fixture_refuses_external_key_symlink(tmp_path):
    root, manifest = prepare(tmp_path / 'tls')
    outside = tmp_path / 'outside-key.pem'
    (root / 'key.pem').rename(outside)
    (root / 'key.pem').symlink_to(outside)
    with pytest.raises(ValueError, match='external credential'):
        validate(root)
