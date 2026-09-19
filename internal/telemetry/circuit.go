package telemetry

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// Circuit breaker metrics. GaugeVec so the state of each upstream
// breaker is always exportable (0=closed, 1=open, 2=half-open) without
// requiring traffic to keep a counter fresh.
var (
	UpstreamCircuitState = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "jussi_upstream_circuit_state",
			Help: "Circuit breaker state per upstream (0=closed, 1=open, 2=half-open)",
		},
		[]string{"upstream"},
	)

	UpstreamCircuitRejects = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "jussi_upstream_circuit_rejects_total",
			Help: "Requests rejected by the upstream circuit breaker",
		},
		[]string{"upstream"},
	)
)
