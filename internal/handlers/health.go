package handlers

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

// HealthHandler handles health check requests
type HealthHandler struct {
	SourceCommit string
	DockerTag    string
	// TODO: Add last irreversible block number tracking
}

// NewHealthHandler creates a new health handler
func NewHealthHandler(sourceCommit, dockerTag string) *HealthHandler {
	return &HealthHandler{
		SourceCommit: sourceCommit,
		DockerTag:    dockerTag,
	}
}

// HandleHealth handles GET /health requests
// Returns health information similar to the legacy project
func (h *HealthHandler) HandleHealth(c *gin.Context) {
	response := gin.H{
		"status":        "OK",
		"datetime":      time.Now().UTC().Format(time.RFC3339),
		"source_commit": h.SourceCommit,
		"docker_tag":    h.DockerTag,
		// TODO: Add jussi_num (last irreversible block number) when block tracking is implemented
		// "jussi_num":     h.LastIrreversibleBlockNum,
	}
	
	// Add CORS headers
	c.Header("Access-Control-Allow-Origin", "*")
	c.Header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	c.Header("Access-Control-Allow-Headers", "DNT,Keep-Alive,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Content-Range,Range")
	
	c.JSON(http.StatusOK, response)
}

