package middleware

import (
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// RequestIDMiddleware adds request ID to context
func RequestIDMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Get or generate request ID
		requestID := c.GetHeader("x-jussi-request-id")
		if requestID == "" {
			requestID = uuid.New().String()
		}

		c.Set("jussi_request_id", requestID)
		c.Header("x-jussi-request-id", requestID)

		c.Next()
	}
}

