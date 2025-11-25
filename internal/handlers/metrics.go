package handlers

import (
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

// MetricsHandler handles Prometheus metrics endpoint
type MetricsHandler struct{}

// HandleMetrics handles GET /metrics requests
func (h *MetricsHandler) HandleMetrics(c *gin.Context) {
	// Prometheus handler
	promhttp.Handler().ServeHTTP(c.Writer, c.Request)
}

