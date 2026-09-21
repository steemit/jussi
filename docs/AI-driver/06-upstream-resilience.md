# 06 — Upstream Resilience

The upstream path has four cooperating policies: connection pooling, timeout, retry, and the
circuit breaker. They were each shaped by a production incident; change one with the others in
mind.

## Connection pool (`internal/upstream/http.go`)

- **HTTP/1.1 forced** (`ForceAttemptHTTP2: false`, `NextProtos: ["http/1.1"]`): HTTP/2
  multiplexing pinned all requests onto a single TCP connection to the ALB, killing load
  distribution (commit e79cbf2). Don't re-enable per-host HTTP/2 without revisiting this.
- `MaxIdleConnsPerHost: 10`, `MaxConnsPerHost: 20`, `IdleConnTimeout: 90s`. The low per-host cap
  forces connection rotation so one sticky backend behind the ALB doesn't absorb all traffic.
  Capacity caveat: throughput per host ≈ `MaxConnsPerHost / avg_latency` — at 20 connections
  this is ~200 rps at 100ms latency and much less when the upstream is slow; excess requests
  queue **inside** `http.Transport` until their own deadline fires. If you raise instance
  throughput targets, measure and raise the cap deliberately.
- No `http.Client.Timeout` — the per-request context (below) is the only deadline, so retries
  share one budget.

## Idempotency split

`validators.IsBroadcastTransactionRequest`: `broadcast_*` (prefix, any API) plus
`chain_api.push_transaction` / `push_block`. These are the non-idempotent writes; everything
else is treated as an idempotent read. The split decides retry, timeout floor, and (by config
convention, TTL `-1`) caching. New write-shaped method ⇒ extend the classifier, not call sites.

## Timeout policy

`handlers/processor.go:selectUpstreamTimeout`:

1. per-URN configured timeout (router trie);
2. `<= 0` → 15s default (`defaultUpstreamTimeout`) — note the router itself returns 30 when
   **no entry matched**, so "no entry" and "entry = 0" land on different defaults (30s vs 15s);
   this inversion vs the code comment is a known wart from the 2026-09-21 review — unify when
   touching;
3. broadcast → floored to 30s (`broadcastMinimumTimeout`): a synchronous broadcast legitimately
   waits ~3s/block and clipping it surfaces as wallet "broadcast timeout"; the floor log is
   throttled to once/minute/method.

Legacy `0 = infinite` is **gone by design** (see deviations in 02). The server's
`WriteTimeout: 35s` covers the 30s floor — keep them coupled.

## Retry policy (`internal/upstream/retry.go`)

`DefaultRetryConfig`: **2 attempts total**, 100ms initial backoff doubling to 500ms cap, 25%
jitter. Deliberately tighter than legacy (3 retries / multi-second) so the worst-case budget
stays under wallet timeouts.

`IsRetriableUpstreamError` retries only: EOF/ErrUnexpectedEOF, net errors with `Timeout()`,
`UpstreamStatusError` with 5xx, and a conservative string list (connection reset/refused, broken
pipe, no such host, i/o timeout, network unreachable). It **never** retries `context.Canceled` /
`context.DeadlineExceeded` — the caller's budget is gone; another attempt just burns it
(this is the lesson of legacy commit 9cf36ea's expiration-on-retry pile-up).

Only the idempotent path uses `RequestWithRetry`; broadcasts call `Request` exactly once —
a transport blip must never double-submit a transaction.

Known gap (2026-09-21 review): upstream **4xx** (notably 429) is treated as success by both the
client (body returned as-is if JSON parses) and the breaker (`Record(true)`). Rate-limit
responses are therefore invisible to resilience. If you fix it, decide: 429/503 → breaker
failure; non-JSON 4xx body → structured upstream error instead of a parse error.

## Circuit breaker (`internal/upstream/breaker.go`)

Per-upstream (`scheme://host` via `Registry.For` — pooled URL variants share one breaker), lazy
creation, defaults: 30s window / 3s buckets / 50% failure rate / 20 min-samples / 10s open
duration / 25% jitter (tunable via `upstream.circuit.*`; `upstream.circuit.enabled=false` is the
kill switch — when disabled the breaker still counts but the processor never rejects).

State machine:

- **closed**: sliding-window failure rate ≥ threshold with ≥ min samples → trip.
- **open**: all requests rejected (`Allow() == false`) until `openFor` (10s + jitter — jitter
  desynchronizes multiple jussi instances probing in lockstep) elapses.
- **half-open**: exactly **one** probe admitted (returns a `ProbeToken`); everyone else rejected.
  Probe succeeds → `reset()` (closed + window cleared so the tripping rate doesn't re-trip
  instantly). Probe fails → re-open a full cycle. A liveness guard re-admits after another
  `OpenDuration` if a probe never records (lost response/panic).

Failure inputs: transport errors, timeouts/deadlines (including jussi's own), and 5xx. Any
successful response counts as success.

**The Allow/Record protocol is the sharp edge.** `Allow()` in half-open hands the probe token to
exactly one caller; `Record(ok, token)` with a `nil` token is ignored in half-open (so stale
in-flight requests can't answer the probe). Two consequences for call sites:

1. The token must flow from `Allow()` to `Record()` — discarding it strands the breaker in
   half-open forever (this is precisely the P0 from the 2026-09-21 review:
   `callHTTPUpstream` had `probeToken = nil` unconditionally; `callSteemd` in
   `get_state_workaround.go` shows the correct form — nil it only when the circuit is disabled).
2. Don't call `Record` from a different request than the one that got the token.

When touching either call site, extract the shared guard/record helper instead of maintaining
two copies.

Config quirk: `handlers/circuit.go:breakerConfig` treats `0` as "unset" (`> 0` guards), so
e.g. `jitter_fraction=0` cannot be expressed — it silently becomes the default 0.25.

## What the breaker is for (context for future tuning)

jussi cancels requests at their deadline, but the SQL the upstream already started keeps running
and holding its DB connection. Unthrottled arrivals during an upstream slowdown therefore
prevent the backend from ever draining — one slow backend becomes an outage (2026-09-18
hivemind storm). The breaker converts that state into fast local failures: the arrival burst
stops, in-flight work finishes, the backend recovers, the probe reopens the path. Tuning should
preserve that story: `min_samples` high enough that normal blips don't trip, `open_duration`
long enough to let queries drain, jitter so N instances don't probe in unison.

## Observability hooks on this path

- `jussi_upstream_requests_total{upstream,protocol}` / `jussi_upstream_request_duration_seconds`
  / `jussi_upstream_errors_total{upstream,protocol,error_type}`
- `jussi_upstream_circuit_state{upstream}` gauge (0 closed / 1 open / 2 half-open) and
  `jussi_upstream_circuit_rejects_total{upstream}` — set at every Allow/Record so state changes
  surface without waiting for traffic
- `/health` mirrors breaker states under configured-name aliases (hostnames never leak;
  see [07](07-errors-and-observability.md#health-endpoint))
- server-side `slog` warn at every rejection and every broadcast failure
