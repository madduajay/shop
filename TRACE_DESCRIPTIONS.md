# Plain-English trace descriptions

**LIVE:** Activated together on 18 October 2026 after approved recoverable archive/reset/restart. PID 49434. Live browser checks passed; see COMBINED_ACTIVATION.md. The readiness notes below describe pre-activation testing.

Ready for combined activation with notification Dismiss; NOT LIVE. PID 47967 remains running with the active shirt-search chat. No restart, archive or clear was performed for this update; approval remains pending.

Every displayed Request and Response has a concise description in its collapsed summary. Descriptions use deterministic mappings and recorded result fields, with no model-generated reasoning. Requests describe the requested action; responses distinguish observed result, HTTP error, pending response, failure without response, and unknown historical outcome. A browser add command reports the observed bag count rather than asserting that a purchase occurred. A browser handoff is described as accepted/cookie-issued only when recorded status, validator outcome and cookie issuance support it. Existing direction labels, reply wording, Poppy/Browser classification, masking and collapsed defaults remain.

20 focused tests passed across trace descriptions, notification dismissal and Thread authentication. Representative cases include Poppy authorization, accepted/rejected handoff, token pending/failure, incomplete historical records, browser add error/empty bag, signed-in observation and unknown actions. Assertions verify descriptions are inside visible summaries and payloads remain collapsed. Headless Chrome verification passed desktop/mobile layout, visible descriptions while collapsed, expand/collapse, archive navigation and user isolation. The isolated fixture used actual GPT elsewhere in the shopping flow; descriptions themselves use no model calls. All 100 fixture profiles remained unchanged and zero orders were created.

Evidence: evidence/trace-descriptions/run.log, trace-ui-fixture.json, thread-traces.png, thread-traces-mobile.png. Combined Dismiss evidence remains in evidence/notification-dismissal/.
