package middleware

import (
	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/errors"
	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/urn"
	"github.com/steemit/jussi/internal/validators"
)

// LimitsConfig holds rate limiting configuration
type LimitsConfig struct {
	BatchSizeLimit      int
	AccountHistoryLimit int
}

// LimitsMiddleware enforces rate limits.
//
// This middleware runs before the handler and checks:
//  1. JSON-RPC batch size limit
//  2. get_account_history limit (temporary ahnode protection)
//
// The account_history_limit check is a temporary measure ported from legacy
// Python jussi (commit 94e3ef2, PR #235) to protect ahnode backend from
// excessively large get_account_history queries that degrade performance.
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
				err := errors.NewBatchSizeError(len(batch), config.BatchSizeLimit)
				errors.HandleError(c, err, nil)
				c.Abort()
				return
			}

			// Check account_history_limit for each request in batch
			if config.AccountHistoryLimit > 0 {
				for _, item := range batch {
					if reqMap, ok := item.(map[string]interface{}); ok {
						if err := checkAccountHistoryLimit(reqMap, config.AccountHistoryLimit); err != nil {
							errors.HandleError(c, err, nil)
							c.Abort()
							return
						}
					}
				}
			}
		} else if reqMap, ok := body.(map[string]interface{}); ok {
			// Check account_history_limit for single request
			if config.AccountHistoryLimit > 0 {
				if err := checkAccountHistoryLimit(reqMap, config.AccountHistoryLimit); err != nil {
					errors.HandleError(c, err, nil)
					c.Abort()
					return
				}
			}
		}

		c.Next()
	}
}

// checkAccountHistoryLimit parses a raw JSON-RPC request and checks the limit.
// Extracted as a helper to avoid duplicating the parse-then-validate logic
// between single and batch request paths.
func checkAccountHistoryLimit(reqMap map[string]interface{}, maxLimit int) error {
	parsedURN, err := urn.FromRequest(reqMap)
	if err != nil {
		return nil // not a valid request, let downstream handle it
	}

	jrpcReq := &request.JSONRPCRequest{
		URN: parsedURN,
	}

	return validators.LimitAccountHistoryCountRequest(jrpcReq, maxLimit)
}
