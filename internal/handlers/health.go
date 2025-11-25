package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
)

// HealthHandler handles health check requests
type HealthHandler struct {
	// Will be populated with app state
}

// HandleHealth handles GET /health requests
func (h *HealthHandler) HandleHealth(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":   "OK",
		"datetime": "", // TODO: Add timestamp
	})
}

