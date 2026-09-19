# Jussi Circuit Breaker — Observability & Alerting Design

Target stack: watchtower (Prometheus + Grafana + OpenObserve). Everything below
is emitted by jussi already (metrics on :9000, states also in /health), so the
Grafana work is dashboards + alert rules only — no new jussi-side collection.

## Signals emitted per jussi instance

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `jussi_upstream_circuit_state` | gauge | `upstream` (`scheme://host`) | 0=closed, 1=open, 2=half-open |
| `jussi_upstream_circuit_rejects_total` | counter | `upstream` | requests rejected locally (never reached upstream) |
| `jussi_upstream_requests_total` | counter | `upstream`, `protocol` | requests dialed |
| `jussi_upstream_errors_total` | counter | `upstream`, `protocol`, `error_type` | dialed requests that failed |
| `jussi_upstream_request_duration_seconds` | histogram | `upstream`, `protocol` | upstream latency |
| `/health` JSON | — | — | `circuit_states` (keyed by configured upstream name — never a backend hostname), `circuit_degraded`, `circuit_worst_state` |

## Golden dashboard (one row per upstream host)

1. **Circuit state** — `jussi_upstream_circuit_state` as a state timeline (0/1/2
   colored green/red/yellow). This is the "is jussi currently refusing to talk
   to this backend" panel. Should be flat green 24/7; any red is an event.
2. **Reject rate** — `rate(jussi_upstream_circuit_rejects_total[5m])`. This is
   the *user-impact* series: every unit is a request that failed without even
   trying the upstream.
3. **Upstream error ratio** —
   `sum(rate(jussi_upstream_errors_total[5m])) by (upstream) /
    sum(rate(jussi_upstream_requests_total[5m])) by (upstream)`.
   This is the *leading* indicator: it rises before the breaker trips.
4. **Latency p99** —
   `histogram_quantile(0.99, sum(rate(jussi_upstream_request_duration_seconds_bucket[5m])) by (le, upstream))`.
   Catches saturation while the error ratio still looks fine.
5. **Aggregate over instances** — `sum by (upstream)` of the above across all
   jussi instances distinguishes "one instance sick" (local issue) from "all
   instances sick" (upstream issue).

## Alert rules (Prometheus format, thresholds from the 09-18 incident profile)

```yaml
groups:
- name: jussi-circuit-breaker
  rules:
  # P0: breaker actually open on any instance = jussi is refusing traffic.
  - alert: JussiCircuitOpen
    expr: max by (instance, upstream) (jussi_upstream_circuit_state) == 1
    for: 1m
    labels: {severity: critical}
    annotations:
      summary: "jussi {{ $labels.instance }} circuit OPEN for {{ $labels.upstream }}"

  # P1: rejections happening at all = active user impact.
  - alert: JussiCircuitRejects
    expr: increase(jussi_upstream_circuit_rejects_total[5m]) > 0
    for: 0m
    labels: {severity: warning}
    annotations:
      summary: "jussi rejected {{ $value }} upstream calls in 5m ({{ $labels.upstream }})"

  # P1: pre-trip warning — error ratio climbing toward the 50% trip line.
  - alert: JussiUpstreamErrorRatioHigh
    expr: |
      sum by (upstream) (rate(jussi_upstream_errors_total[5m]))
        / sum by (upstream) (rate(jussi_upstream_requests_total[5m])) > 0.2
    for: 10m
    labels: {severity: warning}
    annotations:
      summary: "upstream {{ $labels.upstream }} error ratio >20% for 10m (trip line is 50%)"

  # P2: latency saturation without errors (pool-queue signature).
  - alert: JussiUpstreamLatencyP99High
    expr: |
      histogram_quantile(0.99,
        sum by (le, upstream) (rate(jussi_upstream_request_duration_seconds_bucket[5m]))) > 3
    for: 10m
    labels: {severity: warning}
    annotations:
      summary: "upstream {{ $labels.upstream }} p99 >3s for 10m"
```

Rationale for thresholds: the breaker trips at 50% failure over a 30s window
with ≥20 samples; the >20%-for-10m alert fires well before that. The 09-18
storm showed jussi logging ~47000 deadline-cancellations per 3 minutes at
peak — `JussiCircuitRejects` at >0 is deliberately sensitive because in the
old world that volume was invisible until users hit 504s.

## Cross-service view (what would have caught 09-18 in minutes)

Chain: wallet SSR latency (wallet ALB p99) ↑ → jussi circuit rejects + state ↑
→ hivemind upstream error ratio ↑ / latency p99 ↑ → RDS connections (58 =
pool ceiling) + hivemind DB_SLOW rate (Scalyr). A single Grafana row with
these panels per service makes the propagation direction obvious in one
glance. RDS-side panels (`DatabaseConnections`, `CPUUtilization`) come from
CloudWatch — either via the CloudWatch datasource in Grafana or the existing
yace/cloudwatch-exporter pattern.

## Scalyr (logs) vs Prometheus (metrics) split

- Prometheus: aggregate health, rates, alerting — what is on fire, how much.
- Scalyr: per-request forensics — which method/URL/account drove the storm
  (`DB_SLOW`, `DISCUSSION_SLOW`, jussi deadline logs). Keep the existing
  numeric-query playbooks; they answer "why", alerts answer "how bad".

## Ops runbook hook

When `JussiCircuitOpen` fires: 1) check the upstream's own dashboard (hivemind
EB health, RDS connections); 2) if the upstream is genuinely sick, scaling/
restarting it is the fix — the breaker is doing its job; 3) if the upstream is
healthy, suspect a jussi-side network issue and check
`jussi_upstream_request_duration_seconds` from the instance itself;
4) `JUSSI_UPSTREAM_CIRCUIT_ENABLED=false` on new instances is the documented
kill switch if the breaker misbehaves.
