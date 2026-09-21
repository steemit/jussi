# 03 — Configuration and Routing

## Configuration loading

`internal/config/config.go:LoadConfig()` builds the effective config from three layers,
later overriding earlier:

1. **Defaults** (`setDefaults()`)
2. **Config file** — path from `JUSSI_UPSTREAM_CONFIG_FILE` (default `DEV_config.json`). The same
   file carries *both* the app sections (`server`, `cache`, `logging`, ...) *and* the `upstreams`
   array + `limits` consumed by the router.
3. **Environment variables** — explicit `JUSSI_*` bindings (`bindEnvOverrides()`).

Important: Viper's `AutomaticEnv` is **deliberately not used**. Its key replacer turns *every*
underscore into a dot (`TELEMETRY_OTLP_ENDPOINT` → `telemetry.otlp.endpoint`), which breaks
nested fields whose names contain underscores (`otlp_endpoint`). If you add a config field, you
must add its env mapping to the `envMappings` table in `bindEnvOverrides()` — there is no
automatic discovery. Two manual post-parse steps exist for values Viper cannot convert:
`JUSSI_TELEMETRY_OTLP_HEADERS` (comma-separated `K=V` → map) and
`JUSSI_SERVER_TRUSTED_PROXIES` (comma-separated → slice).

Validation runs at `app.NewApp` (`config.ValidateConfig`): port range, log level/format,
telemetry endpoints, and — currently — a hard requirement that an upstream named `steemd` exists
with well-formed URLs. That steemd requirement is legacy-era; a hivemind-only deployment would be
rejected. If you hit that, reconsider whether the requirement still reflects reality.

### Configuration fields that are declared but NOT wired (as of 2026-09-21)

Setting these has no effect — do not document them as knobs, and either wire or delete them when
touching the area:

- `cache.enabled` (there is no way to disable the cache via config)
- `cache.read_timeout`, `cache.test_before_add`, `cache.read_replica_urls`
- `cache.redis.compression` (no compression exists in `redis.go` despite comments)
- `upstream.websocket_pool.max_msg_size` (no env binding)

`docs/CONFIGURATION.md` additionally documents fields that do not exist at all
(`request_timeout`, `memory.enabled`, `redis.url`, `jaeger.*`, `prometheus.port`,
`limits.batch_size`, ...). Trust the code (and this directory), not that file.

## The upstream config file

```jsonc
{
  "limits": { "accounts_blacklist": ["bad-actor"], "custom_json_size_limit": 8192 },
  "upstreams": [
    {
      "name": "steemd",                    // namespace key; also the /health breaker alias base
      "translate_to_appbase": true,        // rewrite legacy positional formats → condenser_api
      "urls":    [["steemd", "https://..."], ["steemd.condenser_api.get_state", "https://..."]],
      "ttls":    [["steemd", 3], ["steemd.database_api.get_block", -2], ...],
      "timeouts": [["steemd", 5], ["steemd.network_broadcast_api", 0]]
    }
  ]
}
```

- Every entry in `urls`/`ttls`/`timeouts` is a `[prefix, value]` pair; **longest prefix wins**
   against the request URN string.
- Prefixes are matched against the *dot-split* URN, so a pattern may descend into params
  (`steemd.database_api.get_state.params=['/trending']`). Dots inside the params JSON split too —
  pattern and request are split identically, so this round-trips.
