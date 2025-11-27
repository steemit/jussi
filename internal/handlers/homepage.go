package handlers

import (
	"io/ioutil"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
)

// HomepageHandler handles homepage GET requests
type HomepageHandler struct {
	// App version information
	SourceCommit string
	DockerTag    string
	ServiceName  string
	BlockCache   *cache.BlockCache
}

// NewHomepageHandler creates a new homepage handler
func NewHomepageHandler(sourceCommit, dockerTag, serviceName string) *HomepageHandler {
	return &HomepageHandler{
		SourceCommit: sourceCommit,
		DockerTag:    dockerTag,
		ServiceName:  serviceName,
		BlockCache:   cache.NewBlockCache(),
	}
}

// HandleHomepage handles GET / requests
// Returns information in the legacy project format
func (h *HomepageHandler) HandleHomepage(c *gin.Context) {
	// Get source commit from /etc/version file or environment
	sourceCommit := h.getSourceCommit()
	
	// Get docker tag from environment
	dockerTag := h.getDockerTag()
	
	// Get latest block number with caching
	jussiNum, err := h.BlockCache.GetLatestBlockNumber(c.Request.Context())
	if err != nil {
		// If we can't get block number, use 0 as fallback
		jussiNum = 0
	}
	
	response := gin.H{
		"status":        "OK",
		"datetime":      time.Now().UTC().Format("2006-01-02T15:04:05.000000"),
		"source_commit": sourceCommit,
		"docker_tag":    dockerTag,
		"jussi_num":     jussiNum,
	}
	
	// Add CORS headers similar to legacy project
	c.Header("Access-Control-Allow-Origin", "*")
	c.Header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	c.Header("Access-Control-Allow-Headers", "DNT,Keep-Alive,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Content-Range,Range")
	
	c.JSON(http.StatusOK, response)
}

// getSourceCommit gets source commit from /etc/version file or environment
func (h *HomepageHandler) getSourceCommit() string {
	// Try to read from /etc/version file first (Docker build)
	if data, err := ioutil.ReadFile("/etc/version"); err == nil {
		commit := strings.TrimSpace(string(data))
		if commit != "" && commit != "unknown" {
			return commit
		}
	}
	
	// Fallback to environment variable
	if commit := os.Getenv("SOURCE_COMMIT"); commit != "" {
		return commit
	}
	
	// Fallback to handler's stored value
	if h.SourceCommit != "" {
		return h.SourceCommit
	}
	
	return "unknown"
}

// getDockerTag gets docker tag from environment
func (h *HomepageHandler) getDockerTag() string {
	// Try DOCKER_TAG environment variable first
	if tag := os.Getenv("DOCKER_TAG"); tag != "" {
		return tag
	}
	
	// Fallback to handler's stored value
	if h.DockerTag != "" {
		return h.DockerTag
	}
	
	return "latest"
}
