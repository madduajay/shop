# Poppy and Browser traces

The separate Thread demo is running at https://atlas.localhost:8443/ with its trace page at https://atlas.localhost:8443/traces. FORME is https://jacket.localhost:8443/shop. Original port-443 apps remain intact.

The trace page displays Poppy discovery, session-token, device authorization, revocation and browser-session handoff HTTP exchanges, plus actual controlled-browser commands and observed results. Each card explicitly says Poppy or Browser. Request and Response remain visible; only metadata expands. Standalone GPT calls, internal events and ordinary storefront HTTP traffic are hidden from this page but retained in underlying diagnostics. No HTTP exchange is fabricated for browser commands.

New records capture application payloads without arbitrary length/list truncation, with authentication secrets masked before storage, unique correlation IDs, request/response timestamps, direction, endpoint, status and provenance. Binary bodies are identified rather than decoded. Historical missing payloads cannot be reconstructed. Website handler observations explicitly distinguish handler execution from independently proven network transport. Commerce is always synthetic.

Current validation:
- Trace/auth/isolation and routing checks: 11 passed; additional trace path coverage: 4 passed.
- Actual GPT headless trace browser fixture passed, with 2 model calls plus 1 company explanation call; desktop/mobile and archive navigation checked; all 100 fixture profiles unchanged and zero orders.
- Exact “show me a red tie” then “yes” passed with actual GPT enabled. Reply proceeds to authorization. Availability wording/routing is deterministic; real GPT was independently called for the profile probe. No subscription was activated and no order created.
- Live browser reload retained Alex's login. Live trace page displayed the final Poppy/Browser scope and all 13 archive links.
- Before/after database hashes match for 100 profiles/accounts/addresses, existing bag/reviews, 6 orders, context and all 13 archives. The 12 pre-existing archive rows also match their pre-clear hash. The approved current chat was archived once; no unsent draft existed.
- Existing local CA/certificate reused with TLS verification; no OS trust changes or new credentials.

Evidence: evidence/trace-pairs/ contains sanitized paired exchanges, fixture model evidence, red-tie-check.json, screenshots, preservation hashes, and regression logs. An initial broad regression run stalled in a browser worker and was interrupted, not counted as a pass; a logged rerun records its final result separately. The earlier routing-only suite passed 287 tests; do not conflate it with this updated build.

Final regression coverage: all 289 collected cases passed across segmented runs (227 completed before the screenshot stall, the isolated browser/assertion case passed in 16.78s after binary capture handling, and the remaining 62 cases passed in 10.54s, with one overlapping filter case). No reported assertion failures; the initial monolithic runs were interrupted and are not represented as completed suites. Final live PID: 43302.
