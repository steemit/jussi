package handlers

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/errors"
	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/validators"
)

// JSONRPCHandler handles JSON-RPC requests
type JSONRPCHandler struct {
	// Will be populated with dependencies
}

// HandleJSONRPC handles POST / requests
func (h *JSONRPCHandler) HandleJSONRPC(c *gin.Context) {
	// Parse request body
	var body interface{}
	if err := c.ShouldBindJSON(&body); err != nil {
		errors.HandleError(c, errors.NewParseError(err.Error()), nil)
		return
	}

	// Validate request
	if err := validators.ValidateJSONRPCRequest(body); err != nil {
		errors.HandleError(c, errors.NewInvalidRequest(err.Error()), nil)
		return
	}

	// Handle single or batch request
	switch req := body.(type) {
	case map[string]interface{}:
		h.handleSingleRequest(c, req)
	case []interface{}:
		h.handleBatchRequest(c, req)
	default:
		errors.HandleError(c, errors.NewInvalidRequest("invalid request format"), nil)
	}
}

func (h *JSONRPCHandler) handleSingleRequest(c *gin.Context, req map[string]interface{}) {
	// Extract request ID
	requestID := req["id"]

	// Create HTTP request wrapper
	httpReq := &request.HTTPRequest{
		AmznTraceID:   c.GetHeader("x-amzn-trace-id"),
		JussiRequestID: c.GetHeader("x-jussi-request-id"),
	}

	// Parse JSON-RPC request
	jsonrpcReq, err := request.FromHTTPRequest(httpReq, 0, req)
	if err != nil {
		errors.HandleError(c, errors.NewInvalidRequest(err.Error()), requestID)
		return
	}

	// TODO: Process request (cache lookup, upstream call, etc.)
	_ = jsonrpcReq

	// For now, return a placeholder response
	c.JSON(http.StatusOK, map[string]interface{}{
		"jsonrpc": "2.0",
		"id":      requestID,
		"result":  nil,
	})
}

func (h *JSONRPCHandler) handleBatchRequest(c *gin.Context, reqs []interface{}) {
	// TODO: Handle batch requests
	results := make([]interface{}, len(reqs))
	for i, req := range reqs {
		reqMap, ok := req.(map[string]interface{})
		if !ok {
			results[i] = errors.NewInvalidRequest("invalid batch item").ToResponse(nil)
			continue
		}
		// Process each request
		_ = reqMap
		results[i] = map[string]interface{}{
			"jsonrpc": "2.0",
			"id":      reqMap["id"],
			"result":  nil,
		}
	}

	c.JSON(http.StatusOK, results)
}

