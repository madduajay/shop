# Feature-rule parity matrix

Current local verification: **552/552 tracked cases passed across the final aggregate and separate genuine-model runs**. The final Chrome aggregate passed529 cases and skipped23 model-dependent cases; all23 have separate live passing evidence. Requested30 browser cases all pass after affected fixes/reruns. See audit/final-combined-case-matrix.json and audit/final-30-case-matrix.json. This is finite case coverage, not a guarantee of every future model output. User-facing live demo is verified; exact temporary CA cleanup remains pending the user finishing their testing. Earlier counts below are dated historical evidence.

The two initial baseline failures were fixture problems: an incomplete device response double and an omitted historical catalog snapshot. The clean baseline recheck repairs only those fixtures, uses the original custom planner, and does not exercise the new graph. Eight original planner cases were migrated from custom-loop mocks to the real graph while retaining their behavioral assertions.

| Required case | Status | Evidence / limit |
|---|---|---|
| Original source preservation (277 hashes) | passed | audit/differential.json |
| 19 business tool schemas and executor | passed | Registry preserved; original executors retained with a catalog adapter fix preserving unsupported-category routing. New request-scope boundaries prevent stale private-bag routing. |
| Five workflow load/reselect gates | passed | test_deep_runtime.py; agent_skills/ |
| Real Deep Agents graph and conditional finish | passed | test_real_deepagents_identity_and_conditional_tools |
| Authenticated chat HTTP → provider adapter → graph → tool | passed | test_deep_http_api.py (mock provider transport) |
| 16-turn / 12-effect / 90-second stopping rules | passed | test_model_turn_limit_without_business_execution; test_twelve_tool_effect_limit; test_elapsed_limit_stops_after_verified_effect |
| Evidence rejection and no-progress/duplicate suppression | passed | test_planner_completion.py; test_agent_tools.py |
| 100 synthetic profiles: persistent memory isolation | passed | test_wardrobe.py::test_memory_isolation_and_persistence [100 cases] |
| 100 synthetic profiles: graph preference/owner isolation | passed | test_deep_runtime.py::test_all_profile_graph_identity_and_preference_isolation [100 cases] |
| Persistent/temporary preferences, source separation and exclusions | passed | test_constraints.py; test_color_exclusions.py; test_context_qa.py; test_preferences_page.py (isolated logic/HTTP subset) |
| Catalog imagery, filtering and constraints | passed | test_photo_coverage_and_preserved_catalog; test_filters; test_constraints.py |
| Rendered imagery, pagination, filter UI and card selections | passed | final-chrome-aggregate.xml; final-30-case-matrix.json |
| Exact variants, stock/price recalculation and direct cart isolation | passed | test_commerce.py; test_purchase_flow.py (HTTP/logic subset) |
| Browser-driven bag additions/update/removal and resume | passed | Real Chrome and genuine-model journeys; exact variants, price/stock changes, authorization resume and duplicate checks |
| Direct synthetic checkout review, explicit consent, stale review and duplicates | passed | test_commerce.py::test_direct_cart_checkout_persistence_and_isolation |
| Forged checkout language rejected by graph | passed | test_checkout_cannot_be_forged; test_confirmation_cannot_be_forged |
| Rendered checkout and exact-card purchase journey through new planner | passed | real-agent-journey-final.xml; browser-live-catalog-recovery-final.xml; fictional checkout only |
| Thread authentication, archives/reset and identity spoof rejection | passed | test_thread_auth.py; test_deep_http_api.py |
| Poppy session, CIMD/JWKS, DPoP, device consent and revocation (ASGI) | passed | test_protocol_asgi.py::test_asgi_device_conversation_and_revocation |
| Negative browser activation signature/audience/subject/expiry/return/replay checks (ASGI) | passed | test_protocol_asgi.py::test_asgi_browser_activation_negative_assertions |
| Account-token refresh/renewal through new harness | passed | test_protocol_asgi.py Flow.chat refresh-before-graph check; lifecycle/revocation and actual HTTPS fixture checks in final aggregate |
| Poppy live HTTPS discovery, OAuth and Chrome browser activation | passed | final-chrome-aggregate.xml; requested30 Chrome/model journeys; exact approved CA and normal TLS validation |
| Availability offer requires new explicit consent turn | passed | test_waiting_for_explicit_watch_consent_stops_graph; original isolated watch-rule tests |
| Availability timer persistence, owner isolation, expiry and cancellation/dismissal logic | passed | test_availability.py isolated subset; test_notification_dismissal.py; test_watch_expiry.py |
| Signed webhook authentication, ownership, digest, replay and event dedup | passed | test_webhook_offline.py |
| Poppy conversation acceptance retry/restart/idempotency | passed | test_protocol02_resilience.py |
| Live HTTP webhook durable retry and legacy SSE delivery | passed | Both corrected legacy SSE journeys and authenticated HTTP webhook503/retry/dedup checks pass in final browser evidence |
| Graph consent pause/resume without repeated effect | passed | test_authorization_resume_does_not_repeat_business_tool |
| Checkpoint reopening, uncertain claims and restart review guard | passed | test_reopen_checkpoints_and_effect_claims; test_crashed_claim_blocks_reexecution; test_new_flow_recovers_pending_graph_without_replaying |
| Clear conversation invalidates graph replay | passed | test_clear_conversation_cancels_graph_checkpoint |
| Secret masking, trace authorization and payload rendering | passed | test_trace_page.py; test_secret_scrubbing_and_live_object_rejection |
| New real-provider HTTP trace hook on real model network | passed | Genuine OpenAI calls, measured spending ledger, actual UI verification and key-free artifact scan |
| No shell/filesystem/subagent tools exposed to model | passed | test_real_deepagents_identity_and_conditional_tools; test_model_turn_limit_without_business_execution |
| Independent origin/port/cookie/browser/DB/checkpoint configuration | passed | ports 8543/8545 only; Thread3 cookie namespace; isolated fixture paths and profile controller; static/config checks |
| Clean dependency consistency on connected Mac | passed | pip check; pinned installed snapshot |
| Fresh cloud installation and full rendered application | unrun | Source handoff prepared locally; no environment transfer performed |
| Actual-model differential functionality parity | blocked | No live model use configured or executed for Thread3; rendered environment pending |

