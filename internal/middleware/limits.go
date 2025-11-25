package middleware

import (
	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/errors"
)

// LimitsConfig holds rate limiting configuration
type LimitsConfig struct {
	BatchSizeLimit       int
	AccountHistoryLimit  int
	BlacklistAccounts    []string
}

// LimitsMiddleware enforces rate limits
func LimitsMiddleware(config *LimitsConfig) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Only process POST requests
		if c.Request.Method != "POST" {
			c.Next()
			return
		}

		// Parse request body
		var body interface{}
		if err := c.ShouldBindJSON(&body); err != nil {
			c.Next()
			return
		}

		// Check batch size
		if batch, ok := body.([]interface{}); ok {
			if len(batch) > config.BatchSizeLimit {
				errors.HandleError(c, &errors.JSONRPCError{
					Code:    errors.CodeBatchSizeError,
					Message: "Batch size exceeds limit",
					Data: map[string]interface{}{
						"batch_size":       len(batch),
						"batch_size_limit": config.BatchSizeLimit,
					},
				}, nil)
				c.Abort()
				return
			}
		}

		c.Next()
	}
}

