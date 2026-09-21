# 05 — Request Pipeline

The pipeline is the ordered middleware chain plus the handler/processor. The order is defined in
`internal/app/app.go:SetupRouter()` and **is contractual** — several pairs only work in one
order.

## Middleware chain and contracts

Registered in this order (all `router.Use`):

| # | Middleware | Contract / ordering constraint |
|---|------------|-------------------------------|
| 1 | `gin.Recovery()` | First; converts panics in the handler goroutine to 500. Does **not** cover per-batch-item goroutines (see Batch). |
| 2 | `otelgin` (if telemetry on) | Wraps everything below in a server span. |
| 3 | `RequestIDMiddleware` | Sets/echoes `x-jussi-request-id`; ctx key **`jussi_request_id`** (exact spelling — other code reads it, e.g. `errors.HandleError`). |
| 4 | `TracingMiddleware` | Starts the `jussi.request` span used by the processor's child spans. |
| 5 | `ErrorMiddleware` | Dead path today (nothing appends to `c.Errors`); kept historically. If you wire `c.Error()` into it, note it reads a `request_id` ctx key that is never set — fix before relying on it. |
| 6 | `BodyParseMiddleware` | Enforces `server.max_body_size` (default 4 MiB), parses body **once** → ctx `parsed_body`, restores the raw body for legacy readers. Must precede every body consumer. |
| 7 | `ResponseCaptureMiddleware` | Wraps `c.Writer` in the body-capturing writer. Must precede everything that writes a response and #8. |
| 8 | `UpdateBlockNumberMiddleware` | After `c.Next()`: type-asserts the writer from #7 and scans the response for `last_irreversible_block_num` → LIB tracker. |
| 9 | `CacheLookupMiddleware` | Single-POST cache lookup (pre-translation key; see [04-caching.md](04-caching.md#two-lookup-layers-middleware-vs-processor)). On hit: respond + `Abort`. Runs after #6 (needs `ParsedBody`). |
| 10 | `LimitsMiddleware` | Batch size cap (`server.batch_size_limit`), `get_account_history` limit cap, broadcast custom_json size + account blacklist (from the upstream file's `limits`). Uses `ParsedBody`; a body it cannot parse is skipped by design. |

`/health`, `/`, `/metrics` are separate routes; middlewares 6/9/10 no-op on GET.

**Rule:** any new middleware that reads the body must read `middleware.ParsedBody(c)` and be
registered after `BodyParseMiddleware`. Any middleware that inspects the response body must be
registered after `ResponseCaptureMiddleware` and read the writer via the `*responseWriter` type
assertion (the `response_body` ctx key set after `Next()` is written too late for in-request
consumers and currently has no readers).

## Handler (`handlers/jsonrpc.go`)

`POST /` → `JSONRPCHandler.HandleJSONRPC`:

1. Take `parsed_body` (fallback re-parse only for test setups without middleware #6).
2. `validators.ValidateJSONRPCRequest`: `jsonrpc == "2.0"`, string method, typed `id`/`params`,
   and **no unknown keys** (strict; legacy-compatible).
3. Single object → `handleSingleRequest`; array → `handleBatchRequest`.

Single: `request.FromHTTPRequest` (parses the URN) → processor → `c.JSON(200, response)`.
Processor errors go through `errors.HandleError` — one special case maps the string
`"no upstream configuration found"` to `NewInvalidNamespaceError` (string-matched; if you touch
that error message, update the matcher — better, introduce a sentinel error).

Batch:

- Each item parsed independently; invalid items get in-place `-32600` responses; **response[i]
  always corresponds to reqs[i]** (original positions preserved).
- Valid items processed concurrently (one goroutine each, see Batch below).
- If the batch-level call fails, valid slots get `-32603`; the batch result is always a JSON
  array per JSON-RPC 2.0.

## Processor (`handlers/processor.go`)

`ProcessSingleRequest` is the spine; in order:

1. `translateToAppbase` (see [03](03-config-and-routing.md#appbase-translation)).
2. get_state workaround intercepts (temporary).
3. `router.GetUpstream(URN.String())` → URL/TTL/timeout; attaches as `req.Upstream`.
4. Cache lookup (if cacheable) — deep-copy + `id` reinject on hit.
5. `callHTTPUpstream`:
   - breaker `Allow()` (reject fast when open — structured error, no hostname),
   - `selectUpstreamTimeout` → `context.WithTimeout`,
   - broadcast → single `Request`; else `RequestWithRetry` (see [06](06-upstream-resilience.md)),
   - breaker `Record(outcome, probeToken)` — **the probe token from `Allow()` must reach
     `Record` un-discarded** (see below),
   - metrics: requests, duration, errors, circuit state gauge.
6. Cache store (if cacheable; deep copy, `id` stripped).
7. `response["id"] = req.ID`; if `response["error"]`: enrich `data` with `trace_id` +
   `jussi_request_id`, mark span, count `RequestsTotal{...,error}`; broadcast errors also log a
   structured warn.

⚠ **Critical invariant — the breaker probe token.** In half-open, exactly one request carries the
probe token; `Record(ok, nil)` in half-open is ignored by design (stale requests must not answer
the probe). The call site therefore must keep the token from `Allow()` and pass it to `Record`,
nil'ing it only when the circuit is disabled. As of the 2026-09-21 review, `callHTTPUpstream`
unconditionally discards it (`probeToken = nil`), which strands the breaker in half-open forever
after one trip — upstream serves 1 probe per open-duration and rejects the rest until restart.
The correct pattern is in `get_state_workaround.go:callSteemd`. When fixing, extract one shared
helper and use it at both call sites; the recovery integration test must assert on the **error**
return (rejections come back as `(nil, err)` and a `resp, _ :=` loop hides them — that is why
this bug shipped).

### Timeout selection

`selectUpstreamTimeout(req)`:

- configured per-URN timeout; `<= 0` (incl. absent-entry router default is 30, explicit `0`) →
  effective defaults,
- broadcast methods floored to 30s (logged once/minute/method when the floor overrides config),
- read default 15s (`defaultUpstreamTimeout`).

The server-level `WriteTimeout` (35s) is sized to cover the 30s broadcast floor; if you raise
broadcast timeouts, raise the server's WriteTimeout with it.

### Batch concurrency

`ProcessBatchRequest` spawns one goroutine per item, collecting via a buffered channel.
Batch size is capped by `LimitsMiddleware` (default 50; production sets 250). Each goroutine has
**no panic guard** — Gin's Recovery does not reach them; a panic in the item path kills the
process. If you add anything type-assertion-heavy to the item path, either guard it or add
`defer recover()` in the loop body (known gap from the 2026-09-21 review).

There is no whole-batch deadline; the server `WriteTimeout` is the only ceiling. Items share the
request context (cancellation of the client connection cancels all items).

## Response shaping rules

- Successful and error JSON-RPC responses are returned with HTTP **200** (JSON-RPC-over-HTTP
  convention; the spec-level error lives in the body).
- Notifications (requests without `id`) still receive a response with `id: null` — same as
  legacy; clients depend on it.
- Client `id` is echoed from the request, never from the upstream (jussi sends its own numeric
  `id` = `batchIndex + 1000000` upstream and overwrites it in the response).
- Responses are serialized by gin's `c.JSON` (HTML-escaped `<>&`) — safe for standards-compliant
  clients; only the **upstream request** direction requires escape-free serialization
  (steemd's parser). Do not "unify" these.
