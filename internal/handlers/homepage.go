package handlers

import (
	"net/http"
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

// HandleHomepage handles GET / requests
func (h *HomepageHandler) HandleHomepage(c *gin.Context) {
	response := gin.H{
		"status":        "OK",
		"datetime":      time.Now().UTC().Format(time.RFC3339),
		"source_commit": h.SourceCommit,
		"docker_tag":    h.DockerTag,
		"jussi_num":     h.Tracker.GetLastIrreversibleBlockNum(),
	}

	// Add CORS headers
	c.Header("Access-Control-Allow-Origin", "*")
	c.Header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	c.Header("Access-Control-Allow-Headers", "DNT,Keep-Alive,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Content-Range,Range")

	c.JSON(http.StatusOK, response)
}
