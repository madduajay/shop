"""Prepare a local source handoff. This script never uploads or reads live state."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
EXTENSIONS = {'.py', '.html', '.js', '.cjs', '.json', '.toml', '.txt'}
DOCS = {'README.md', 'PARITY.md', 'STATUS.md', 'HANDOFF.md', 'CLOUD-HANDOFF.md', '.gitignore'}


def selected():
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if not p.resolve().is_relative_to(ROOT) or p.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.crt', '.cer', '.sqlite', '.sqlite3', '.db', '.log', '.pid'} or any(str(p).endswith(s) for s in ('-wal', '-shm', '.env')):
            continue
        if any(part in {'.venv', '__pycache__', '.pytest_cache', '.git'} for part in rel.parts):
            continue
        # No traces, logs, credentials, profiles, state or arbitrary evidence files.
        if rel.parts[0] in {'audit', 'evidence'}:
            if str(rel) not in {'audit/source-manifest.json', 'audit/test-cases.json', 'audit/case-results.json', 'audit/differential.json', 'audit/verification-summary.json', 'audit/verification.xml', 'audit/baseline-recheck.xml', 'audit/cloud-validation.json', 'evidence/before-photo-catalog.json'}:
                continue
        elif rel.parts[0] in {'assets', 'vendor', 'agent_skills'}:
            if p.suffix.lower() not in {'.py', '.md', '.json', '.jpg', '.jpeg', '.png', '.webp', '.svg', '.css', '.js', '.html', '.txt', '.yaml', '.yml'} and p.name != 'LICENSE':
                continue
        elif len(rel.parts) != 1 or (p.suffix not in EXTENSIONS and p.name not in DOCS):
            continue
        if p.name == 'store.before-expansion.py' or p.name.startswith('.') and p.name != '.gitignore':
            continue
        yield p, rel


def main():
    archive = ROOT.parent / 'thread3-source-handoff.zip'
    manifest = []
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for p, rel in selected():
            data = p.read_bytes()
            output.writestr('thread3/' + str(rel), data)
            manifest.append({'path': str(rel), 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        output.writestr('thread3/HANDOFF-MANIFEST.json', json.dumps(manifest, indent=2))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(checksum + '  ' + archive.name + '\n')
    print(json.dumps({'archive': str(archive), 'files': len(manifest), 'bytes': archive.stat().st_size, 'sha256': checksum}))


if __name__ == '__main__':
    main()
