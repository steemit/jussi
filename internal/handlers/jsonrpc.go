package handlers

import (
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

	// Parse all requests
	jsonrpcReqs := make([]*request.JSONRPCRequest, 0, len(reqs))
	httpReq := &request.HTTPRequest{
		JussiRequestID: getString(jussiRequestID),
	}

	for i, req := range reqs {
		reqMap, ok := req.(map[string]interface{})
		if !ok {
			continue
		}
		jsonrpcReq, err := request.FromHTTPRequest(httpReq, i, reqMap)
		if err != nil {
			continue
		}
		jsonrpcReqs = append(jsonrpcReqs, jsonrpcReq)
	}

	// Initialize processor if not already done
	if h.processor == nil {
		h.processor = NewRequestProcessor(h.CacheGroup, h.Router, h.HTTPClient, h.WSPools)
	}

	// Process batch
	ctx := c.Request.Context()
	responses, err := h.processor.ProcessBatchRequest(ctx, jsonrpcReqs)
	if err != nil {
		errors.HandleError(c, errors.NewInternalError(err.Error()), nil)
		return
	}

	// Convert to interface slice
	results := make([]interface{}, len(responses))
	for i, resp := range responses {
		results[i] = resp
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

