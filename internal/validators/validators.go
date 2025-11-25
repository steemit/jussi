package validators

import (
	"fmt"
	"reflect"
)

// JSONRPCRequestKeys are the valid keys in a JSON-RPC request
var JSONRPCRequestKeys = map[string]bool{
	"id":      true,
	"jsonrpc": true,
	"method":  true,
	"params":  true,
}

// JSONRPCResponseKeys are the valid keys in a JSON-RPC response
var JSONRPCResponseKeys = map[string]bool{
	"id":      true,
	"jsonrpc": true,
	"result":  true,
	"error":   true,
}

// IDTypes are valid types for JSON-RPC ID field
var IDTypes = []reflect.Kind{
	reflect.String,
	reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64,
	reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64,
	reflect.Float32, reflect.Float64,
}

// ParamsTypes are valid types for JSON-RPC params field
var ParamsTypes = []reflect.Kind{
	reflect.Slice,
	reflect.Map,
	reflect.Invalid, // nil
}

// ValidateJSONRPCRequest validates a JSON-RPC 2.0 request
func ValidateJSONRPCRequest(request interface{}) error {
	switch req := request.(type) {
	case map[string]interface{}:
		return validateSingleRequest(req)
	case []interface{}:
		if len(req) == 0 {
			return fmt.Errorf("batch request cannot be empty")
		}
		for i, r := range req {
			if err := validateSingleRequest(r.(map[string]interface{})); err != nil {
				return fmt.Errorf("batch request[%d]: %w", i, err)
			}
		}
		return nil
	default:
		return fmt.Errorf("request must be an object or array")
	}
}

func validateSingleRequest(req map[string]interface{}) error {
	// Check required fields
	jsonrpc, ok := req["jsonrpc"].(string)
	if !ok || jsonrpc != "2.0" {
		return fmt.Errorf("jsonrpc must be '2.0'")
	}

	method, ok := req["method"].(string)
	if !ok {
		return fmt.Errorf("method must be a string")
	}
	if method == "" {
		return fmt.Errorf("method cannot be empty")
	}

	// Check id (optional but must be valid type if present)
	if id, ok := req["id"]; ok && id != nil {
		if !isValidIDType(id) {
			return fmt.Errorf("id must be string, number, or null")
		}
	}

	// Check params (optional but must be valid type if present)
	if params, ok := req["params"]; ok && params != nil {
		if !isValidParamsType(params) {
			return fmt.Errorf("params must be array, object, or null")
		}
	}

	// Check for invalid keys
	for key := range req {
		if !JSONRPCRequestKeys[key] {
			return fmt.Errorf("invalid key: %s", key)
		}
	}

	return nil
}

// ValidateJSONRPCResponse validates a JSON-RPC 2.0 response
func ValidateJSONRPCResponse(response map[string]interface{}) error {
	// Must have either result or error, but not both
	hasResult := false
	hasError := false

	if _, ok := response["result"]; ok {
		hasResult = true
	}
	if _, ok := response["error"]; ok {
		hasError = true
	}

	if !hasResult && !hasError {
		return fmt.Errorf("response must have either 'result' or 'error'")
	}

	if hasResult && hasError {
		return fmt.Errorf("response cannot have both 'result' and 'error'")
	}

	// Check jsonrpc version
	if jsonrpc, ok := response["jsonrpc"].(string); ok {
		if jsonrpc != "2.0" {
			return fmt.Errorf("jsonrpc must be '2.0'")
		}
	}

	return nil
}

// IsValidNonErrorResponse checks if response is valid and non-error
func IsValidNonErrorResponse(response map[string]interface{}) bool {
	if err := ValidateJSONRPCResponse(response); err != nil {
		return false
	}

	// Must have result (not error)
	_, hasResult := response["result"]
	_, hasError := response["error"]

	return hasResult && !hasError
}

func isValidIDType(v interface{}) bool {
	kind := reflect.TypeOf(v).Kind()
	for _, validKind := range IDTypes {
		if kind == validKind {
			return true
		}
	}
	return false
}

func isValidParamsType(v interface{}) bool {
	if v == nil {
		return true
	}
	kind := reflect.TypeOf(v).Kind()
	for _, validKind := range ParamsTypes {
		if kind == validKind {
			return true
		}
	}
	return false
}

