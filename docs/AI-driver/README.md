# AI-Driver Docs — Architecture Reference for AI Agents

This directory is the **authoritative internal reference** for anyone (human or AI agent) changing
this codebase. Its goal: let you add features without breaking the existing architecture, reuse
what already exists, and avoid re-stepping on landmines that were already stepped on.

> If a statement here conflicts with `docs/CONFIGURATION.md` or `docs/METRICS.md`, **this directory
> wins** — those documents predate the Go rewrite's current state and contain drift. Verify against
> code anyway; the code is the final truth.

## Reading order

| # | Document | What it covers |
|---|----------|----------------|
| 1 | [01-architecture-overview.md](01-architecture-overview.md) | System context, request lifecycle end-to-end, module inventory, dependency flow |
| 2 | [02-design-philosophy.md](02-design-philosophy.md) | The invariants. Rules you must not break, and *why* they exist |
| 3 | [03-config-and-routing.md](03-config-and-routing.md) | Config loading, upstream JSON format, URN parsing, trie routing, appbase translation |
| 4 | [04-caching.md](04-caching.md) | Cache key design, TTL semantics (including the `-1/0/-2` special values), cache tiers, LIB tracker |
| 5 | [05-request-pipeline.md](05-request-pipeline.md) | Middleware chain order and contracts, handler, processor, batch semantics |
| 6 | [06-upstream-resilience.md](06-upstream-resilience.md) | HTTP client, retry policy, timeout policy, circuit breaker, connection pooling |
| 7 | [07-errors-and-observability.md](07-errors-and-observability.md) | Error taxonomy, logging, telemetry, /health & /metrics, security middleware |
| 8 | [08-known-pitfalls.md](08-known-pitfalls.md) | The scars. Every historical bug class that has bitten this service, with the rule that prevents it |
| 9 | [09-testing.md](09-testing.md) | Test layout, coverage map, known gaps, how to add tests that actually assert behavior |

## The five rules that matter most

If you read nothing else before changing code:

1. **Never serialize a request body to an upstream with `json.Marshal`.** steemd's FC JSON parser
   does not understand `\uXXXX` escapes; use `helpers.MarshalJSONWithoutHTMLEscape` or signatures
   break. (See [08-known-pitfalls.md](08-known-pitfalls.md#1-html-escaping-breaks-transaction-signatures).)
2. **Never re-read the request body.** `BodyParseMiddleware` parses it once; everything downstream
   must use `middleware.ParsedBody(c)`. A second `ShouldBindJSON` silently returns EOF and
   disables whatever check ran second. (See [pitfall #2](08-known-pitfalls.md#2-body-re-reads-silently-disable-middleware).)
3. **Broadcast (`broadcast_*`, `chain_api.push_*`) requests are never retried, never cached.**
   Everything else is treated as idempotent and may be retried once. (See
   [06-upstream-resilience.md](06-upstream-resilience.md#idempotency-split).)
4. **Cache keys are the URN string** (`namespace.api.method.params=[...]`). They are shared with
   Redis across instances and with the legacy Python jussi. Changing key format invalidates the
   entire cache layer at once. (See [04-caching.md](04-caching.md#cache-keys).)
5. **One logic, one implementation.** The worst bugs in this codebase's history came from the same
   rule existing twice (breaker token handling, cache deep-copy, error-response filtering) and only
   one copy being updated. Before duplicating a pattern, extract and share it.
   (See [pitfall #9](08-known-pitfalls.md#9-duplicated-logic-drifts-the-meta-pitfall).)

## Project identity

- jussi is a **JSON-RPC 2.0 reverse proxy** for Steem blockchain APIs: it routes by method
  namespace to upstream services (steemd/appbase/hivemind/...), caches responses, and protects
  the backends.
- This branch (`next`) is the **Go rewrite** of the Python original. The Python implementation
  lives on `master` (legacy). When porting behavior, check legacy semantics explicitly — some were
  deliberately changed (see "Deliberate deviations from legacy" in
  [02-design-philosophy.md](02-design-philosophy.md#deliberate-deviations-from-legacy)).
- Production runs on AWS Elastic Beanstalk; deployment config lives outside this repo
  (`orchestration/deployment/production/jussi-next`), including the production upstream config
  file (`configfiles.json` mounted into the container).

## Conventions

- All repository content (comments, commits, PRs, docs) is **English**. Chinese is for
  conversation only.
- Internal packages live under `internal/` and are not importable outside the module.
- Everything user-facing that could reveal deployment topology (upstream hostnames, URLs, error
  chains) must stay out of client-visible responses; server-side logs and metric labels only.
