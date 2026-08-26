package handlers

import (
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
)

// HomepageHandler handles homepage GET requests
type HomepageHandler struct {
	SourceCommit string
	DockerTag    string
	Tracker      *cache.BlockNumberTracker
}

// NewHomepageHandler creates a new homepage handler.
func NewHomepageHandler(sourceCommit, dockerTag string, tracker *cache.BlockNumberTracker) *HomepageHandler {
	return &HomepageHandler{
		SourceCommit: sourceCommit,
		DockerTag:    dockerTag,
		Tracker:      tracker,
	}
}

// versionInfo mirrors HealthHandler.versionInfo — redacted unless
// JUSSI_EXPOSE_VERSION=true.
func (h *HomepageHandler) versionInfo() (string, string) {
	if os.Getenv("JUSSI_EXPOSE_VERSION") == "true" {
		return h.SourceCommit, h.DockerTag
	}
	return "unknown", "unknown"
}

// HandleHomepage handles GET / requests
func (h *HomepageHandler) HandleHomepage(c *gin.Context) {
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
