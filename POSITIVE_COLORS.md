# Explicit positive color constraints

**LIVE:** Activated together on 18 October 2026 after approved recoverable archive/reset/restart. PID 49434. Live browser checks passed; see COMBINED_ACTIVATION.md. The readiness notes below describe pre-activation testing.

Implemented and verified in isolated fixtures; NOT LIVE. Live PID 47967 is unchanged. Combine activation with NOTIFICATION_DISMISSAL.md and TRACE_DESCRIPTIONS.md after the pending archive/reset/restart approval. No live chat, profile, order, bag, or notification was changed by these tests.

## Root cause

Read-only inspection of the real user trace showed Thread sent `color=red` for “show me red shirts”. The storefront select had no red option. The controlled browser's normal select assignment became an empty value, submitting `color=''`. Preference ranking then returned blue, burgundy and white shirts. Their image metadata matched those variants: this was a lost eligibility constraint, not an image-only mismatch or GPT forgetting red. The catalog contains no red shirt variants.

## Change

The retailer's real color select now includes every supported color, including zero-count red. An explicit positive color is also submitted through the existing `include_colors` constraint, even for one color. The agent rejects any returned variant outside the requested positive/negative colors. These changes still use the controlled browser and retailer forms; no purchase API or cookie injection was added.

Unexpired empty searches now retain context for a budget or color refinement. Bare “red” is recognized; “under $80” retains red after no matches. Empty searches do not enable ordinal selection. Original user color polarity remains authoritative if model normalization loses it. Saved ranking preferences cannot substitute for explicit colors.

## Verification

- 40 tests pass across color constraints, conversation routing, trace descriptions and notification dismissal. Tests cover actual browser form submission, no-match red, budget refinement, deliberately lossy model normalization, a disallowed retailer response, exclusion/pagination, contradictions and persistence/isolation behavior.
- Actual GPT fixture: white shirts → red shirts → under $80 → blue shirts → red → blue or navy excluding white → not blue either. All colors and image metadata agree; red honestly returns no matches; the final exclusion retains navy and returns no matches. 10 actual GPT calls, all 100 profiles unchanged, zero orders.
- Rendered disposable Chrome fixture: white → red → under $80, no substitute cards appended, desktop/mobile screenshots, no mobile overflow. Four actual GPT calls. One company explanation attempt failed grounding validation and correctly used the labeled catalog-based fallback; it did not affect filtering. All 100 profiles unchanged, zero orders.
- Initial fixture failures exposed missing routing for empty-result refinements and bare red; fixed and rerun successfully.
- Live post-restart check is unrun because approval remains pending. Existing real-user browser was inspected read-only; corrected UI was verified in disposable Chrome, not injected into the user's active session.

Evidence: `evidence/positive-colors/result.json`, `regression.log`, `ui-result.json`, `ui.log`, `red-shirts-desktop.png`, `red-shirts-mobile.png`. Fixtures used ports 8447/8448 and have shut down. Run URLs after activation remain https://atlas.localhost:8443/ and https://jacket.localhost:8443/shop. Original Atlas/store on port 443 were not modified.