- TTL values: positive = seconds, `0` = cache forever, `-1` = never cache,
  `-2` = cache 3s only if the response block is irreversible (see
  [04-caching.md](04-caching.md#ttl-semantics)).
- Timeout values: positive = seconds; `0` falls back to the processor default (15s reads, 30s
  broadcast floor). **`0` no longer means "infinite" as it did in legacy** — see deviations in
  [02-design-philosophy.md](02-design-philosophy.md#deliberate-deviations-from-legacy).
- Unmatched namespaces fall back to the `appbase` upstream's URL, then `steemd`'s — a typo'd
  namespace reaches an upstream and fails there with method-not-found rather than being rejected
  at the gateway. This mirrors legacy and is intentional.

### Prefix-selection subtlety: translation changes the URN

When `translate_to_appbase` is on, legacy-format requests are rewritten to
`appbase.condenser_api.*` **before** the router lookup (see below). That means `ttls`/`timeouts`
entries keyed under `steemd.*` only ever match requests that were *not* translated (i.e.
named-params steemd requests). When tuning production TTLs, verify which namespace the traffic
actually lands under — the DEV config's `steemd.database_api.get_state.params=['/trending']`
entries are inert for translated traffic, which lands on the `appbase` section's entries instead.

## URN parsing (`internal/urn/urn.go`)

The URN is the single identity of a request: routing key, cache key, metrics dimensions.

Method string → URN, in priority order of the regex alternation:

| Client method | Parsed URN |
|---|---|
| `condenser_api.get_block` (any `X_api.method`) | `appbase.X_api.method` |
| `jsonrpc.get_methods` | `appbase.jsonrpc.get_methods` |
| `hivemind.bridge.get_ranked_posts` | `hivemind.bridge.get_ranked_posts` |
| `steemd.get_block` (2-part, first not `*_api`) | `steemd..get_block` (empty API) |
| `get_block` (bare method) | `steemd.database_api.get_block` |
| `call` + `["condenser_api","get_block",[1000]]` | `appbase.condenser_api.get_block`, params `[1000]` |
| `call` + `[0,"get_block",[1000]]` | `steemd.database_api.get_block` (numeric API index: 0=database_api, 1=login_api) |
| `call` + `["database_api","find_accounts",{"accounts":[...]}]` | `appbase.database_api.find_accounts` (named params ⇒ appbase) |

The `call` heuristic: namespace is `appbase` when the API is `condenser_api`/`jsonrpc` or the
inner params are a JSON object, else `steemd`. This matches legacy; don't tune it casually.

`URN.String()` renders `namespace.api.method.params=<json>` (params omitted when nil). Params
maps get key-sorted (Go's `json.Marshal` sorts map keys anyway, so the explicit sort is
belt-and-braces). **This string is the cache key and the routing key.**

## Router (`internal/upstream/router.go` + `trie.go`)

- Three tries (urls / ttls / timeouts), each `Insert(prefix, value)` at startup; lookups are
  `LongestPrefix(urnString)`.
- Lookup URNs are clamped to 4096 bytes (`maxLookupURN`) so absurd client params can't inflate
  the split cost; cache keys are **not** clamped (two requests differing only past 4096 bytes
  cache separately — fine).
- `GetUpstream(urn)` returns `(url, ttl, timeout)`; the ttl/timeout getters default to 3s / 30s
  when nothing matches. Note the effective timeout is then further adjusted in the processor
  (`selectUpstreamTimeout`) — see [06-upstream-resilience.md](06-upstream-resilience.md#timeout-policy).
- `ShouldTranslateToAppbase(name)` exposes the per-upstream translation flag.

## Appbase translation

Implemented by `translateToAppbase` in `handlers/processor.go`. Runs at the top of
`ProcessSingleRequest`, before routing and caching. It applies only when:

- the URN namespace is `steemd` (flag on the `steemd` upstream), or `appbase` (flag on either
  `steemd` or `appbase`), and
- the request uses the **legacy positional wire format** — bare method, `call` triple, or
  `api.method` with array/absent params.

Then: `URN.API → condenser_api`, `URN.Namespace → appbase`; for `call`-style the first params
element is rewritten to `"condenser_api"`; otherwise the method is rebuilt as
`condenser_api.<method>`. Requests with **named (object) params are never rewritten** — they are
already appbase-format, and many appbase methods (`find_accounts`, `list_votes`, ...) do not
exist on `condenser_api` (this exact rewrite broke them once; there is a regression test).

Other namespaces (hivemind `bridge.*`, overseer, ...) are forwarded verbatim, always.

Translation consequence to keep in mind: the cache key is generated **after** translation, so
`get_block` and `condenser_api.get_block` share one cache entry
(`appbase.condenser_api.get_block.params=[...]`). See
[04-caching.md](04-caching.md#two-lookup-layers-middleware-vs-processor) for the middleware/processor key mismatch this
creates.
