# Remaining validation prerequisites — local continuation

## Expired certificate cleanup — now verified

At 2026-10-23 19:13 UTC, Keychain Access had no pending save dialog. Native details and an escalated read-only query verified the exact old certificate fingerprint 5de00475f0e727621fcaac0f00d5874509e87276b8b7b9b0eb0196e614e29d08 and user SSL trust. The certificate expired at 09:48:52 UTC. Under the existing exact cleanup authorization, deletion of that certificate was confirmed in Keychain Access. The delete action timed out; a subsequent independent query still found both the exact certificate and user trust. A fresh Keychain Access observation also timed out. The native delete was not repeated. Evidence: audit/local-resume-trust-readonly.json and audit/local-resume-cleanup.json.

Resolution at 19:19 UTC: the deletion subsequently completed without retry. Independent read-only queries confirm exact certificate/trust absence, and native Keychain Access shows no matching results or pending dialog. No old-cleanup user action is needed now. A fresh constrained fixture is prepared but not trusted; public details are in audit/fresh-browser-trust-request.json. New trust requires its own action-time confirmation. The expired certificate must never be reused.

## Corrected browser cases

Two legacy-SSE fixtures have webhook mode explicitly disabled: test_availability.py::test_watch_browser_flow and test_availability.py::test_restart_reconnect_inbox_and_expiry. Six non-browser SSE contract checks passed, but these browser journeys still require rerun. The previous complete browser suite remains 477 passed, 2 failed, 13 skipped. No rendered rerun is claimed.

A fresh isolated HTTPS arrangement preserving browser and Poppy TLS validation is required. No supported profile-only CA arrangement has been verified on this Mac. Installing another temporary user SSL root would require a new exact certificate/fingerprint, validity, scope and cleanup confirmation at action time. Do not use warning bypasses, TLS overrides, original private keys, original browser state or the denied Terminal UI route. Old cleanup is now verified; obtain fresh exact trust confirmation before browser execution.

## Actual-model test opt-in prepared, not executed

All 13 cases are listed in audit/remaining-blocked-cases.md. No original credentials were read/copied and no API calls were made. Default tests strip OPENAI_API_KEY, disable LangSmith tracing and deny external sockets.

The implemented opt-in is --thread3-live-model plus an explicit --thread3-model-max-requests N (1..50 for the entire pytest session). It requires a key supplied securely only to that process. It rejects endpoint/proxy overrides and model changes, permits only resolved api.openai.com addresses on port 443 beyond loopback, checks HTTPS POST endpoint/model/store=False/non-streaming/one completion, bounds request bytes to 131072 and output tokens to 1200, and counts failed attempts too. The Deep Agents production provider now explicitly sets store=False. ModelBudget contains no credential. Unit/provider-contract tests are synthetic and require no API access.

Minimum first approval: one test_conversation_images.py::test_real_gpt_local_context smoke test, process-only user-supplied API key, documented model gpt-4.1-mini-2025-04-14, HTTPS api.openai.com, at most 20 requests, each at most 131072 request bytes and 1200 output tokens. This is a quantity cap, not a guaranteed dollar cap; provider billing depends on actual usage. Do not assume an API budget or ask for a key in chat. The user must authorize these calls and supply the key securely before execution. No .env file, persistent credential, grant or copying original configuration is authorized. The other 12 cases also require browser prerequisites. Further bounded batches need explicit remaining budget.

Prepared smoke command, after authorization and secure process-only key injection:

    .venv/bin/python -m pytest -q --thread3-live-model --thread3-model-max-requests 20 test_conversation_images.py::test_real_gpt_local_context

No such live-model command has been run. Full functional acceptance remains open.


## Latest browser result and cleanup blocker

All browser cases now pass in the final complete aggregate: 514 passed, 0 failed, 13 actual-model blocked (527 cases, audit/local-browser-final-verified.xml). New CA 40e16e70c2b2 was explicitly approved, committed and verified for both hostnames. The Mac then locked. One exact CLI delete-with-trust operation timed out; independent read-only checks still find the exact certificate and trust at 19:48:31 UTC. Native removal awaits manual unlock/authentication. Do not repeat the uncertain delete; check outcome after unlock first. Cleanup remains unverified; see audit/new-ca-cleanup.json. This supersedes earlier browser rerun prerequisites above. No new grant is needed for the already approved exact removal. The remaining 13 live-model cases still require secure ephemeral credential supply and explicit capped API authorization.
