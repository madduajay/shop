# FORME My preferences

## User-facing behavior

`/shop/preferences` is available from the FORME navigation and account page. Guests are sent through normal FORME sign-in and returned to the editor. The responsive form has catalog-backed collection, US clothing/waist/shoe sizes, colors, excluded colors, fit, style, design family, materials, brands, quality, occasion and budget controls. Colors and brands allow multiple selections. Collection changes refresh size and design-family options without silently converting existing selections. Existing non-catalog choices remain visible until deliberately changed. Individual Clear buttons remove only that choice when saved.

Saving uses the existing authenticated FORME account, existing CSRF/origin protections, server-side catalog validation and the existing durable explicit-memory store. A revision check prevents stale forms overwriting another tab's edits. Unedited fields and fields outside the editor are preserved. Invalid values, contradictory colors and invalid budget ranges are rejected. Temporary constraints, inferred interests, Thread profiles, identities, addresses, bags and orders are not edited by the form. Controlled browser sessions retain existing read/write scope enforcement; no permissions were expanded.

## Strict ownership and reflection

Direct FORME shopping uses FORME-owned saved preferences. Current explicit storefront filters take precedence. Multiple favorite colors/brands and design family influence recommendation ordering; sizes, budgets and exclusions constrain eligibility.

Thread shopping uses only Thread-owned saved preferences plus the current chat request. Its filter form carries an application-level `preference_source=thread` marker within the authenticated controlled-browser session. FORME excludes its saved and inferred preferences from that search and from recommendation explanations. The marker does not bypass authentication and has no such effect for ordinary direct storefront requests. The controlled browser clears previous form values before submitting a fresh search to prevent stale FORME defaults reappearing. Automatic copying of Thread preferences into FORME during shopping is disabled. Explicit commands addressed to FORME stage only those explicitly supplied company values without updating the Thread saved profile.

When asked to show FORME preferences, Thread performs an authorized controlled-browser read of the currently linked account, with source, revision and update time. It replaces its transient view on every requested read; clears therefore disappear. It never imports that view into Thread's saved memory or general personalization prompt. Expired/revoked access requires normal reconnection on demand. A mismatched linked account is rejected. There is no background synchronization: changes appear on the next authorized FORME-preference request in Thread or fresh direct FORME storefront load. Existing historical chat messages remain historical.

## Verification and activation

Headless Mac Chrome verifies guest sign-in return, dropdown coverage, multiple colors, save feedback, reload persistence, individual clearing, desktop layout and mobile overflow. Isolated integration tests cover server validation, CSRF, account isolation, persistence across a new application instance, authorized Poppy reads, edit/clear revision refresh, expired/revoked access, and conflicting preferences across the two surfaces. See `evidence/preferences-ui.json`, `preferences-ui-model.json`, `preferences-focused.xml` and `preferences-regression.xml` for exact outcomes.

Final regression: **278 passed, 0 failed, 0 skipped**, in 154.18 seconds. Earlier focused/full runs exposed assertions for the superseded automatic-sharing behavior; those expectations were updated and the final full run passed. The headless editor fixture preserved all 100 Thread profiles and its empty cart, created no orders, and required no agent authorization grant.

Screenshots: `evidence/preferences-desktop.png` and `evidence/preferences-mobile.png`.

Activated after fresh user approval on 2026-10-18. The current conversation was durably archived (nine archives total; previous eight unchanged), and the separate demo restarted as PID 23255. The live preferences page was verified in Chrome; Thread remained signed in and its unsent draft was restored. Post-activation integration checks: 2 passed in 7.93 seconds. Disposable desktop/mobile UI checks passed again. Before/after checksums confirm all protected profiles, FORME preferences, identities, addresses, carts, reviews and orders unchanged. No additional account scopes were granted. Existing controlled-browser sessions reconnect through normal authorization when next needed; no forced live grant was performed. Refresh existing storefront tabs to load the new navigation. Evidence: `evidence/preferences-activation-archive.json`, `preferences-pre-activation.json`, `preferences-post-activation.json`, `preferences-post-activation.xml`.

Limits: the catalog uses US sizes; no unverified international conversion is offered. Design family is a single preferred choice. The multi-select controls use native platform behavior. Product availability may mean no matching items even for valid preferences.
