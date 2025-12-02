package errors

import (
	"fmt"
	"net/http"

	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/otel/trace"
)

// JSONRPCError represents a JSON-RPC 2.0 error
type JSONRPCError struct {
	Code    int                    `json:"code"`
	Message string                 `json:"message"`
	Data    map[string]interface{} `json:"data,omitempty"`
}

// Error implements the error interface
func (e *JSONRPCError) Error() string {
	return fmt.Sprintf("JSON-RPC error %d: %s", e.Code, e.Message)
}

// ToResponse converts error to JSON-RPC error response
func (e *JSONRPCError) ToResponse(id interface{}) map[string]interface{} {
	return e.ToResponseWithRequestID(id, "", "")
}

// ToResponseWithRequestID converts error to JSON-RPC error response with jussi request ID and trace ID
func (e *JSONRPCError) ToResponseWithRequestID(id interface{}, jussiRequestID string, traceID string) map[string]interface{} {
	response := map[string]interface{}{
		"jsonrpc": "2.0",
		"id":      id,
		"error": map[string]interface{}{
			"code":    e.Code,
			"message": e.Message,
		},
	}

	// Build error data
	errorData := make(map[string]interface{})
	
	// Copy existing data
	if len(e.Data) > 0 {
		for k, v := range e.Data {
			errorData[k] = v
		}
	}
	
	// Add jussi_request_id if provided
	if jussiRequestID != "" {
		errorData["jussi_request_id"] = jussiRequestID
	}
	
	// Add trace_id if provided
	if traceID != "" {
		errorData["trace_id"] = traceID
	}
	
	// Only add data field if there's data to include
	if len(errorData) > 0 {
		response["error"].(map[string]interface{})["data"] = errorData
	}

	return response
}

// Standard JSON-RPC error codes
const (
	CodeParseError     = -32700
	CodeInvalidRequest = -32600
	CodeMethodNotFound = -32601
	CodeInvalidParams  = -32602
	CodeInternalError  = -32603
)

// Jussi-specific error codes
const (
	CodeRequestTimeout      = 1000
	CodeResponseTimeout     = 1050
	CodeUpstreamResponseErr = 1100
	CodeInvalidNamespace    = 1200
	CodeInvalidNamespaceAPI = 1300
	CodeInvalidUpstreamHost = 1400
	CodeInvalidUpstreamURL  = 1500
	CodeBatchSizeError      = 1600
	CodeLimitsError         = 1700
	CodeAccountHistoryLimit = 1701
	CodeCustomJSONOpLength  = 1800
)

// NewParseError creates a parse error
func NewParseError(message string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeParseError,
		Message: "Parse error",
		Data:    map[string]interface{}{"details": message},
	}
}

// NewInvalidRequest creates an invalid request error
func NewInvalidRequest(message string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeInvalidRequest,
		Message: "Invalid Request",
		Data:    map[string]interface{}{"details": message},
	}
}

// NewInternalError creates an internal error
func NewInternalError(message string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeInternalError,
		Message: "Internal error",
		Data:    map[string]interface{}{"details": message},
	}
}

// NewRequestTimeoutError creates a request timeout error
func NewRequestTimeoutError(message string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeRequestTimeout,
		Message: "Request Timeout",
		Data:    map[string]interface{}{"details": message},
	}
}

// NewUpstreamError creates an upstream error
func NewUpstreamError(message string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeUpstreamResponseErr,
		Message: "Upstream response error",
		Data:    map[string]interface{}{"details": message},
	}
}

// HandleError handles errors and returns appropriate JSON-RPC response
func HandleError(c *gin.Context, err error, requestID interface{}) {
	var jsonrpcErr *JSONRPCError

	switch e := err.(type) {
	case *JSONRPCError:
		jsonrpcErr = e
	default:
		jsonrpcErr = NewInternalError(err.Error())
	}

	// Get jussi_request_id from context if available
	jussiRequestID := ""
	if jussiID, exists := c.Get("jussi_request_id"); exists {
		if idStr, ok := jussiID.(string); ok {
			jussiRequestID = idStr
		}
	}

	// Get OpenTelemetry trace ID from context if available
	traceID := ""
	if span := trace.SpanFromContext(c.Request.Context()); span.SpanContext().IsValid() {
		traceID = span.SpanContext().TraceID().String()
	}

	c.JSON(http.StatusOK, jsonrpcErr.ToResponseWithRequestID(requestID, jussiRequestID, traceID))
}

