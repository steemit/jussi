package telemetry

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// Request metrics
	RequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "jussi_requests_total",
			Help: "Total number of JSON-RPC requests",
		},
		[]string{"namespace", "method", "status"},
	)

	RequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "jussi_request_duration_seconds",
			Help:    "Request latency in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"namespace", "method"},
	)

	RequestErrors = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "jussi_request_errors_total",
			Help: "Total number of request errors",
		},
		[]string{"namespace", "method", "error_type"},
	)

	BatchSize = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "jussi_batch_size",
			Help:    "Batch request size distribution",
			Buckets: []float64{1, 5, 10, 25, 50, 100},
		},
	)

	// Cache metrics
	CacheOperations = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "jussi_cache_operations_total",
			Help: "Total number of cache operations",
		},
		[]string{"operation", "result"},
	)

	CacheHitRatio = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "jussi_cache_hit_ratio",
			Help: "Cache hit ratio",
		},
	)

	CacheOperationDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "jussi_cache_operation_duration_seconds",
			Help:    "Cache operation latency in seconds",
			Buckets: []float64{0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0},
		},
		[]string{"operation"},
	)

	// Upstream metrics
	UpstreamRequests = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "jussi_upstream_requests_total",
			Help: "Total number of upstream requests",
		},
		[]string{"upstream", "protocol"},
	)

	UpstreamRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "jussi_upstream_request_duration_seconds",
			Help:    "Upstream call latency in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"upstream", "protocol"},
	)

	UpstreamErrors = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "jussi_upstream_errors_total",
			Help: "Total number of upstream errors",
		},
		[]string{"upstream", "protocol", "error_type"},
	)

	// Connection pool metrics
	WebSocketPoolSize = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "jussi_websocket_pool_size",
			Help: "WebSocket pool size",
		},
		[]string{"upstream"},
	)

	WebSocketPoolActive = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "jussi_websocket_pool_active",
			Help: "Active WebSocket connections",
		},
		[]string{"upstream"},
	)

	WebSocketPoolIdle = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "jussi_websocket_pool_idle",
			Help: "Idle WebSocket connections",
		},
		[]string{"upstream"},
	)
)

