# Thread3

Separate synthetic Thread/FORMe application using **Deep Agents 0.7.24** and LangGraph 1.2.14. This is an interim implementation checkpoint, not a verified functionality-parity release.

## Start the shop with its own API key

The live launcher now reads `OPENAI_API_KEY` from its launch environment, or from
`.env` in this shop directory when the environment value is empty. It no longer
requires the original Thread service or reads credentials from another process.
This supersedes the historical key-source instructions below.

Copy `.env.example` to `.env` if `.env` does not already exist. Set
`OPENAI_API_KEY` to your own key in that file using a local editor, then run
`chmod 600 .env`. Do not paste the key into chat. `.env` is ignored; the launcher
loads only its API key, without environment-variable interpolation, and never
records the key in runtime metadata. Environment configuration takes precedence.
This follows [official OpenAI guidance on server-side API keys](https://developers.openai.com/api/reference/overview#authentication).

```sh
cd /Users/ajaybabum/Documents/Codex/shop
.venv/bin/python launch_live_demo.py --serve-live --tls-dir "$PWD/.local-live-tls/2767617c4da7" --port 8545
```

Keep the terminal open. Shop: <https://jacket.localhost:8545/shop>.
Thread chat: <https://atlas.localhost:8545/>. Press Ctrl+C to stop.
The existing native TLS trust, saved synthetic state, and cumulative $50 ledger
at `audit/live-spend-20261024.sqlite` remain in use. Never reset that ledger.
Missing or malformed key configuration stops startup before the server starts.

Poppy discovery appears under **Behind the conversation → Poppy** when Thread
opens a FORME connection. Clear chat archives those exchanges while retaining
the connection and bag. The next non-greeting request fetches fresh discovery
documents for the new trace, without opening another session or resetting the
browser. Later requests in the same conversation reuse that discovery.

## Latest local continuation

**Restored October 25 and left running:** [Thread3](https://atlas.localhost:8545/) and [FORME3](https://jacket.localhost:8545/shop). Synthetic demo login: `customer001@thread.local` / `wardrobe`. Normal-TLS Chrome login → real GPT → Deep Agents business tool → rendered reply was verified in the final saved-state application. PID **32806**, execution session **78006**; current runtime metadata is in `audit/live-demo-process.json`.

Fresh full suite: **550 passed, 2 wording-assertion failures, 0 skipped**. Both corrected checks now require canonical source facts and equivalent size wording, retain every no-write/isolation assertion, and passed their live reruns. Effective coverage is **552/552 tracked cases passed**. This is finite evidence, not a guarantee about every future model response. See `audit/three-month-final-case-matrix.json` and `STATUS.md` for the raw and rerun results.

The approved three-month SSL CA `2767617c4da7` is constrained to `atlas.localhost` and `jacket.localhost`. The CA and leaf expire **January 25, 2027 at 4:14:05 p.m. Arizona time**. The expired prior certificate and trust are verified removed; the new SSL-only login-keychain trust is retained for continued use. Generated TLS files are in ignored `.local-live-tls/2767617c4da7/`, with owner-only permissions. The CA signing key was discarded. No certificate-warning bypass is used.

The application stops one minute before certificate expiry (**January 25 at 4:13:05 p.m. Arizona time**), or when its process or Mac stops. No OS startup service was installed. Manual relaunch from this directory requires the original Thread key-source service to be running:

```sh
.venv/bin/python launch_live_demo.py --serve-live --tls-dir "$PWD/.local-live-tls/2767617c4da7"
```

Saved profiles, preferences, carts, orders and archives remain in ignored `.local-live-state/`. Original wardrobe code and services are untouched. The API key is borrowed only in process and never persisted; browser children exclude it. All calls share the existing cumulative **US$50** gate at `audit/live-spend-20261024.sqlite`; never reset that ledger. At final verification, 3,163 attempts priced to **US$1.775652**, with zero outstanding reservations. Actual billed cost is unavailable; future use increases this estimate within the same gate.

**Future gap:** the current `gpt-4.1-mini-2025-04-14` snapshot is scheduled for removal on **January 14, 2027**, before TLS expiry. Provider migration is required before then; no silent replacement was made. [Official OpenAI deprecation notice](https://developers.openai.com/api/docs/deprecations). Historical sections below retain their dated scope.

## Verified checkpoint

- Original business baseline: **332 passed, 32 blocked** after repairing two source-test fixture issues.
- Latest complete trusted-Chrome run: **477 passed, 2 failed, 13 blocked** across 492 expanded cases. The two failures are legacy-SSE fixtures using the default webhook mode; their fixture configuration is corrected and needs a browser rerun. Three additional cleanup-guard tests passed afterward.
- All 19 original business tools and five workflow documents retained. The old planner loop is replaced by `create_deep_agent`; its historical copy is confined to `audit/baseline-agent-tools.py.txt`.
- All 100 profiles pass graph preference/owner isolation checks. Real graph execution, authenticated chat API, LangChain provider parsing, consent pauses/resume, completion evidence, duplicate suppression and checkpoint reopening are tested.
- No original source files changed: all 277 inventoried hashes match. No original databases, credentials, tokens, profiles or TLS keys were copied or opened for writing.

See [PARITY.md](PARITY.md), [STATUS.md](STATUS.md), and [HANDOFF.md](HANDOFF.md). Detailed results are in `audit/verification.xml`, `audit/case-results.json`, `audit/test-cases.json`, and `audit/verification-summary.json`.

## Run isolated tests on this Mac

```sh
cd /Users/ajaybabum/Documents/Codex/2026-10-22/task/thread3
.venv/bin/python -m pytest -q --junitxml=audit/verification.xml
.venv/bin/python -m pip check
```

By default, the test harness removes ambient OpenAI credentials, blocks non-loopback socket connections, and marks socket/Chrome tests blocked before starting them. The approved `--thread3-live-sockets --thread3-live-browser` run used a separate validated temporary certificate with full TLS checks; no bypass flags were used. Additional ASGI tests explicitly use in-process transports and synthetic consent. Scripted model providers live only in test fixtures; they are not a production agent fallback.

## Clean environment setup

Python 3.12+, Node 22+, and Chrome/Chromium are needed for the complete app. Pure HTTP/graph tests do not need Chrome. This dependency snapshot passes `pip check` locally; clean installation on another OS has not been verified.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pytest -q
```

Private Poppy 0.16.0/protocol 0.2 is bundled under `vendor/poppy02`, with its license. Do not substitute the older public checkout. No dependency on the original application source remains. The current Mac virtualenv uses an existing read-only Python 3.12 interpreter; the virtualenv itself is excluded from the handoff.

## Local application status

No runnable URL has been verified. Candidate origins are `https://atlas.localhost:8543` and `https://jacket.localhost:8543`, with 8545 reserved for tests. The app binds loopback only. Other ports are rejected. Every cloned cookie has a Thread3-specific name because browser cookies ignore ports. Chrome uses a fresh temporary profile and incognito context.

`App.setup()` creates temporary synthetic databases, signing identities and a temporary CA/leaf certificate. It does not install trust, change DNS, or load the original TLS keys. The app needs an explicitly approved Thread3 TLS/DNS arrangement and socket access for real-browser verification. Any durable credential/grant setup still requires specific authorization. The default sandbox restricts socket binding; the supported approved execution path permits it and resolves both existing names to loopback. No DNS change is needed. The temporary approved certificate was removed after the browser run, and exact-certificate/trust absence was independently verified.

Once those blockers are resolved, `THREAD3_PORT=8543 .venv/bin/python app.py` is the prepared launch command. It is not a verified launch instruction yet. `THREAD3_CHROME` can select a Chrome/Chromium binary; otherwise common Mac/Linux locations are checked. The original deterministic no-model business fallback is retained; actual Deep Agents language planning requires a model configured explicitly for Thread3. Do not copy an original `.env` or obtain new persistent access implicitly.

## Runtime boundaries

`deep_runtime.py` supplies the real Deep Agents graph. Only the business tools, requirement planning, and conditional evidence-based completion are advertised. Shell, general filesystem, todo, and subagent capabilities are excluded. The necessary internal `read_file` registration is hidden and denied at the execution boundary.

Business authorization remains server-owned. Runtime limits are 16 model turns, 12 business effects and 90 seconds across consent continuation. Exact current-message checkout approval, stock/price/variant validation, stale-review rejection and browser-only bag mutations remain in the preserved business implementation.

`checkpoints.py` stores typed LangGraph checkpoints and durable effect claims in a separate SQLite database. Clients, browser handles, signing keys, OAuth tokens and cookie stores stay outside graph state. Model-visible results are scrubbed. A previously claimed uncertain action is not replayed. Recovered pending requests require fresh review; clear-chat cancels the saved graph. Existing archives are read-only.

No deployment, external publication, purchase, external messaging or upload has been performed.

Latest complete socket-enabled run: **463 passed, 0 failed, 29 blocked**, across 492 expanded cases (`audit/socket-enabled-suite.xml`). Native DNS and loopback HTTPS work through the supported approved execution path. Both reverse identity-fetch failure cases and the independent device/conversation/revocation case now pass over real HTTPS. The ASGI Flow.chat entrypoint refresh-before-graph check and temporary TLS validation checks also passed. Remaining cases are listed individually in `audit/remaining-blocked-cases.md`. See `TRUST-REQUEST.md` for the exact pending browser trust request; no trust or DNS changes have been executed.

Latest native browser evidence: `audit/browser-enabled-suite.xml`, `audit/browser-case-results.json`, and `evidence/store-mobile.png`. Cleanup after CLI timeouts succeeded through native Keychain Access; `audit/current-trust-state.json` confirms both certificate and trust absence. Production behavior remains unchanged by the SSE test-fixture correction. No trusted browser service is currently left running.