## Tool inventory

The following are the 19 preserved business tools. `plan_request` is a separate planning gate; `finish_request` is conditional on current-request evidence.

| Tool | Workflow |
|---|---|
| `thread_user_context` | identity-preferences |
| `forme_user_context` | identity-preferences |
| `read_thread_user_data` | identity-preferences |
| `read_user_preferences` | identity-preferences |
| `read_forme_orders` | identity-preferences |
| `read_forme_bag` | bag-management |
| `read_forme_user_data` | identity-preferences |
| `unsupported_question` | Read-only unsupported/clarification gate |
| `catalog_search` | product-discovery |
| `product_details` | product-discovery |
| `update_preferences` | identity-preferences |
| `add_to_bag` | bag-management |
| `update_bag_item` | bag-management |
| `remove_bag_item` | bag-management |
| `availability_notifications` | availability |
| `connection_status` | identity-preferences |
| `checkout_review` | checkout |
| `confirm_checkout` | checkout |
| `queued_additions` | bag-management |

## Reports

- `audit/test-cases.json`: all 128 original function requirements, with expanded-case counts and current status.
- `audit/case-results.json`: all 489 collected parameterized cases with reasons for blocked cases.
- `audit/verification.xml`: current full run, 457 passed / 32 skipped-as-blocked.
- `audit/baseline-recheck.xml`: clean original-planner fixture baseline, 332 passed / 32 blocked.
- `audit/differential.json`: untouched original source hashes and retained executor/resume AST equality.
- `audit/verification-summary.json`: totals, acceptance status and uncollected required work.

No runnable local URL, rendered screenshots, real-model behavior parity, or live TLS conformance is claimed.

Follow-up evidence: the formerly blocked independent protocol test passed over real HTTPS using the approved socket execution path (`audit/live-protocol.xml`). Account refresh now passed at `Flow.chat` before the real Deep Agents graph using an in-process protocol fixture (`audit/refresh-tls.xml`). Chrome trust confirmation is pending; no DNS changes are needed. Full-suite totals above refer to the prior completed run.

Latest complete socket-enabled run: **463 passed, 0 failed, 29 blocked**, across 492 expanded cases (`audit/socket-enabled-suite.xml`). Native DNS and loopback HTTPS work through the supported approved execution path. Both reverse identity-fetch failure cases and the independent device/conversation/revocation case now pass over real HTTPS. The ASGI Flow.chat entrypoint refresh-before-graph check and temporary TLS validation checks also passed. Remaining cases are listed individually in `audit/remaining-blocked-cases.md`. See `TRUST-REQUEST.md` for the exact pending browser trust request; no trust or DNS changes have been executed.

## Trusted-browser follow-up

Full native Chrome run: **477 passed, 2 failed, 13 blocked** (`audit/browser-enabled-suite.xml`). Browser TLS was verified; no warning/certificate-check bypass was used. Live webhook retry/security, legacy Poppy SSE stream/activation, exact-card/cart/stock/price checks, stale-review and duplicate checkout, identity isolation, and rendered catalog/filter/pagination checks passed.

