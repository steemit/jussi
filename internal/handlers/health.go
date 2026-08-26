package handlers

import (
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
)

// HealthHandler handles health check requests
type HealthHandler struct {
	SourceCommit string
	DockerTag    string
	Tracker      *cache.BlockNumberTracker
}

// NewHealthHandler creates a new health handler
func NewHealthHandler(sourceCommit, dockerTag string, tracker *cache.BlockNumberTracker) *HealthHandler {
	return &HealthHandler{
		SourceCommit: sourceCommit,
		DockerTag:    dockerTag,
		Tracker:      tracker,
	}
}

// versionInfo returns (sourceCommit, dockerTag), redacted to "unknown"
// unless JUSSI_EXPOSE_VERSION=true — build metadata on a public endpoint
// helps attackers fingerprint the deployment.
func (h *HealthHandler) versionInfo() (string, string) {
	if os.Getenv("JUSSI_EXPOSE_VERSION") == "true" {
		return h.SourceCommit, h.DockerTag
	}
	return "unknown", "unknown"
}

// HandleHealth handles GET /health requests
// Returns health information similar to the legacy project
func (h *HealthHandler) HandleHealth(c *gin.Context) {
	sourceCommit, dockerTag := h.versionInfo()
	response := gin.H{
		"status":        "OK",
		"datetime":      time.Now().UTC().Format(time.RFC3339),
		"source_commit": sourceCommit,
		"docker_tag":    dockerTag,
		"jussi_num":     h.Tracker.GetLastIrreversibleBlockNum(),
	}

	// Add CORS headers
	c.Header("Access-Control-Allow-Origin", "*")
	c.Header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	c.Header("Access-Control-Allow-Headers", "DNT,Keep-Alive,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Content-Range,Range")

	c.JSON(http.StatusOK, response)
}

