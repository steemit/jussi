package middleware

import (
	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/errors"
)

// ErrorMiddleware handles errors and returns JSON-RPC compliant responses
func ErrorMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Next()

		// Check if there are any errors
		if len(c.Errors) > 0 {
			err := c.Errors.Last()
			
			// Try to extract request ID from context
			requestID, _ := c.Get("request_id")
			
			// Handle error
			var jsonrpcErr *errors.JSONRPCError
			if jErr, ok := err.Err.(*errors.JSONRPCError); ok {
				jsonrpcErr = jErr
			} else {
				jsonrpcErr = errors.NewInternalError(err.Error())
			}

			errors.HandleError(c, jsonrpcErr, requestID)
			c.Abort()
		}
	}
}

