# Concise availability copy

Before opt-in: “Red shoes are not available. Would you like FORME to notify you when they’re available?”

After authorized watch activation: “Red shoes are not available. FORME will notify you when they’re available.”

Red tie uses singular grammar. Other catalog watches retain the actual product name. Repeated offers and active-watch replies use the same concise copy. Required authorization remains explicit and no watch is created before consent and authorization.

Only customer-facing copy and corresponding expectations changed. The 60-second timer, actionable notification, cancellation, persistence, customer isolation, duplicate prevention and checkout approval are unchanged.

Verification: availability suite 25 passed in 75.35 seconds; final copy/generic-name checks 2 passed (24 deselected). Existing headless UI script assertions updated and JavaScript syntax checked, but its real-minute UI scenario was not rerun for this copy-only change. Browser integration covers consent, invalid sign-in, authorized activation, repeat requests, notification delivery, cancellation and restart recovery using isolated fixtures. Evidence: `evidence/availability-copy-tests.xml` and `evidence/availability-copy-readiness.json`.

Activated with fresh user approval on 2026-10-18; separate demo PID 24428. Current chat was archived before restart (11 messages, 36 trace entries). All ten archives are durable, including the unchanged prior nine. Before/after record checksums match for 100 profiles, FORME preferences, accounts, addresses, carts, reviews and six orders. Thread remained signed in; composer was empty. No live subscription or order was created. Post-activation isolated browser suite: 26 passed in 75.50 seconds, including exact copy, consent/authentication, timing, actionable notifications and restart recovery. Live TLS health checks passed for this demo and both original apps. Historical messages retain their original text. See evidence/availability-copy-archive.json, availability-copy-post-activation.xml and availability-copy-readiness.json.
