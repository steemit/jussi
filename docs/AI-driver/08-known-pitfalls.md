# 08 — Known Pitfalls

Every item here is a bug class that has actually bitten this service (in production or in
review). Each comes with the rule that prevents it. Read before touching the related area.

## 1. HTML escaping breaks transaction signatures

**What happened:** Go's `json.Marshal` escapes `<`, `>`, `&` to `\u003c/\u003e/\u0026`. steemd's
FC JSON parser does not understand `\uXXXX` — it reads the escape as literal characters, so a
post body containing `>` (Markdown blockquote) no longer matched the signed bytes →
"Missing Posting Authority" on otherwise valid transactions.

**Rule:** every serialization of a body sent to a steemd-family upstream must use
`helpers.MarshalJSONWithoutHTMLEscape` (encoder with `SetEscapeHTML(false)`, trailing newline
stripped). The **response** direction (gin `c.JSON`) is intentionally allowed to escape —
standard JSON clients decode escapes fine. Do not "unify" the two directions.
Reference: `internal/helpers/json.go` (full write-up in its doc comment).

## 2. Body re-reads silently disable middleware

**What happened:** two middlewares each called `ShouldBindJSON`; the second got EOF (body already
consumed) and treated it as "nothing to check" — which silently disabled all limit checks (audit
finding H-1, fixed in #263).

**Rule:** the body is parsed once in `BodyParseMiddleware`; every consumer uses
`middleware.ParsedBody(c)`. A new middleware that needs the body must (a) run after it and
(b) fail **closed** when the parse is missing, not open.

## 3. Cache-hit responses must re-inject the caller's `id` — on a deep copy

**What happened:** cached responses carried a previous caller's id; and concurrent batch
goroutines mutated the same cached map (`resp["id"] = ...`), a data race corrupting ids.

**Rule:** stored entries have `id` stripped; every hit path deep-copies
(`helpers.DeepCopyMap`) and then sets `id`. Applies to **any** new cache read path, including
sub-request caches. The memory tier returns shared pointers; Redis does not — code must be safe
for the memory tier because it becomes active whenever Redis is unreachable at startup.

## 4. appbase translation must not touch named-params requests

**What happened:** translating requests that were already in appbase format (object params) to
`condenser_api` broke every method that exists only on the real appbase APIs
("Could not find method find_accounts").

**Rule:** translation applies to legacy positional formats only (bare method / `call` triple /
`api.method` with array params). `isNamedParams` is the guard. Other namespaces (hivemind
`bridge.*`, ...) are forwarded verbatim, always. Regression tests:
`processor_translate_test.go`.

## 5. TTL `0` means "forever", `-1` "never", `-2` "3s if irreversible" — and `CalculateTTL` lies

**What happened (repeatedly):** the special TTL values are easy to half-implement; the helper's
comments describe semantics its return values don't implement (both `-2` branches return 0;
`lastIrreversibleBlockNum` unused).

**Rule:** use the processor's resolution order (`IrreversibleTTL` for `-2`, then duration) and
do not call `CalculateTTL` with raw configured TTLs. When touching TTL code, delete misleading
helpers instead of adding callers. Full semantics: [04-caching.md](04-caching.md#ttl-semantics).

## 6. Legacy `timeout: 0` no longer means "infinite"

Ported configs that set `timeouts: [["...network_broadcast_api", 0]]` meant "wait forever" in
Python jussi. In Go, `0` (and absent) resolve to bounded defaults (15s reads / 30s broadcast
floor; router-level absent-entry default is 30s). If a wallet reports broadcast timeouts after a
config migration, check the effective timeouts in the startup `upstream registered` log line —
and remember that line prints the configured value, not the effective one (known doc gap).

## 7. Shared references out of the cache mutate under you

**What happened:** the get_state workaround returned the cached map without copying and then
wrote `current_route`/`transfer_history`/`id` into it — a race under the memory tier (found in
the 2026-09-21 review; three sibling code paths had the copy, this one didn't).

**Rule:** anything obtained via `cacheGroup.Get` that will be mutated (or handed to concurrent
mutators) is deep-copied first. See pitfall #3 — same root, different symptom.

## 8. Errors as `(nil resp, err)` are invisible to `resp, _ :=` tests

**What happened:** the circuit-breaker recovery test discarded the error return; breaker
rejections (which return `(nil, err)`) sailed through "post-recovery success" assertions,
hiding a P0 that stranded the breaker in half-open forever.

**Rule:** any test that asserts success must assert on **both** returns — especially paths whose
failure mode is an error rather than an error envelope inside the response.

## 9. Duplicated logic drifts (the meta-pitfall)

**What happened:** every severe bug in the 2026-09-21 review had this shape — the same rule
existed in two places, one was fixed, the other wasn't:

- breaker Allow/Record token handling: `callSteemd` correct, `callHTTPUpstream` broken;
- cache-hit deep copy: three paths correct, workaround path missing;
- error-response cache filtering: legacy had it, Go ported the helpers but never wired them.

**Rule:** before writing a second copy of an existing pattern (guard clauses, cache access,
serialization, metric emission), extract a shared helper and call it from both sites. In review,
treat "same logic, two implementations" as a defect on its own.

## 10. Circuit breaker: the probe token is a protocol, not a detail

In half-open, `Allow()` returns a token to exactly one caller and `Record(_, nil)` is ignored
(stale requests must not answer the probe). Discarding the token = the breaker can never close
(or re-open) again. If you write a new upstream call path (e.g. re-enabling WebSocket), it must
participate in the same Allow → call → Record(token) sequence, ideally via the shared helper
that pitfall #9 asks for. Kill switch: `upstream.circuit.enabled=false` makes every `Allow`
pass-through (breakers still count; enforcement is off).

## 11. Redis-down startup falls back to the memory tier — behavior differences activate

With Redis unreachable at startup, `initCache` silently switches to `MemoryCache`
(process-local, random eviction at capacity, shared-pointer reads). Code that is "safe because
Redis deserializes fresh objects" becomes unsafe (pitfalls #3/#7). Never assume the Redis tier
when reasoning about mutation safety.

## 12. Anything client-visible is public — including headers and /health

`x-jussi-cache-hit` exposes the cache key (caller's own params — acceptable, matches legacy);
error envelopes must not carry upstream URLs/hostnames (generic Internal error instead);
/health aliases hostnames away; version metadata is redacted by default. Before adding a
response header or payload field, ask what it reveals about deployment topology.

## 13. Middleware order is load-bearing

`BodyParse → ResponseCapture → UpdateBlockNumber → CacheLookup → Limits` works because each
depends on the previous (parsed body / captured writer / captured writer / parsed body / parsed
body). Insertions that look harmless (e.g. a logging middleware that reads the body before
BodyParse) resurrect pitfall #2. The order lives in `app.SetupRouter()`; change it only with the
dependency table in [05-request-pipeline.md](05-request-pipeline.md) in hand.

## 14. The strict request validator rejects unknown keys

`ValidateJSONRPCRequest` fails requests carrying keys outside `{id, jsonrpc, method, params}`.
Adding a new accepted request field means updating `JSONRPCRequestKeys` **and** making sure
downstream code tolerates its absence (old clients). This strictness is inherited from legacy —
clients depend on junk being rejected.

## 15. Don't trust docs that predate the Go rewrite

`docs/CONFIGURATION.md` documents nonexistent fields; `docs/METRICS.md` documents never-recorded
metrics (see [07](07-errors-and-observability.md#metrics) for the live list). When a doc and the
code disagree, the code wins — and the doc should be fixed in the same PR that noticed it.
