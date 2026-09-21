# 07 — Errors and Observability

## Error taxonomy (`internal/errors`)

All client-visible errors are `*errors.JSONRPCError` (`code`, `message`, optional `data` map).

- Standard JSON-RPC codes: `-32700` parse, `-32600` invalid request, `-32601` method not found,
  `-32602` invalid params, `-32603` internal.
- Jussi-specific codes (`1000`+): request/response timeout, `1100` upstream response error
  (also the circuit-open class), `1200/1300` invalid namespace/api, `1500` invalid upstream URL,
  `1600` batch size, `1700` limits, `1701` account-history limit, `1800` custom_json length.
- Constructors in `errors.go` / `errors_extended.go`; keep new codes in the 1000-space and
  documented here.

**`errors.HandleError(c, err, requestID)` is the single client-facing renderer.** Its contract:

- Wraps the response as HTTP **200** + JSON-RPC error envelope (id, jussi_request_id from the
  `jussi_request_id` ctx key, trace_id from the current span).
- Unwraps with `errors.As`, so a typed error wrapped anywhere with `%w` reaches the client with
  its code/message intact — wrap typed errors with `%w`, never re-wrap them into new strings.
- Non-typed errors are **logged server-side** (`slog.Error`) and replaced by a generic
  `Internal error` — their text may contain upstream URLs/internal topology that must not leak
  (design rule #4 in 02). Internal detail goes in logs, never in the client message.

Client-safe vs server-only placement, by current convention:

| Signal | Client sees | Server-side |
|---|---|---|
| Circuit open | code 1100, "Upstream temporarily unavailable", generic details | metric label (`breakerKey`), `slog.Warn` with upstream |
| Upstream transport failure | generic Internal error | full error chain in log |
| Broadcast failure | upstream's JSON-RPC error (+trace_id) | structured `slog.Warn` with method/namespace/upstream_url/request id |
| /health breaker states | alias names or sha256 digests | — |

## Logging

Two systems currently coexist (known wart, 2026-09-21 review):

- **zerolog** (`internal/logging`): app-level structured JSON for Scalyr (startup, shutdown,
  wiring messages). Configured via `logging.*`.
- **`log/slog`** default handler: used by the hot paths (processor, breaker rejection, router
  summary, error renderer). Emits text to stderr and is **not** part of the zerolog JSON stream.

If you add logging on a hot path, match the surrounding code (slog there), but be aware the
split exists; consolidating onto one pipeline is a welcome refactor, not a regression.

Never log full request params at info level on the broadcast path; `trace_id` +
`jussi_request_id` are the correlation keys.

## Traces

`internal/telemetry` sets up OTLP/HTTP export (`telemetry.otlp_endpoint`, optional path +
headers for OpenObserve-style collectors) with TraceContext-only propagation — **baggage is
deliberately not propagated** (public gateway; client-supplied baggage is untrusted input).

Span tree per request: `jussi.request` (TracingMiddleware / otelgin) → `jussi.process_request`
→ `jussi.cache.lookup` / `jussi.upstream.http` / `jussi.cache.store`. Batch adds
`jussi.process_batch`. Attributes carry namespace/api/method, upstream URL, TTL, cache-hit flag.
`RecordSpanParams` puts the full params JSON into a span event — useful for reads, but it sends
transaction bodies into trace storage for broadcasts; truncate/skip if you touch it.

Trace context is injected into upstream request headers (`propagator.Inject` in
`HTTPClient.Request`) so upstreams/jaeger can stitch the full path.

## Metrics

Endpoint: `GET /metrics` (path configurable), served by `promhttp` from the default registry.
Access control in `app.SetupRouter`: `prometheus.localhost_only` → `LocalhostOnlyMiddleware`,
else `prometheus.allowed_ips` → CIDR/IP whitelist. Client-IP integrity depends on
`server.trusted_proxies` being set to the LB's CIDR in production (otherwise XFF is ignored —
safe default, but the whitelist then matches the LB address).

**Live, recorded metrics** (the ones dashboards should use):

| Metric | Labels | Where recorded |
|---|---|---|
| `jussi_requests_total` | namespace, method, status(success/error/workaround_*) | processor |
| `jussi_batch_size` | — | processor |
| `jussi_cache_operations_total` | operation(get/set), result(hit/miss/success/skipped) | processor |
| `jussi_upstream_requests_total` | upstream, protocol | processor |
| `jussi_upstream_request_duration_seconds` | upstream, protocol | processor |
| `jussi_upstream_errors_total` | upstream, protocol, error_type | processor |
| `jussi_upstream_circuit_state` | upstream | processor / callSteemd |
| `jussi_upstream_circuit_rejects_total` | upstream | processor / callSteemd |

**Declared but never recorded (always zero)** — do not build dashboards on them, and either wire
or delete when touching telemetry: `jussi_request_duration_seconds`, `jussi_request_errors_total`,
`jussi_cache_hit_ratio`, `jussi_cache_operation_duration_seconds`, `jussi_websocket_pool_*`.
(`docs/METRICS.md` predates this and documents several of the dead ones extensively — trust the
table above.)

Known measurement blind spots: middleware-layer cache hits (they bypass the processor), and
cache backend errors (CacheGroup swallows them).

## Health endpoint

`GET /health` (and `GET /`, same shape): `status`, `datetime`, redacted `source_commit` /
`docker_tag` (unless `JUSSI_EXPOSE_VERSION=true`), `jussi_num` (LIB), and when wired:
`circuit_states` (breaker state per alias) + `circuit_degraded` / `circuit_worst_state` when any
breaker is not closed.

Properties to preserve:

- **Always HTTP 200 while the process is alive** — ELB health checks must not flap on upstream
  trouble (degradation is an alarm via the gauge, not an instance kill). If you want a
  failing health mode, gate it behind a separate path.
- **Alias discipline**: breaker keys are `scheme://host`; the public payload maps them through
  `BreakerAliases` (configured upstream names, `-2/-3` suffixes for multi-host pools, stable
  ordering) and sha256-digest fallbacks. Hostnames never appear. If you add upstream URL shapes
  to the config, keep `BreakerAliases`' pair-length rule in sync with the router's (they
  currently disagree on `==2` vs `>=2` — known minor gap).
- CORS-open (`*`) — anything added to this payload is public information by definition.

## Security-relevant middleware

- `BodyParseMiddleware`: request body cap (default 4 MiB) via `http.MaxBytesReader`.
- `LocalhostOnlyMiddleware` / `IPWhitelistMiddleware` (metrics): CIDR-aware; rely on
  trusted-proxy config, see above.
- Upstream response bodies are capped at 64 MiB (`maxUpstreamResponseBody`) before parse.
- URNs fed to trie lookups are clamped at 4096 bytes (`maxLookupURN`) to bound split cost under
  absurd client input.
- OTLP uses TLS automatically for `https://` endpoints (credentials in headers).

When adding a new public surface, run it against rule #4 in
[02-design-philosophy.md](02-design-philosophy.md): what does it reveal about topology?
