"""Ephemeral synthetic fixtures. Never loads an original credential or database."""
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
import os
from personal_agent_protocol.demo.sockets import _certificates

ROOT = Path(__file__).resolve().parent


def fixture_paths(memory_path=None):
    directory = TemporaryDirectory(prefix='thread3-fixture-')
    root = Path(directory.name)
    path = (Path(memory_path) if memory_path else root / 'thread3.sqlite').resolve()
    allowed = (ROOT, Path('/tmp').resolve(), Path(gettempdir()).resolve())
    if not any(path.is_relative_to(base) for base in allowed):
        directory.cleanup()
        raise ValueError('Thread3 cannot open writable state outside its isolated workspace')
    path.parent.mkdir(parents=True, exist_ok=True)
    shared = os.getenv('THREAD3_TLS_DIR')
    if shared:
        from tls_fixture import validate
        tls = validate(shared)
    else:
        tls = root / 'tls'
        tls.mkdir(mode=0o700)
        _certificates({'atlas.localhost', 'jacket.localhost'}, tls)
        (tls / 'key.pem').chmod(0o600)
    return path, tls, directory
