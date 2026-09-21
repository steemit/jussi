# 09 — Testing

## Layout

```
internal/<pkg>/*_test.go        unit tests, colocated (cache, config, errors, handlers,
                                middleware, upstream, urn, validators, helpers)
tests/integration/              black-box tests against an httptest jussi + httptest upstream
  server_test.go                  shared harness: setupTestServer(WithUpstream), makeRequest
  mock_upstream_test.go           configurable mock upstream keyed by method name
  cache_middleware_test.go        cache behaviors through the handler
  jsonrpc_test.go / routes_test.go
tests/data/configs/TEST_UPSTREAM_CONFIG.json   legacy-format upstream config fixture
tests/docker-compose.test.yml    (integration env, see tests/README.md)
```

Run everything: `go test ./...`. Everything passing is the baseline for any change.

## What is actually covered

- **URN parsing** (`urn_test.go`): all method formats, `call` variants, string form.
- **Router** (`router_test.go`): longest-prefix selection incl. params-level patterns, using the
  legacy-format fixture.
- **TTL helpers** (`ttl_test.go`), **cache group** (`group_test.go`, incl. promotion TTL expiry),
  **memory cache** eviction/cleanup.
- **Translation** (`processor_translate_test.go`): named-params passthrough, legacy-format
  rewrites, other-namespace passthrough — the guard for pitfall #4.
- **Timeout policy** (`processor_timeout_test.go`): broadcast floor behavior.
- **Circuit breaker unit** (`breaker_test.go`): state machine incl. probe tokens, with injected
  clock.
- **Circuit integration** (`circuit_integration_test.go`): trip/reject/recover/error-envelope/
  kill-switch against a real httptest upstream.
- **Limits** (`limits_test.go`): batch size, account-history cap, custom_json limits.
- **Errors** (`handle_error_test.go`), **validators** (`validators_test.go` — the largest suite),
  **helpers** (JSON escape-free marshal).

## Known coverage gaps (2026-09-21 review) — preferentially close when touching these areas

1. **The production middleware chain is never exercised end-to-end.** `tests/integration` wires
   only `RequestIDMiddleware` + the handler; `BodyParse → ResponseCapture → UpdateBlockNumber →
   CacheLookup → Limits → Error` in their real order (app.SetupRouter) has no test. Several
   shipped bugs lived exactly in that gap (cache-key divergence, `request_id` key mismatch).
   Fix direction: extract the chain assembly from `app.SetupRouter` into a testable constructor
   and use it in integration tests.
2. **Assertion blind spots:** tests that discard the error return (`resp, _ :=`) cannot see
   failures that manifest as `(nil, err)` — the circuit recovery test hid a P0 this way
   (pitfall #8). Audit existing `_, _ =`/`resp, _ :=` patterns when touching them.
3. **"Not cached" is asserted by absence of evidence:** the TTL=-1 test doesn't count upstream
   hits. Cache behavior tests should count mock-upstream hits (add a counter to the mock) rather
   than compare response payloads.
4. **Processor store-path unit tests missing:** error-response caching, `-2` irreversibility,
   `id`-stripping on the stored copy.
5. **Config divergence between test and prod wiring:** tests construct `JSONRPCHandler` with a
   zero `CircuitConfig` (breaker disabled) and TTL `-1` (caching off) — the two axes with the
   biggest production behavior differences run untested by default.

## Conventions for new tests

- Table-driven with `t.Run` subtests, mirroring the existing suites.
- Upstream behavior ⇒ `httptest.Server` + the shared mock; count hits when asserting on
  retry/caching/breaker effects.
- Time-dependent logic ⇒ inject a clock (`BreakerConfig.Now`) or generous margins; the breaker's
  open-duration jitter is 25% by default and `JitterFraction: 0` **cannot actually be configured
  to zero** (`>0` guard in `handlers/circuit.go`) — account for up to `1.25×` the open duration
  when waiting for state transitions.
- Regression tests for pitfalls: when you fix one, add the test that would have caught it, and
  reference the pitfall number in a comment (`// pitfall #8` style).
- Unit tests colocated in `internal/<pkg>`; anything spanning middleware+handler belongs in
  `tests/integration`.

## CI

`.github/workflows/build.yml` builds and tests on PRs. Keep `go vet ./...` clean; `ineffassign`
nolint markers exist in the codebase — don't add new ones casually (one of them currently hides
the breaker P0; dead-store assignments deserve scrutiny, not suppression).
