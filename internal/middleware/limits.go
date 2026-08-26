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
	// UpstreamLimits carries the raw "limits" object from the upstream
	// config file (custom_json_size_limit, accounts_blacklist, ...),
	// consumed by validators.LimitBroadcastTransactionRequest.
	UpstreamLimits map[string]interface{}
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

		// Use the body parsed by BodyParseMiddleware. The body has already
		// been consumed at this point in the chain, so a fallback parse here
		// would silently skip every check below (that was the H-1 bug).
		body, ok := ParsedBody(c)
		if !ok {
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

			for _, item := range batch {
				if reqMap, ok := item.(map[string]interface{}); ok {
					if err := checkRequestLimits(reqMap, config); err != nil {
						errors.HandleError(c, err, nil)
						c.Abort()
						return
					}
				}
			}
		} else if reqMap, ok := body.(map[string]interface{}); ok {
			if err := checkRequestLimits(reqMap, config); err != nil {
				errors.HandleError(c, err, nil)
				c.Abort()
				return
			}
		}

		c.Next()
	}
}

// checkRequestLimits applies per-request limits to a raw JSON-RPC request:
//   1. get_account_history limit (temporary ahnode protection)
//   2. broadcast/custom_json limits (size cap + accounts blacklist)
func checkRequestLimits(reqMap map[string]interface{}, config *LimitsConfig) error {
	parsedURN, err := urn.FromRequest(reqMap)
	if err != nil {
		return nil // not a valid request, let downstream handle it
	}

	jrpcReq := &request.JSONRPCRequest{
		URN: parsedURN,
	}

	if config.AccountHistoryLimit > 0 {
		if err := validators.LimitAccountHistoryCountRequest(jrpcReq, config.AccountHistoryLimit); err != nil {
			return err
		}
	}

	return validators.LimitBroadcastTransactionRequest(jrpcReq, config.UpstreamLimits)
}

