# Explicit shopping requirements

Status: LIVE and verified on 18 October 2026, PID 53682. No remaining blockers.

The original live “Show me shirts, Size L only” request was correct: browser request/response both had apparel_size=L, with L stock 8 for Essential Crew Tee and 3 each for Pine and Cliff Guayabera-inspired Shirts. Selection uses current request size before saved Thread size. No live add was performed. The visible cards previously omitted selected size.

Changes:
- Original request requirements are extracted before model rewrites can alter them; supported size, positive/negative colors, fit, style/design family, material, category and decimal price bounds are applied together.
- Every returned product is checked against the requested attributes, price and in-stock size before displaying. The browser refuses a form assignment that silently loses a requested value.
- Current positive color overrides a saved exclusion; refinements retain explicit constraints and an existing minimum price unless changed. Unsupported/ambiguous fits, styles, size or category combinations ask for clarification rather than selecting substitutes.
- “Under/below/less than” excludes the boundary by one cent; “up to/at most” includes it. Decimal cents are preserved.
- Thread-originated requests do not inherit FORME saved preferences, behavior ranking or shared request envelopes.
- Cards show a clear “Size L · In stock” badge, with selected size in product details. Response copy refers to current requirements.
- Before adding, the agent reopens the product page and rechecks the exact variant and all requirements. Pending sign-in retains the requirement snapshot; expired searches cannot add.
- Availability candidates respect the same price/category requirements. No real payment or delivery is used.

Evidence: evidence/explicit-constraints/live-L.json, result.json (actual GPT), ui-result.json, size-L-desktop.png, size-L-mobile.png, and test logs. Tests use isolated data; an actual browser add is confined to fixture customer 1 and checked against customer 2, while all 100 fixture profiles remain unchanged. No fixture checkout occurs in the new constraint tests (older full-suite checkout regressions remain synthetic and isolated).

Limits: this is a bounded clothing-catalog demo, not a guarantee of perfect interpretation of arbitrary language or physical fit. Stock and size labels are synthetic; the same representative product photograph can cover multiple sizes. Unsupported or conflicting requests should clarify or return no match, not silently relax requirements. Restarts require a recoverable conversation archive; saved profiles, bags, orders and previous archives must be preserved.

## Final verification and activation

The maintained suite finished with 313 passed and one stale strict-price expectation. Only that corrected integration test was rerun: 1 passed in 16.95 seconds. Thus all 314 maintained cases have passing results, with zero unresolved failures. Logs: `final-suite.log` and `final-recheck.log` (these deliberately retain the initial failure rather than implying one all-green invocation). Initial broad collection mistakenly included copied historical evidence scripts; those are not maintained tests. Actual GPT: 6 scenarios, 8 real calls, 100 fixture profiles unchanged, zero orders. Desktop/mobile size badges and details passed with actual GPT, plus JS syntax checks.

Live browser verification: white Guayabera shirts, L, regular fit, $70.50–$81.50 returned 3 matching products. Refining to under $80.25 retained every other constraint and the $70.50 minimum, returning 2 products. Red/XXXL returned no products. Actual rendered trace data was checked with the same attribute/price/stock validator. Product details showed Size L; no add/checkout was clicked.

Recoverable archive `10ce1c7a3735b095cdd18b1d327e5fc5` contains the previous L request, its response and 17 trace events. Prior 17 archive rows are byte-for-byte unchanged (18 total). Hash checks preserve all 100 profiles, 6 existing orders, the current cart, 3 reviews, 100 accounts and delivery records, company preferences and purchase-memory keys. The original port-443 apps returned HTTP 200. The archived chat is available through Past chats; the live verification conversation remains open.

Activation proof: `evidence/explicit-constraints/activation/result.json`, `live-browser.json`, before/archived/after hashes, and `live-size-L.jpg`. URLs: https://atlas.localhost:8443/ and https://jacket.localhost:8443/shop.
