package handlers

import (
	"fmt"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
	"github.com/steemit/jussi/internal/errors"
	"github.com/steemit/jussi/internal/logging"
	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/upstream"
	"github.com/steemit/jussi/internal/validators"
	"github.com/steemit/jussi/internal/ws"
)

// JSONRPCHandler handles JSON-RPC requests
type JSONRPCHandler struct {
	CacheGroup *cache.CacheGroup
	Router     *upstream.Router
	HTTPClient *upstream.HTTPClient
	WSPools    map[string]*ws.Pool
	Logger     *logging.Logger
	processor  *RequestProcessor
}

// HandleJSONRPC handles POST / requests
func (h *JSONRPCHandler) HandleJSONRPC(c *gin.Context) {
	// Try to get parsed body from middleware first
	var body interface{}
	if parsedBody, exists := c.Get("parsed_body"); exists {
		body = parsedBody
	} else {
		// Parse request body if not already parsed
		if err := c.ShouldBindJSON(&body); err != nil {
			errors.HandleError(c, errors.NewParseError(err.Error()), nil)
			return
		}
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

	// Get request ID from context
	jussiRequestID, _ := c.Get("jussi_request_id")

	// Create HTTP request wrapper
	httpReq := &request.HTTPRequest{
		JussiRequestID: getString(jussiRequestID),
	}

	// Parse JSON-RPC request
	jsonrpcReq, err := request.FromHTTPRequest(httpReq, 0, req)
	if err != nil {
		errors.HandleError(c, errors.NewInvalidRequest(err.Error()), requestID)
		return
	}

	// Initialize processor if not already done
	if h.processor == nil {
		h.processor = NewRequestProcessor(h.CacheGroup, h.Router, h.HTTPClient, h.WSPools)
	}

	// Process request
	ctx := c.Request.Context()
	response, err := h.processor.ProcessSingleRequest(ctx, jsonrpcReq)
	if err != nil {
		// Check if it's a namespace/upstream configuration error
		if strings.Contains(err.Error(), "no upstream configuration found") {
			// Use NewInvalidNamespaceError which already exists
			namespace := jsonrpcReq.URN.Namespace
			errors.HandleError(c, errors.NewInvalidNamespaceError(namespace), requestID)
		} else {
			errors.HandleError(c, errors.NewInternalError(err.Error()), requestID)
		}
		return
	}

	c.JSON(http.StatusOK, response)
}

func (h *JSONRPCHandler) handleBatchRequest(c *gin.Context, reqs []interface{}) {
	// Get request ID from context
	jussiRequestID, _ := c.Get("jussi_request_id")

	// Parse all requests, preserving original positions so that
	// response[i] always corresponds to reqs[i].
	httpReq := &request.HTTPRequest{
		JussiRequestID: getString(jussiRequestID),
	}

	type parsedItem struct {
		req *request.JSONRPCRequest
		err error
	}
	parsed := make([]parsedItem, len(reqs))

	for i, req := range reqs {
		reqMap, ok := req.(map[string]interface{})
		if !ok {
			parsed[i] = parsedItem{err: fmt.Errorf("invalid request format")}
			continue
		}
		jsonrpcReq, err := request.FromHTTPRequest(httpReq, i, reqMap)
		if err != nil {
			parsed[i] = parsedItem{err: err}
			continue
		}
		parsed[i] = parsedItem{req: jsonrpcReq}
	}

	// Collect valid requests for batch processing
	validReqs := make([]*request.JSONRPCRequest, 0, len(reqs))
	validIndices := make([]int, 0, len(reqs))
	for i, p := range parsed {
		if p.req != nil {
			validReqs = append(validReqs, p.req)
			validIndices = append(validIndices, i)
		}
	}

	// Build final results array (same length as input reqs)
	results := make([]interface{}, len(reqs))

	// Fill error responses for invalid requests
	for i, p := range parsed {
		if p.err != nil {
			// Try to extract id from the raw request for the error response
			var reqID interface{} = nil
			if reqMap, ok := reqs[i].(map[string]interface{}); ok {
				if id, exists := reqMap["id"]; exists {
					reqID = id
				}
			}
			results[i] = map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      reqID,
				"error": map[string]interface{}{
					"code":    -32600,
					"message": p.err.Error(),
				},
			}
		}
	}

	// Process valid batch requests
	if len(validReqs) > 0 {
		// Initialize processor if not already done
		if h.processor == nil {
			h.processor = NewRequestProcessor(h.CacheGroup, h.Router, h.HTTPClient, h.WSPools)
		}

		ctx := c.Request.Context()
		responses, err := h.processor.ProcessBatchRequest(ctx, validReqs)
		if err != nil {
			errors.HandleError(c, errors.NewInternalError(err.Error()), nil)
			return
		}

		// Place responses at their original positions
		for batchIdx, origIdx := range validIndices {
			results[origIdx] = responses[batchIdx]
		}
	}

	c.JSON(http.StatusOK, results)
}

// getString safely converts interface{} to string
func getString(v interface{}) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

