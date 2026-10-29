import os
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from tls_fixture import bind_approved_existing, validate


@pytest.mark.asyncio
async def test_generic_demo_CA_needs_exact_explicit_process_approval(tmp_path, monkeypatch):
    from app import App
    monkeypatch.delenv('THREAD3_TLS_DIR', raising=False)
    app = App()
    await app.setup(tmp_path / 'approved-tls.sqlite')
    try:
        tls = app.tls
        ca = x509.load_pem_x509_certificate((tls / 'ca.pem').read_bytes())
        fingerprint = ca.fingerprint(hashes.SHA256()).hex()
        monkeypatch.delenv('THREAD3_APPROVED_CA_SHA256', raising=False)
        with pytest.raises(ValueError, match='opt-in'):
            bind_approved_existing(tls, fingerprint)
        monkeypatch.setenv('THREAD3_APPROVED_CA_SHA256', fingerprint)
        assert bind_approved_existing(tls, fingerprint) == tls.resolve()
        monkeypatch.setenv('THREAD3_APPROVED_CA_SHA256', '0' * 64)
        with pytest.raises(ValueError, match='reuse'):
            validate(tls)
        assert not (tls / 'ca-key.pem').exists()
    finally:
        await app.close()
