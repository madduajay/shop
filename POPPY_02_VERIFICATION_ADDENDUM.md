# Bounded Poppy 0.2 verification — 2026-10-19

The supported local deployment is a single-process Thread client and FORME company: discovery, Session Tokens/DPoP, Device Sign-In, Account Token refresh/revocation, browser activation, Poppy conversations, and SSE. Its private SDK leaves original Atlas untouched. Current demo PID:79676.

## Actual defects found and fixed

Fault injection reproduced two in-scope failures: interruption after message-ID reservation caused retry404; interruption after the idempotent watch effect left retry permanently working. Conversation receipt, history and original response now commit in one SQLite transaction under a single-process request lock. Exceptions and task cancellation roll back. The separate availability database uses the existing consent key to recover an already-committed effect without duplication. This is specific to the current idempotent availability operation, not a generic distributed exactly-once guarantee.

## Final evidence

- `evidence/protocol02-gap-checks.xml`:15 passed. Concurrent12 identical requests produce one completed operation and identical original responses. Interruption after claim and after effect recovers. Cancellation rolls back. Receipt replay survives database connection reopen. A separate subprocess exits abruptly inside a transaction; reopening finds neither partial receipt nor partial history.
- Independent peer fixture `evidence/independent02_peer_checks.py`: plain HTTP/JSON/JWT responder, no company SDK validators. It independently validates ES256 signature, public JWK, proof type, method/URL, time, token hash and fresh jti. It checks creation201, later messages202, incoming SSE id/data and Last-Event-ID. GET retry and explicit POST retry wait at least Retry-After; a POST is not automatically replayed. SSE propagates retry delay. OAuth cooldown tests cover queued token/device/revocation callers, delta seconds, HTTP date and huge delay. Token/device/account paths share this tested OAuth gate.
- Adversarial boundary checks: injected profile text requests credentials and purchases, a user claims another customer identity, model calls attempt extra customer/password/path access, invalid model output invents sources, and a model forges confirm_checkout. No orders, watches, sign-in or unauthorized browsing occur; the customer2 sentinel and password sentinel do not leak. These deliberately malicious tool outputs test enforcement independent of a model's willingness to obey an attack.
- `evidence/protocol02-atomic-integration.xml`:47 passed after the fix, including independent-client device authorization, actual controlled Chrome activation/cookie, availability delivery, ownership isolation, cancellation and trace rendering. Earlier unchanged-core checks:86 protocol/security tests,102 memory/filter tests,2 real GPT journeys. The GPT journeys were not rerun for this transaction-only change; the real browser integration was.
- Live TLS health and Chrome reload verified after restart. Both original port443 pages returned200. Eight customer/commerce table hashes are unchanged (`poppy02-atomic-before.json` versus `poppy02-atomic-after.json`). All36 prior archive payloads are unchanged; the browsing verification chat was added as archive37. No purchases, external accounts, new credentials or new live watches.

## MUST/SHOULD disposition and residual scope

The two reproducible single-process recovery failures are resolved and deployed. No known failing MUST remains in the exercised supported flows. This is a bounded evidence statement, not mathematical proof or third-party certification; the requirements ledger records inspection versus targeted testing.

Rate-limit scope: advertised OAuth paths and conversation transport are covered, including cross-request cooldown. This storefront does not emit429 to the agent's normal shopping/browser-activation routes. Its user-operated device sign-in form rate-limits invalid passwords and supplies Retry-After; the agent does not automate that user page. A general browser capable of handling arbitrary external retailer429 policies is not the current one-company demo's capability.

Optional APIs/MCP, Direct/Mediated Sign-In, feedback and operations are not advertised. The company conversation lifecycle is tested; Thread does not offer a human/direct conversation interface and FORME does not emit a user_requested event. They are not claims of supported product features.

No external setup is required for further local negative tests. A real third-party interoperability result requires a separately operated Poppy0.2 peer, which is not available here; no account or infrastructure was created. Multiworker/distributed receipt locking and hardware/power-loss/storage corruption testing are outside this single-process deployment. Arbitrary future model behavior cannot be certified by a finite attack corpus; current deterministic authorization, identity and approval boundaries passed the attacks above.

Bounded conclusion: the supported local Poppy0.2 flows pass the recorded protocol, independent-wire, recovery and adversarial-boundary checks, with no known remaining reproduced failure. Do not describe this as universal100% conformance across optional capabilities, arbitrary peers or production architectures.
