# 02 — Design Philosophy

The rules below are the load-bearing decisions behind the code. Each exists because something
broke without it. When adding features, treat them as constraints, not suggestions.

## 1. jussi is a proxy, not an application

jussi never interprets JSON-RPC results beyond what routing/caching/safety requires. It does not
rewrite results, does not enforce schema on them, and passes both successful and error responses
through (errors get enrichment — `trace_id`, `jussi_request_id` — but the payload is the
upstream's). Anything that smells like business logic on response contents needs a strong reason;
the `get_state` workaround is the sanctioned exception and is explicitly temporary.

## 2. The idempotency split governs retry, timeout and caching

Methods are classified by `validators.IsBroadcastTransactionRequest`:
`broadcast_*` (any API) and `chain_api.push_transaction` / `push_block` are **non-idempotent
writes**; everything else is treated as an idempotent read.

- Non-idempotent: **single attempt, no retry ever** (a transient transport error must not
  double-submit a transaction), timeout floored at 30s (a synchronous broadcast legitimately waits
  for block inclusion), never cached (their TTL entries in config are `-1`).
- Idempotent: bounded retry (`DefaultRetryConfig`, ≤2 attempts, 100–500ms backoff, only on
  retriable transport errors / 5xx), per-URN timeout, cacheable per TTL.

If you add a new write-shaped method, extend `IsBroadcastTransactionRequest` — do not special-case
retry at call sites.

## 3. Fail fast, protect the backend

The service exists to sit in front of backends that can saturate. When a backend degrades:

- per-request deadlines cancel jussi's wait — but the SQL the upstream already started keeps
  running, so
- the **circuit breaker** converts sustained failure into instant local rejections, stopping the
  arrival burst so the backend can drain (incident 2026-09-18, see `breaker.go` package comment),
- retries are tight (2 attempts, sub-second) specifically to avoid the legacy
  expiration-on-retry pattern that piled waiting requests onto ALB.

Prefer "reject quickly with a structured error" over "queue and hope". Never add unbounded
buffering (channels, queues, in-flight maps) on the request path.

## 4. Nothing about deployment topology leaks to clients

jussi is a public gateway. The rule set:

- Client-facing error messages never contain upstream URLs, hostnames, or internal error chains —
  those go to server-side logs (`slog`) and metric labels only. `errors.HandleError` implements
  this: non-typed errors are logged and replaced by a generic `Internal error`.
- `/health` reports breaker states under **aliases** derived from configured upstream names
  (`handlers.BreakerAliases`); unknown keys fall back to a sha256 digest alias, never a hostname.
- Version metadata (`source_commit`, `docker_tag`) is redacted to `"unknown"` unless
  `JUSSI_EXPOSE_VERSION=true`.
- Proxy trust is opt-in: with no `server.trusted_proxies`, gin trusts nothing and `ClientIP()`
  uses the socket address, so `X-Forwarded-For` cannot spoof the metrics allowlist.

## 5. Cache keys and wire formats are compatibility surfaces

- The cache key is the URN string (`steemd.database_api.get_block.params=[1000]`) — byte-identical
  to legacy Python jussi, and shared across all instances via Redis. Change the format and every
  entry misses simultaneously (and legacy instances, if ever run side-by-side, stop matching).
- The upstream request body must be serialized without HTML escaping
  (`helpers.MarshalJSONWithoutHTMLEscape`) because steemd's FC parser mis-reads `\uXXXX`.
- Appbase-format requests (named/object params) are forwarded verbatim; only legacy positional
  formats are rewritten to `condenser_api` (see translation rules in
  [03-config-and-routing.md](03-config-and-routing.md#appbase-translation)).

## 6. Parse once, share the result

The request body is read and parsed exactly once by `BodyParseMiddleware` (with a size cap), and
the parsed value travels in the gin context (`middleware.ParsedBody`). Every consumer — cache
lookup, limits, the handler — must use it. Re-reading the body is not just wasteful: the second
reader gets EOF and silently skips its checks (this was a real security-affecting bug).

## 7. The client's `id` is per-request state, never cached

Cached entries are stored **without** `id` (`delete(cacheEntry, "id")` at store time) and every
cache-hit path deep-copies the cached map before setting `id` to the current request's. Two
reasons: correctness (each caller gets its own id) and safety (Go maps are not concurrency-safe;
without the copy, concurrent batch goroutines race on the same cached map). If you add a cache
read path, both rules apply.

## 8. Observability is part of the feature

Every upstream call is counted (`jussi_upstream_requests_total`), timed, classified
(`jussi_upstream_errors_total`), and breaker state is exported as a gauge
(`jussi_upstream_circuit_state`) plus a `/health` mirror — a scrape failure must not blind
operators to a tripped breaker. Broadcast failures additionally emit a structured `slog` warn
because that is the signal operators correlate with "wallets are seeing failed transactions".
When you add a failure mode, add its counter at the same time.

## Deliberate deviations from legacy

Ported-config semantics that were **intentionally changed** vs the Python jussi — do not "fix"
them back without a discussion:

| Legacy behavior | Go behavior | Why |
|---|---|---|
| `timeouts: 0` = no limit (infinite) | `0`/absent → bounded defaults (see timeout policy in 06) | Infinite waits behind an LB accumulate connections; broadcasts get a 30s floor instead (commit e79cbf2) |
| 3 retries, multi-second backoff | ≤2 attempts, 100–500ms backoff, idempotent only | Keep retry budget under wallet timeouts (commit e79cbf2) |
| Memory + Redis both active | Redis-only when configured; memory only as no-Redis fallback | Redis→memory promotion with `TTL=0` served stale data forever (commit 56ae2f9) |
| HTTP/2 allowed | HTTP/1.1 forced (`ForceAttemptHTTP2=false`) | HTTP/2 multiplexing pinned all requests to one ALB connection (commit e79cbf2) |
| Circuit breaker: none | per-upstream breaker, default on | 2026-09-18 saturation storm (commit dc1983d) |

## Decision checklist for new features

Before implementing, be able to answer:

1. Which side of the idempotency split is the new path on? (retry/timeout/cache policy follows)
2. Does it touch the request body? Then it goes **after** `BodyParseMiddleware` and reads
   `ParsedBody`.
3. Does it change what clients can infer about topology? (URLs/hostnames in errors, headers,
   health)
4. Does it interact with the cache? Then: same key format, same `id`-stripping, deep copies on
   every shared-reference read.
5. Is the same logic already implemented somewhere? Then share it — extract a helper — instead of
   copying it.
