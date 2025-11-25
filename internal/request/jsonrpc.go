package request

import (
	"encoding/json"
	"fmt"

	"github.com/steemit/jussi/internal/urn"
)

// JSONRPCRequest represents a parsed JSON-RPC request
type JSONRPCRequest struct {
	ID            interface{} `json:"id"`
	JSONRPC       string      `json:"jsonrpc"`
	Method        string      `json:"method"`
	Params        interface{} `json:"params,omitempty"`
	URN           *urn.URN
	Upstream      *UpstreamConfig
	AmznTraceID   string
	JussiRequestID string
	BatchIndex    int
	OriginalRequest map[string]interface{}
}

// UpstreamConfig holds upstream routing configuration
type UpstreamConfig struct {
	URL     string
	TTL     int
	Timeout int
}

// ToUpstreamRequest converts the request to upstream format
func (r *JSONRPCRequest) ToUpstreamRequest() map[string]interface{} {
	req := map[string]interface{}{
		"jsonrpc": r.JSONRPC,
		"method":  r.Method,
		"id":      r.UpstreamID(),
	}

	if r.Params != nil {
		req["params"] = r.Params
	}

	return req
}

// UpstreamID returns the ID to use for upstream requests
func (r *JSONRPCRequest) UpstreamID() int {
	// Use batch index to ensure unique IDs
	return r.BatchIndex + 1000000 // Offset to avoid conflicts
}

// UpstreamHeaders returns headers to include in upstream requests
func (r *JSONRPCRequest) UpstreamHeaders() map[string]string {
	headers := map[string]string{
		"x-jussi-request-id": r.JussiRequestID,
	}
	if r.AmznTraceID != "" {
		headers["x-amzn-trace-id"] = r.AmznTraceID
	}
	return headers
}

// FromHTTPRequest creates a JSONRPCRequest from an HTTP request
func FromHTTPRequest(httpReq *HTTPRequest, batchIndex int, rawRequest map[string]interface{}) (*JSONRPCRequest, error) {
	// Parse URN
	urn, err := urn.FromRequest(rawRequest)
	if err != nil {
		return nil, fmt.Errorf("failed to parse URN: %w", err)
	}

	// Get upstream configuration (will be set by upstream router)
	upstream := &UpstreamConfig{
		URL:     "",
		TTL:     3,
		Timeout: 5,
	}

	id, _ := rawRequest["id"]
	jsonrpc, _ := rawRequest["jsonrpc"].(string)
	method, _ := rawRequest["method"].(string)
	params, _ := rawRequest["params"]

	return &JSONRPCRequest{
		ID:             id,
		JSONRPC:        jsonrpc,
		Method:         method,
		Params:         params,
		URN:            urn,
		Upstream:       upstream,
		AmznTraceID:    httpReq.AmznTraceID,
		JussiRequestID: httpReq.JussiRequestID,
		BatchIndex:     batchIndex,
		OriginalRequest: rawRequest,
	}, nil
}

// HTTPRequest represents an HTTP request wrapper
type HTTPRequest struct {
	AmznTraceID   string
	JussiRequestID string
	Body          []byte
}

// ParseJSONRPC parses the request body as JSON-RPC
func (r *HTTPRequest) ParseJSONRPC() (interface{}, error) {
	if len(r.Body) == 0 {
		return nil, fmt.Errorf("empty request body")
	}

	var request interface{}
	if err := json.Unmarshal(r.Body, &request); err != nil {
		return nil, fmt.Errorf("invalid JSON: %w", err)
	}

	return request, nil
}

