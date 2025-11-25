package errors

import (
	"fmt"
)

// NewMethodNotFoundError creates a method not found error
func NewMethodNotFoundError(method string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeMethodNotFound,
		Message: "Method not found",
		Data:    map[string]interface{}{"method": method},
	}
}

// NewInvalidParamsError creates an invalid params error
func NewInvalidParamsError(message string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeInvalidParams,
		Message: "Invalid params",
		Data:    map[string]interface{}{"details": message},
	}
}

// NewInvalidNamespaceError creates an invalid namespace error
func NewInvalidNamespaceError(namespace string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeInvalidNamespace,
		Message: "Invalid namespace",
		Data:    map[string]interface{}{"namespace": namespace},
	}
}

// NewInvalidUpstreamURLError creates an invalid upstream URL error
func NewInvalidUpstreamURLError(url string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeInvalidUpstreamURL,
		Message: "Invalid upstream URL",
		Data:    map[string]interface{}{"url": url},
	}
}

// NewBatchSizeError creates a batch size error
func NewBatchSizeError(currentSize, maxSize int) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeBatchSizeError,
		Message: fmt.Sprintf("Batch size %d exceeds limit %d", currentSize, maxSize),
		Data: map[string]interface{}{
			"current_size": currentSize,
			"max_size":     maxSize,
		},
	}
}

// NewLimitsError creates a limits error
func NewLimitsError(reason string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeLimitsError,
		Message: "Request limit exceeded",
		Data:    map[string]interface{}{"reason": reason},
	}
}

// NewAccountHistoryLimitError creates an account history limit error
func NewAccountHistoryLimitError(requestedLimit, maxLimit int) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeAccountHistoryLimit,
		Message: fmt.Sprintf("Account history limit %d exceeds maximum %d", requestedLimit, maxLimit),
		Data: map[string]interface{}{
			"requested_limit": requestedLimit,
			"max_limit":       maxLimit,
		},
	}
}

// NewCustomJSONOpLengthError creates a custom JSON operation length error
func NewCustomJSONOpLengthError(length, maxLength int) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeCustomJSONOpLength,
		Message: fmt.Sprintf("Custom JSON operation length %d exceeds limit %d", length, maxLength),
		Data: map[string]interface{}{
			"length":    length,
			"max_length": maxLength,
		},
	}
}

// NewResponseTimeoutError creates a response timeout error
func NewResponseTimeoutError(message string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeResponseTimeout,
		Message: "Response timeout",
		Data:    map[string]interface{}{"details": message},
	}
}

// WithContext adds context information to an error
func (e *JSONRPCError) WithContext(key string, value interface{}) *JSONRPCError {
	if e.Data == nil {
		e.Data = make(map[string]interface{})
	}
	e.Data[key] = value
	return e
}

// WithRequestID adds request ID to error data
func (e *JSONRPCError) WithRequestID(requestID string) *JSONRPCError {
	return e.WithContext("request_id", requestID)
}

// WithMethod adds method name to error data
func (e *JSONRPCError) WithMethod(method string) *JSONRPCError {
	return e.WithContext("method", method)
}

// WithNamespace adds namespace to error data
func (e *JSONRPCError) WithNamespace(namespace string) *JSONRPCError {
	return e.WithContext("namespace", namespace)
}

