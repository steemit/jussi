# 01 — Architecture Overview

## What jussi is

jussi is a high-performance JSON-RPC 2.0 reverse proxy in front of Steem blockchain services.
Clients (wallets, condenser, explorers, scripts) POST JSON-RPC to `/`; jussi:

1. parses and validates the request,
2. resolves the method to an **upstream** (steemd / appbase / hivemind / overseer / ...) using
   longest-prefix routing on the method URN,
3. optionally translates legacy wire formats to the appbase format,
4. serves from cache when the per-URN TTL allows,
5. fans out to the upstream with per-URN timeouts, bounded retry (idempotent reads only), and a
   per-upstream circuit breaker,
6. caches the response under the TTL policy and returns it with the client's `id` re-injected.

It also serves `GET /health` (public, alias-safe breaker states + last irreversible block),
`GET /` (same shape as /health), and `GET /metrics` (Prometheus, IP-restricted).

## Process shape

Single Go binary (`cmd/jussi/main.go` → `internal/app.App`), one `gin` HTTP server, no
sidecar goroutines except cache cleanup and telemetry batching. Horizontal scaling is by
running N stateless instances behind an LB, sharing a Redis for the cache tier.

```
client ──HTTP──▶ openresty (edge, rate limit) ──▶ jussi :9000 ──HTTP──▶ upstreams
                                                    │
                                                    ├──▶ Redis (cache tier, optional)
                                                    └──▶ OTLP collector (traces)
```

WebSocket upstream support exists in `internal/ws` but is **disabled** (`TODO: WebSocket support`
blocks in `app.go` / `processor.go`). Treat `ws://` upstream URLs as unsupported until that
changes; the HTTP path is the only production path.

## Request lifecycle (single request)

Middleware order is defined in `internal/app/app.go:SetupRouter()` and **the order is load-bearing**
(see [05-request-pipeline.md](05-request-pipeline.md) for each contract):

```
gin.Recovery
otelgin (if telemetry enabled)
RequestIDMiddleware          — sets/echoes x-jussi-request-id, ctx key "jussi_request_id"
TracingMiddleware            — starts the jussi.request span
ErrorMiddleware              — (currently a dead path; see pipeline doc)
BodyParseMiddleware          — size cap + ONE shared JSON parse → ctx "parsed_body"
ResponseCaptureMiddleware    — wraps gin.Writer to capture the response body
UpdateBlockNumberMiddleware  — after response: extracts last_irreversible_block_num → LIB tracker
CacheLookupMiddleware        — single-request cache lookup (see caveats in 04-caching.md)
LimitsMiddleware             — batch size cap, get_account_history cap, broadcast limits
  └─ POST / → JSONRPCHandler.HandleJSONRPC
       ├─ validators.ValidateJSONRPCRequest
       ├─ request.FromHTTPRequest → urn.FromRequest → URN
       └─ RequestProcessor.ProcessSingleRequest
            ├─ translateToAppbase (if upstream configured translate_to_appbase)
            ├─ get_state workaround intercepts (temporary; see handlers/get_state_workaround.go)
            ├─ router.GetUpstream(URN) → URL + TTL + timeout
            ├─ cache lookup (processor-level, post-translation key)
            ├─ callHTTPUpstream: breaker.Allow → timeout ctx → Request|RequestWithRetry → breaker.Record
            ├─ cache store (if cacheable; strips "id" from the stored copy)
            └─ response["id"] = client id; error enrichment (trace_id, jussi_request_id)
```

Batch requests take the same chain but skip the middleware cache lookup; the processor runs
`ProcessSingleRequest` for every item in its own goroutine and reassembles responses by original
position.

## Module inventory

| Package | Responsibility | Key files |
|---------|----------------|-----------|
| `cmd/jussi` | Entry point | `main.go` |
| `internal/app` | Wiring: config → logger → cache → router → HTTP client → gin setup → graceful shutdown | `app.go` |
| `internal/config` | Viper-based config (file + explicit env bindings), upstream JSON schema, validation | `config.go`, `validation.go`, `circuit.go` |
| `internal/urn` | JSON-RPC method → URN (namespace/api/method/params); URN string = cache/routing key | `urn.go` |
| `internal/upstream` | Trie-based longest-prefix router; HTTP client; retry policy; circuit breaker | `router.go`, `trie.go`, `http.go`, `retry.go`, `breaker.go` |
| `internal/cache` | Cache interface, memory + Redis backends, CacheGroup, TTL semantics, LIB tracker | `group.go`, `memory.go`, `redis.go`, `ttl.go`, `irreversible.go` |
| `internal/middleware` | Gin middlewares: body parse, cache lookup, limits, security, block number, capture | `body.go`, `cache.go`, `limits.go`, `security.go`, `blocknum.go` |
| `internal/handlers` | HTTP handlers and the request processor (the heart), get_state workaround, health | `jsonrpc.go`, `processor.go`, `health.go`, `get_state_workaround.go` |
| `internal/request` | Parsed JSON-RPC request type, upstream payload shaping | `jsonrpc.go` |
| `internal/validators` | JSON-RPC shape validation, broadcast detection, limit checks | `validators.go` |
| `internal/errors` | JSON-RPC error taxonomy + `HandleError` (the single client-facing error renderer) | `errors.go`, `errors_extended.go`, `circuit.go` |
| `internal/telemetry` | OTel setup, spans, Prometheus metric declarations | `setup.go`, `metrics.go`, `circuit.go` |
| `internal/logging` | zerolog logger (Scalyr-oriented) | `logger.go` |
| `internal/ws` | WebSocket client/pool — **disabled**, not production-tested | `client.go`, `pool.go` |

## Dependency flow (what may import what)

Roughly layered, inward-pointing:

```
app → handlers → {request, upstream, cache, middleware, validators, errors, telemetry}
middleware → {cache, urn, request, validators, errors}
upstream → config        (raw upstream config types only)
cache → urn
errors → (gin, otel)     (rendering only)
```

Rules worth keeping:

- `internal/errors` must stay free of business logic — it is the rendering layer for client-facing
  errors.
- `internal/config` must not import `internal/upstream` internals (the breaker's runtime config
  conversion intentionally lives in `handlers/circuit.go` for this reason).
- `internal/middleware` reaches into handlers only via the shared `middleware.GetBlockNumberTracker()`
  global (a pragmatic singleton; see 04-caching.md#lib-tracker).

## Where state lives

| State | Owner | Lifetime |
|-------|-------|----------|
| Parsed request body | gin context key `parsed_body` | request |
| Captured response body | `responseWriter` wrapper (read via type assertion, **not** the `response_body` context key) | request |
| LIB (last irreversible block) | `cache.BlockNumberTracker` process-global | process |
| Circuit breakers | `upstream.Registry`, one per `scheme://host`, lazily created inside the processor | process |
| Cache | `CacheGroup` → Redis (shared) or memory (process-local fallback) | cross-instance (Redis) |

The service is stateless apart from Redis; anything else you add as process-global state
(registries, caches, trackers) will be per-instance and must tolerate instances restarting at any
time.
