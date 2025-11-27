package handlers

import (
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
)

// HomepageHandler handles homepage GET requests
type HomepageHandler struct {
	// App version information
	SourceCommit string
	DockerTag    string
	ServiceName  string
}

// NewHomepageHandler creates a new homepage handler
func NewHomepageHandler(sourceCommit, dockerTag, serviceName string) *HomepageHandler {
	return &HomepageHandler{
		SourceCommit: sourceCommit,
		DockerTag:    dockerTag,
		ServiceName:  serviceName,
	}
}

// HandleHomepage handles GET / requests
// Returns information similar to the legacy project's health endpoint
func (h *HomepageHandler) HandleHomepage(c *gin.Context) {
	// Get hostname for additional context
	hostname, _ := os.Hostname()
	
	response := gin.H{
		"status":        "OK",
		"datetime":      time.Now().UTC().Format(time.RFC3339),
		"service":       h.ServiceName,
		"version":       "go-rewrite",
		"source_commit": h.SourceCommit,
		"docker_tag":    h.DockerTag,
		"hostname":      hostname,
		"description":   "Jussi JSON-RPC 2.0 reverse proxy - Go implementation",
		"endpoints": gin.H{
			"health":   "/health",
			"jsonrpc":  "POST /",
		},
		"note": "Metrics endpoint (/metrics) is restricted to localhost access only for security",
	}
	
	// Add CORS headers similar to legacy project
	c.Header("Access-Control-Allow-Origin", "*")
	c.Header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	c.Header("Access-Control-Allow-Headers", "DNT,Keep-Alive,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Content-Range,Range")
	
	c.JSON(http.StatusOK, response)
}