The two failed legacy reconnect tests used webhook mode by default; corrected their fixtures to choose SSE explicitly. Their rerun is still unrun, and the previous failures remain in the report. All 13 remaining skipped cases need an actual model. Cleanup is independently verified (`audit/current-trust-state.json`): the exact approved certificate and its user trust entry are both absent. Three additional cleanup-guard tests pass with all native security calls mocked. Functionality parity remains open.


## Local continuation on October 23, 19:13 UTC

The historical cleanup statement above is superseded: the later native save completed outside the earlier observation window. A new read-only check verified the exact old CA and SSL trust still installed after certificate expiry. No save dialog remained. Exact native deletion was requested under existing cleanup scope, but timed out; subsequent queries still show the exact certificate/trust. Await local authentication completion/cancellation; do not repeat deletion or reuse the expired certificate. See audit/local-resume-cleanup.json and VALIDATION-PREREQS.md. No new trust was installed.

New source adds an explicit live-model test opt-in with endpoint/model/retention/input/output/request-budget guards and default network isolation preserved. Production Deep Agents now explicitly requests store=False. Twenty-three synthetic security/provider contract cases pass; no real model call or credential copying occurred. Functional acceptance, two corrected SSE browser reruns and thirteen actual-model cases remain open.


Final local applicable aggregate: **495 passed, 0 failed, 29 blocked**, 524 expanded cases (`audit/local-final-applicable-suite.xml`). This includes 23 new synthetic request-budget/provider-contract checks. Exact expired certificate and trust cleanup subsequently completed without retry and is independently VERIFIED at 19:19 UTC; no native dialog remains. Browser tests and actual-model cases remain blocked on their separate prerequisites.


Latest complete Chrome aggregate: **514 passed, 0 failed, 13 model-dependent blocked**, 527 cases. The two SSE fixture reruns now pass, as do the new real-browser DOM/image and rendered Thread UI/graph/archive/isolation checks. See audit/browser-final-summary.json and audit/remaining-blocked-cases.md. Temporary trust cleanup is pending verification because the Mac locked; no actual-model parity or persistent runnable URL is claimed.


## Strict-schema live verification checkpoint — 2026-10-24T19:35:36.095018+00:00

The invalid enum selected by profile 046 is resolved: strict=True is now passed to OpenAI business-tool binding. The focused real profile rerun passed, followed by **100/100 profiles passed** in the full genuine GPT rerun (500 API attempts). Authenticated canonical source facts, principal ownership, all other profile preferences, FORMЕ separation and absence of orders were asserted. This supersedes the prior 99/100 result; the earlier failed XML is retained as diagnostic history.

Three additional genuine-model read-only/consent scenarios passed: saved preferences, hypothetical preference changes without mutation, and zero active-watch status without subscription. Preference writing plus authenticated API/archive/restart recovery passed again after strict binding (2/2). Ten unique independent actual-model pytest cases have now passed across saved runs. These checks do not verify browser-dependent live workflows.

Final non-browser aggregate: **509 passed, 0 failed, 40 skipped** (549 cases, 66.55 seconds). Of the 40 aggregate skips, 18 need browser TLS, 12 need both actual model and browser TLS, and 10 are model cases separately verified live. Exact case inventory: audit/skip-categories.json. The previous aggregate had 36 skips; focused profile 046 and three new consent cases account for the four added model skips. Focused offline strict checks:158/158 passed. pip check passes.

Cumulative provider-usage-priced estimate **US$0.8063104**, 1593 API attempts; US$0 outstanding/unknown reservations; US$49.1936896 remains under the shared US$50 gate. Actual billed cost is unavailable. No API call remains active. All 277 original source hashes match, and an exact-key artifact scan found 0 matches.

Browser remains blocked: read-only verification at 19:32:22 UTC found exact SSL trust absent, both hostname checks failing and the Mac locked. No uncertain security operation was repeated. User must unlock and handle any native authorization locally; inspect outcome before further action. The imported exact CA still requires approved cleanup when safe. Existing PID90342 demo remains command fallback with saved state preserved, not live GPT. Full functionality acceptance remains OPEN.


## Verified local live application and complete tracked coverage — 2026-10-24T21:08:40.785746+00:00

Final aggregate:529 passed,0 failed,23 model-dependent skips in552 cases (207.88seconds). All23 skips have separate genuine-model passing evidence; combined552/552 tracked cases pass. Requested30 browser cases are all passed after affected fixes, with earlier failure XML retained. Broad real agent journey passes again after final routing fixes. A separate genuine-model rendered UI checks login/chat/reload/archives/second-identity isolation. Evidence: audit/final-combined-case-matrix.json, audit/final-30-case-matrix.json, audit/final-chrome-aggregate.xml, audit/real-agent-journey-final.xml, audit/real-thread-ui-result.json.

