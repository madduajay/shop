# Portable source handoff

Read CLOUD-HANDOFF.md first. Rebuild the source-only ZIP with `python build_handoff.py` from this directory. The ZIP contains HANDOFF-MANIFEST.json with SHA-256 hashes and sizes for each included file, and has a separate whole-archive SHA-256 sidecar.

The user authorized private Library transfer for cloud coding and browser testing. No public repository or deployment is authorized. Upload receipt and whole-archive checksum are reported separately because embedding them would change the archive checksum.

No virtual environment, original application state, credentials, active grants, database, browser profile, private trace, TLS certificate or private key is included. Source tests contain synthetic fixture passwords and dynamically create synthetic tokens/keys. These are test logic, not copied access credentials. Existing static demo imagery is included for visual parity.
