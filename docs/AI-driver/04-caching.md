# 04 — Caching

## Cache keys

The key is the URN string: `appbase.condenser_api.get_block.params=[1000]`.

- Generated **after** appbase translation, so legacy-format and appbase-format requests for the
  same call share one entry.
- Keys are shared with Redis across instances and are format-compatible with the legacy Python
  jussi. Treat the format as frozen.
- The `get_state` workaround uses a separate key family (`jussi.gs:base:`, `jussi.gs:hist:`, ...)
  with a configurable prefix (`JUSSI_CACHE_KEY_PREFIX`, default `jussi.`).
- On hit, the `x-jussi-cache-hit` response header carries the key (same as legacy; the key only
  exposes the caller's own params).

## TTL semantics

Configured per URN prefix in the upstream file. Special values:

| Value | Meaning | Store behavior |
|---|---|---|
| `> 0` | seconds | cached for that duration |
| `0` (`TTLNoExpire`) | cache forever | stored with no expiry (memory: zero `expiresAt`; Redis: SET without TTL) |
| `-1` (`TTLNoCache`) | never cache | lookup and store both skipped (`cache.IsCacheable`) |
| `-2` (`TTLExpireIfIrreversible`) | conditional | resolved at store time via `cache.IrreversibleTTL`: if the response carries a block number ≤ LIB → cached **3s** (`TTLDefault`); otherwise not cached |

`-2` matches legacy semantics (legacy `ttl.py`: "cached with default expiration only if
'irreversible'"). The block number is extracted by `cache.BlockNumFromJSONRPCResponse` from
`result.block_num`, `result.block.block_id`, or `result.block_id` (hex prefix). Responses without
any of those (e.g. `get_state`) are never cached under `-2`.

**Implementation trap — do not call `cache.CalculateTTL` directly with a configured `-2`.**
Its switch returns duration 0 for every special value and its comments claim behaviors
("cache forever if irreversible") that the store-side guard (`cacheTTL > 0 || ttl == TTLNoExpire`)
then makes unreachable. The working path is exactly what the processor does:
`ttl == -2` → `IrreversibleTTL(response, lib)` → (3 | -1) → only then `CalculateTTL` on a plain
value. If you touch TTL logic, simplify these helpers rather than adding callers for them.

## LIB tracker

`cache.BlockNumberTracker` (process-global, initialized in `middleware.InitBlockNumberTracker`)
monotonically tracks `last_irreversible_block_num`. It is fed by
`UpdateBlockNumberMiddleware`, which parses **every single-object JSON-RPC response** and updates
on `result.last_irreversible_block_num` — in practice from the constant stream of
`get_dynamic_global_properties` calls clients make.

Consequences:

- On cold start LIB is 0 and `-2` entries are not cached until traffic warms the tracker.
- **Batch responses are not scanned** (the middleware can't unmarshal an array) — a deployment
  where only batch callers poll global properties would never update LIB.
- If you need LIB in a new code path, use `middleware.GetBlockNumberTracker()`.

## Cache tiers

`app.initCache` picks **one** tier:

- Redis configured (`cache.redis_url` or discrete `redis.*`) and reachable at startup → Redis
  only. Memory cache is intentionally disabled to avoid TTL-stale promotion (commit 56ae2f9:
  promotion wrote entries with unbounded TTL into memory).
- No Redis / Redis unreachable at startup → memory only (`MemoryCache`, bounded entries +
  background cleanup + random ~10% eviction at capacity).

`CacheGroup` (group.go) is the facade. Note its error policy: `Get`/`MGet` **swallow backend
errors** (a cache outage must not fail requests) — there is currently no signal (metric/log) when
that happens; if you rely on cache health, add one rather than assuming.

Memory-vs-Redis safety difference: `MemoryCache.Get` returns the **stored pointer**; Redis
deserializes fresh objects per read. Any code that mutates a value obtained from the cache
**must deep-copy first** when it might be running against the memory tier (see pitfall #7).

## What gets stored

At store time (`processor.ProcessSingleRequest`):

- Only when `cache.IsCacheable(ttl)`.
- A deep copy of the response with `id` **deleted** — ids are per-request and re-injected on hit.
- Duration per the TTL table above; `_ = Set(...)` errors are ignored (with a metric
  `jussi_cache_operations_total{set,skipped|success}`).

⚠ Known gap (2026-09-21 review): the store path does **not** check `response["error"]`, so
upstream JSON-RPC error responses are cached like any other response (legacy filtered them via
`is_valid_non_error_single_jsonrpc_response`; the ported helpers
`validators.IsValidNonErrorResponse` / `IsValidGetBlockResponse` exist but are unwired). Fix
before relying on "errors are never cached". The `get_state` workaround's `fetchCachedOrCall`
does check `resp["error"] == nil` — use it as the reference pattern.

## Two lookup layers (middleware vs processor)

There are currently **two** cache lookups on the request path:

1. `middleware.CacheLookupMiddleware` — single POST requests only, key from the **pre-translation**
   URN. On hit: deep-copies, re-injects `id`, responds 200 immediately (metrics-blind — see below).
2. `processor.ProcessSingleRequest` — key from the **post-translation** URN; serves batches too.

Because (1) computes keys before translation and (2) stores after, requests that get translated
(legacy-format traffic) can never hit layer 1, and every miss pays both lookups (two Redis RTTs
in production). Middleware-layer hits also bypass `jussi_requests_total` /
`jussi_cache_operations_total` entirely. This duplication is a known architectural wart from the
2026-09-21 review — if you touch it, converge on a single lookup layer (the processor is the
natural survivor; it owns the translated key space and the metrics) rather than adding a third.

## get_state workaround cache (temporary)

`handlers/get_state_workaround.go` emulates `get_state` sub-paths steemd does not implement
(`/@user/transfers`, `/~witnesses`, ...) by assembling sub-request results cached for **10s**
under the `jussi.gs:*` key family. Only successful (`error`-free) sub-responses are cached.
The whole file is scheduled for deletion once the condenser/wallet rewrites ship — do not build
new features on it, and keep its removal blocklist (processor.go "TEMPORARY WORKAROUND") in sync
if you touch it.

## Concurrency rules for cached values

1. Never mutate a map obtained from `cacheGroup.Get` without deep-copying
   (`helpers.DeepCopyMap`); the memory tier hands out shared pointers.
2. Never store a map you intend to keep mutating — deep-copy before `Set`.
3. Batch goroutines share cached entries by key; the `id`-reinject step must operate on the
   per-request copy only.

These rules exist because a shared-cached-map race corrupted response ids under concurrent
batches once already (there are tests pinning the deep-copy behavior).
