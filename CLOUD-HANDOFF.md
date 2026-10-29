# Cloud continuation checkpoint — 2026-10-23

This is the isolated Thread3 source, using genuine Deep Agents 0.7.24 and LangGraph 1.2.14. Functional parity remains OPEN. Preserve this acceptance requirement; scripted tests do not establish actual-model parity.

## Contents and topology

The isolated FORME counterpart is integrated in app.py, store.py, commerce.py, purchase_flow.py and the bundled private Poppy SDK, rather than in a separate FORME3 directory. The same ASGI app serves atlas.localhost (Thread3) and jacket.localhost (FORME test store) by hostname. It binds loopback only, with ports 8543 and 8545 allowed. Every setup creates independent synthetic state, identities, SQLite storage and temporary TLS. All 100 customer profiles, five workflows in agent_skills, all 19 business tools, UI assets, browser.cjs and tests are included. Poppy 0.16.0/protocol 0.2 source and license are bundled in vendor/poppy02; no private package repository is required.

No original Thread/FORMe database, .env, credential, OAuth grant, browser cookie/profile, approval, private trace or key is included. Original source manifest is read-only provenance. Mac-local virtualenv and Python interpreter are excluded. Do not use original Mac resources or run run_trusted_browser_tests.py in cloud: it is a Mac-only historical helper retained because test_trust_cleanup.py mocks its control flow. Its old certificate has expired and is not included.

## Verify and install

Verify the whole ZIP SHA-256 against the separately delivered receipt before extraction. Compare every extracted source file against HANDOFF-MANIFEST.json; reject unexpected paths. Python >=3.12, Node >=22, and Chrome/Chromium are required. requirements.lock.txt is an exact installed dependency snapshot with no editable/local checkout references. It passed pip check on Mac; clean Linux installation remains UNVERIFIED.

```sh
cd thread3
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip check
mkdir -p audit evidence/commerce-images
.venv/bin/python -m pytest -q --junitxml=audit/cloud-default.xml
```

Default tests strip ambient OPENAI_API_KEY, disable LangSmith tracing, deny external sockets and skip real socket/browser cases. Synthetic fixtures never reach real commerce. Socket-only checks use `--thread3-live-sockets` in the supported cloud execution environment. THREAD3_CHROME selects the browser executable. Browser fixtures additionally require `--thread3-live-browser` and a freshly generated/validated THREAD3_TLS_DIR; tls_fixture.py generates it. The cloud agent must establish supported HTTPS routing and trusted TLS inside its isolated cloud browser environment. Do not disable TLS validation, use warning bypasses, import Mac certificates or change Mac trust. The Linux browser/DNS/TLS setup is not yet validated. A generic preview hostname alone will not preserve this two-origin protocol.

Prepared server command is `THREAD3_PORT=8543 .venv/bin/python app.py`. Candidate app URLs are https://atlas.localhost:8543 and https://jacket.localhost:8543; no persistent runnable cloud URL is verified yet. Confirm app.setup, both HTTPS origins, auth, rendered pages and cleanup before reporting a runnable URL.

## Test evidence and next steps

Latest complete real-Chrome Mac run: 477 passed, 2 failed, 13 skipped across 492 expanded cases. The two failures were legacy SSE test fixtures running webhook mode. test_availability.py now explicitly disables webhooks in test_watch_browser_flow and test_restart_reconnect_inbox_and_expiry; their browser rerun is OUTSTANDING. Six additional non-browser SSE checks and three mocked cleanup-guard checks passed separately. See audit/cloud-validation.json for exact case results. Do not add these separate totals to the older complete-suite result or describe the two browser failures as passed.

The 13 actual-model cases remain skipped: one each in test_add_queue.py (two tests), test_agent_tools.py, test_conversation_images.py, test_exact_add_gpt.py; three test_planner_diagnosis.py cases; three test_product_identity.py cases; two test_watch_consent_gpt.py cases. No model credential was copied. conftest.py currently unconditionally removes OPENAI_API_KEY and restricts network to loopback. A securely supplied ephemeral credential, explicit live-model opt-in, provider-only network scope and bounded test budget must be authorized separately (now implemented in the later local source; the already uploaded archive predates this change) before those cases can run. Do not relax default isolation. The production default model is gpt-4.1-mini-2025-04-14.

Prioritize clean installation, corrected two SSE browser reruns, related live webhook/SSE/refresh regressions, all-profile isolation, failure/restart/duplicate-effect checks and actual-model differential behavior. Keep case statuses passed/failed/unrun/blocked accurate. No real purchases, external messages, public deployment, new persistent credentials or original-data changes are authorized.