Fixes: public catalog/refinement requests are scoped away from stale private-bag tools; exact checkout selects the original checkout handler and resumes pending authorization/adds; unsupported categories preserve legacy routing; storefront string expiry values are normalized; real Deep Agents transport updates existing model counters. Original business logic remains retained except the narrow unsupported-category dispatch adaptation. Added negative request-scope/unsupported-tool checks pass.

Live GPT app is now running at atlas.localhost:8545 and jacket.localhost:8545/shop, PID97712 (exec90670), loopback only, gpt-4.1-mini-2025-04-14. Verified actual user-facing Chrome login and chat: Show pending additions -> No items are waiting to be added,4 measured successful real-provider calls and completed queued_additions graph checkpoint. No scripted provider or missing-key fallback. Key reused from authorized original Thread process only, never printed/persisted; child browsers exclude it. State is separate retained synthetic .local-live-state; existing fallbackPID90342 on8543 and original wardrobe untouched. Server stops2026-10-25T18:31:21UTC, one minute before leaf expiry.

Cumulative2168 API attempts: US$1.1974964 provider-usage-priced estimate,zero outstanding/unknown reservations,US$48.8025036 remaining. Actual billed cost unavailable; future human demo interactions remain under the same cap and can increase this estimate. All277 original source hashes match. Exact-key scan of audit/evidence/new live state foundzero matches. pip check passes.

Approved CA SHA2562a6df6ec92d698ef45da62880defb087c5db6f8180da270524934fe401fb8551 is installed with SSL-only trust and native/browser verification passes. It is retained only for the user-facing testing phase per approval to remove when the user finishes; cleanup has NOT occurred. Parent must resolve when user testing finishes, then remove only the exact certificate/trust and independently verify absence. Removing now would prevent normal browser access to the ready live app. No trust expansion, TLS bypass, real purchase or original-data change occurred. Functional automated case coverage is complete; operational cleanup remains pending user testing completion.


## Three-month restoration complete — 2026-10-25T16:54:15.974355-07:00

New CA7fb2a4a6865a27742a38b66b086e8811782a82e25fbfe9ccc82a70feadc6e1f3 was approved and installed for user-login SSL only. NameConstraints and exact leaf SANs restrict atlas.localhost/jacket.localhost. Both certificates expireJanuary25,2027 at4:14:05PM Arizona. Native validation accepts both hosts and rejects unrelated hostname/future expired date. The exact expired prior CA2a6df6ec… certificate and trust are both independently verified absent. New TLS files reside in private ignored .local-live-tls/2767617c4da7, moved without copying generated key; key0600, directory0700; CA signing key discarded.

Fresh full Chrome+realGPT aggregate:550passed,2assertionfailed,0skipped in552 cases,801.99seconds,897 actual API attempts. Both failures were oracle wording assumptions (decorative synthetic-name suffix, literal uppercaseM versus medium). Corrected tests now require canonical authenticated Thread source facts and whole-word equivalent size wording; all no-write/isolation guards remain, observer forwards real provider responses unchanged. Both affected cases passed live after correction (2/2). Effective552tracked cases pass; raw failed XML retained; no universal100percent claim.

Final app PID32806 is running on loopback8545, execsession78006, genuine GPT4.1-mini2025-04-14 through DeepAgents. Normal-TLS dedicated Chrome login→Show pending additions→4 measured real GPT calls→queued_additions→rendered reply passed, without clearing or altering archives/preferences/carts/orders. Latest completed checkpoint owner matches authenticated profile. Screenshot:evidence/thread3-live-restored.png. ControlledSIGTERM restart exits0 and correctly records stopped metadata after launcher signal/graceful-shutdown fix; final instance restarted and left serving.

All protected saved-table logical hashes match pre-renewal baseline:100profiles, cart, orders, add receipts, FORME preferences, accounts/addresses, archives and company links. All277 originalwardrobe code hashes unchanged. No original-data mutation or API-key persistence/copy; exact-key scan of195 Thread3 artifacts/state/TLS files haszero matches. Originalkey reused only in live process; browser child environment excludes it.

Cumulative3163 API attempts:US$1.775652 usage-priced estimate,zero outstanding/unknown reservations,US$48.224348 remaining from originalUS$50 cap. Actualbill unavailable; future demo use remains under the same shared gate and increases measured estimate. Current published GPT4.1mini prices reverified unchanged.

Actual certificate-safety stop isJanuary25,2027 at4:13:05PM Arizona (one minute before expiry), not the old one-day timer. App requires Mac/process availability; no OS startup service installed; manual relaunch after reboot needs original Thread key-source service. Provider announced current GPT snapshot shutdownJanuary14,2027, requiring future migration before certificate expiry; no silent model change was made. New trust intentionally retained for continued user use. Exact old-trust cleanup is complete; no pending native operation. Full artifacts:audit/three-month-final-results.json and audit/three-month-final-case-matrix.json.
