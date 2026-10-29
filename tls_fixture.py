"""Prepare/validate a temporary Thread3-only certificate. Never installs trust."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

HOSTS = ('atlas.localhost', 'jacket.localhost')


def prepare(directory=None, *, expires_at=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    expires = expires_at or now + datetime.timedelta(hours=6)
    if (not isinstance(expires, datetime.datetime) or expires.tzinfo is None or
            not now < expires <= now + datetime.timedelta(days=93)):
        raise ValueError('TLS expiry must be timezone-aware, future and at most93days away')
    root = Path(directory) if directory else Path(tempfile.mkdtemp(prefix='thread3-tls-'))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError('TLS fixture destination must be empty')
    root.chmod(0o700)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Thread3 test CA ' + secrets.token_hex(6))])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - datetime.timedelta(minutes=5)).not_valid_after(expires)
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True,
                         content_commitment=False, key_encipherment=False, data_encipherment=False,
                         key_agreement=False, encipher_only=False, decipher_only=False), critical=True)
          .add_extension(x509.NameConstraints(permitted_subtrees=[x509.DNSName(h) for h in HOSTS], excluded_subtrees=None), critical=True)
          .sign(ca_key, hashes.SHA256()))
    key = ec.generate_private_key(ec.SECP256R1())
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, HOSTS[0])]))
            .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5)).not_valid_after(expires)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(h) for h in HOSTS]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    (root / 'ca.pem').write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (root / 'cert.pem').write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    # Only the leaf key is saved, in the temporary fixture. The CA signing key is discarded.
    (root / 'key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    for name in ('ca.pem', 'cert.pem', 'key.pem'):
        (root / name).chmod(0o600)
    manifest = {'purpose': 'thread3-temporary-tls-v1', 'hosts': list(HOSTS), 'expires_utc': expires.isoformat(),
                'ca_subject': ca.subject.rfc4514_string(), 'ca_sha256': ca.fingerprint(hashes.SHA256()).hex(),
                'leaf_sha256': leaf.fingerprint(hashes.SHA256()).hex(), 'trust_installed': False}
    (root / 'thread3-tls.json').write_text(json.dumps(manifest, indent=2))
    return root.resolve(), manifest


def validate(directory):
    root = Path(directory).resolve()
    allowed = (Path(__file__).resolve().parent, Path('/tmp').resolve(), Path(tempfile.gettempdir()).resolve())
    if not any(root.is_relative_to(p) for p in allowed):
        raise ValueError('Thread3 TLS must be in its workspace or temporary fixtures')
    manifest = json.loads((root / 'thread3-tls.json').read_text())
    if manifest.get('purpose') != 'thread3-temporary-tls-v1' or manifest.get('hosts') != list(HOSTS):
        raise ValueError('Not a Thread3-generated TLS fixture')
    if any(not (root / name).resolve().is_relative_to(root) for name in ('ca.pem', 'cert.pem', 'key.pem')):
        raise ValueError('TLS fixture cannot reference external credential files')
    keypath = root / 'key.pem'
    if keypath.stat().st_uid != os.getuid() or keypath.stat().st_mode & 0o077:
        raise ValueError('Thread3 leaf key permissions must be owner-only')
    ca = x509.load_pem_x509_certificate((root / 'ca.pem').read_bytes())
    leaf = x509.load_pem_x509_certificate((root / 'cert.pem').read_bytes())
    ca_fingerprint = ca.fingerprint(hashes.SHA256()).hex()
    approved_existing = (ca.subject.rfc4514_string() == 'CN=PAP demo CA' and
                         os.environ.get('THREAD3_APPROVED_CA_SHA256') == ca_fingerprint)
    if not ca.subject.rfc4514_string().startswith('CN=Thread3 test CA ') and not approved_existing:
        raise ValueError('Original/shared CA reuse is prohibited')
    if ca.fingerprint(hashes.SHA256()).hex() != manifest['ca_sha256'] or leaf.fingerprint(hashes.SHA256()).hex() != manifest['leaf_sha256']:
        raise ValueError('TLS fixture fingerprint mismatch')
    if set(leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)) != set(HOSTS):
        raise ValueError('Unexpected certificate hostnames')
    if min(leaf.not_valid_after_utc, ca.not_valid_after_utc) <= datetime.datetime.now(datetime.timezone.utc):
        raise ValueError('Thread3 TLS fixture expired')
    leaf.verify_directly_issued_by(ca)
    key = serialization.load_pem_private_key(keypath.read_bytes(), password=None)
    if key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo) != leaf.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo):
        raise ValueError('Thread3 TLS leaf/key mismatch')
    return root


def bind_approved_existing(directory, expected_ca_sha256):
    """Add public fixture metadata for the exact already-approved Thread3 demo CA.

    No trust is installed, keys are never copied, and ordinary validation retains
    its original rejection unless this process explicitly names the exact hash.
    """
    root = Path(directory).resolve()
    if not root.parent.name.startswith('thread3-fixture-') or root.name != 'tls':
        raise ValueError('Only an existing isolated Thread3 demo fixture is eligible')
    if not root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise ValueError('Existing demo TLS must remain temporary')
    ca = x509.load_pem_x509_certificate((root / 'ca.pem').read_bytes())
    leaf = x509.load_pem_x509_certificate((root / 'cert.pem').read_bytes())
    if ca.fingerprint(hashes.SHA256()).hex() != expected_ca_sha256:
        raise ValueError('Explicitly approved CA fingerprint mismatch')
    if os.environ.get('THREAD3_APPROVED_CA_SHA256') != expected_ca_sha256:
        raise ValueError('Exact existing-CA process opt-in is required')
    manifest = {'purpose': 'thread3-temporary-tls-v1', 'hosts': list(HOSTS),
        'expires_utc': leaf.not_valid_after_utc.isoformat(), 'ca_subject': ca.subject.rfc4514_string(),
        'ca_sha256': expected_ca_sha256, 'leaf_sha256': leaf.fingerprint(hashes.SHA256()).hex(),
        'trust_installed': False}
    (root / 'thread3-tls.json').write_text(json.dumps(manifest, indent=2))
    return validate(root)


def validate_pinned(directory, expected_ca_sha256):
    """Validate an existing fixture against the exact caller-approved CA hash.

    This reads files only. Native SSL trust remains a separate required check.
    """
    root = validate(directory)
    ca = x509.load_pem_x509_certificate((root / 'ca.pem').read_bytes())
    if ca.fingerprint(hashes.SHA256()).hex() != expected_ca_sha256:
        raise ValueError('Explicitly approved CA fingerprint mismatch')
    return root


if __name__ == '__main__':
    root, manifest = prepare()
    print(json.dumps({'directory': str(root), **manifest}, indent=2))
