package validators

import (
	"testing"
)

func TestValidateJSONRPCRequest(t *testing.T) {
	tests := []struct {
		name     string
		request  map[string]interface{}
		hasError bool
	}{
		{
			name: "valid request",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  []interface{}{1000},
				"id":      1,
			},
			hasError: false,
		},
		{
			name: "missing jsonrpc",
			request: map[string]interface{}{
				"method": "get_block",
				"params": []interface{}{1000},
				"id":     1,
			},
			hasError: true,
		},
		{
			name: "wrong jsonrpc version",
			request: map[string]interface{}{
				"jsonrpc": "1.0",
				"method":  "get_block",
				"params":  []interface{}{1000},
				"id":      1,
			},
			hasError: true,
		},
		{
			name: "missing method",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"params":  []interface{}{1000},
				"id":      1,
			},
			hasError: true,
		},
		{
			name: "invalid method type",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  123,
				"params":  []interface{}{1000},
				"id":      1,
			},
			hasError: true,
		},
		{
			name: "missing id",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  []interface{}{1000},
			},
			hasError: false, // ID is optional in some cases
		},
		{
			name: "valid request without params",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_dynamic_global_properties",
				"id":      1,
			},
			hasError: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateJSONRPCRequest(tt.request)
			
			if tt.hasError && err == nil {
				t.Errorf("expected error but got none")
			}
			
			if !tt.hasError && err != nil {
				t.Errorf("unexpected error: %v", err)
			}
		})
	}
}

func TestValidateJSONRPCRequestBatch(t *testing.T) {
	tests := []struct {
		name     string
		request  []interface{}
		hasError bool
	}{
		{
			name: "valid batch request",
			request: []interface{}{
				map[string]interface{}{
					"jsonrpc": "2.0",
					"method":  "get_block",
					"params":  []interface{}{1000},
					"id":      1,
				},
				map[string]interface{}{
					"jsonrpc": "2.0",
					"method":  "call",
					"params":  []interface{}{"database_api", "get_block", []interface{}{1000}},
					"id":      2,
				},
			},
			hasError: false,
		},
		{
			name:     "empty batch request",
			request:  []interface{}{},
			hasError: true,
		},
		{
			name: "batch request with invalid item",
			request: []interface{}{
				map[string]interface{}{
					"jsonrpc": "2.0",
					"method":  "get_block",
					"params":  []interface{}{1000},
					"id":      1,
				},
				map[string]interface{}{
					"jsonrpc": "1.0", // Invalid version
					"method":  "get_block",
					"params":  []interface{}{1000},
					"id":      2,
				},
			},
			hasError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateJSONRPCRequest(tt.request)

			if tt.hasError && err == nil {
				t.Errorf("expected error but got none")
			}

			if !tt.hasError && err != nil {
				t.Errorf("unexpected error: %v", err)
			}
		})
	}
}

func TestValidateJSONRPCResponse(t *testing.T) {
	tests := []struct {
		name     string
		response map[string]interface{}
		hasError bool
	}{
		{
			name: "valid response with result",
			response: map[string]interface{}{
				"jsonrpc": "2.0",
				"result":  map[string]interface{}{"block_id": "000003e8"},
				"id":      1,
			},
			hasError: false,
		},
		{
			name: "valid response with error",
			response: map[string]interface{}{
				"jsonrpc": "2.0",
				"error": map[string]interface{}{
					"code":    -32600,
					"message": "Invalid Request",
				},
				"id": 1,
			},
			hasError: false,
		},
		{
			name: "response with both result and error",
			response: map[string]interface{}{
				"jsonrpc": "2.0",
				"result":  map[string]interface{}{"block_id": "000003e8"},
				"error": map[string]interface{}{
					"code":    -32600,
					"message": "Invalid Request",
				},
				"id": 1,
			},
			hasError: true,
		},
		{
			name: "response with neither result nor error",
			response: map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      1,
			},
			hasError: true,
		},
		{
			name: "response with wrong jsonrpc version",
			response: map[string]interface{}{
				"jsonrpc": "1.0",
				"result":  map[string]interface{}{"block_id": "000003e8"},
				"id":      1,
			},
			hasError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateJSONRPCResponse(tt.response)

			if tt.hasError && err == nil {
				t.Errorf("expected error but got none")
			}

			if !tt.hasError && err != nil {
				t.Errorf("unexpected error: %v", err)
			}
		})
	}
}

func TestIsValidNonErrorResponse(t *testing.T) {
	tests := []struct {
		name     string
		response map[string]interface{}
		expected bool
	}{
		{
			name: "valid non-error response",
			response: map[string]interface{}{
				"jsonrpc": "2.0",
				"result":  map[string]interface{}{"block_id": "000003e8"},
				"id":      1,
			},
			expected: true,
		},
		{
			name: "error response",
			response: map[string]interface{}{
				"jsonrpc": "2.0",
				"error": map[string]interface{}{
					"code":    -32600,
					"message": "Invalid Request",
				},
				"id": 1,
			},
			expected: false,
		},
		{
			name: "invalid response - no result or error",
			response: map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      1,
			},
			expected: false,
		},
		{
			name: "invalid response - both result and error",
			response: map[string]interface{}{
				"jsonrpc": "2.0",
				"result":  map[string]interface{}{"block_id": "000003e8"},
				"error": map[string]interface{}{
					"code":    -32600,
					"message": "Invalid Request",
				},
				"id": 1,
			},
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsValidNonErrorResponse(tt.response)
			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
		})
	}
}

func TestValidateJSONRPCRequestInvalidKeys(t *testing.T) {
	tests := []struct {
		name     string
		request  map[string]interface{}
		hasError bool
	}{
		{
			name: "request with extra invalid key",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  []interface{}{1000},
				"id":      1,
				"extra":   "invalid", // Invalid key
			},
			hasError: true,
		},
		{
			name: "request with valid keys only",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  []interface{}{1000},
				"id":      1,
			},
			hasError: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateJSONRPCRequest(tt.request)

			if tt.hasError && err == nil {
				t.Errorf("expected error but got none")
			}

			if !tt.hasError && err != nil {
				t.Errorf("unexpected error: %v", err)
			}
		})
	}
}

func TestValidateJSONRPCRequestIDTypes(t *testing.T) {
	tests := []struct {
		name     string
		request  map[string]interface{}
		hasError bool
	}{
		{
			name: "valid string ID",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  []interface{}{1000},
				"id":      "123",
			},
			hasError: false,
		},
		{
			name: "valid integer ID",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  []interface{}{1000},
				"id":      123,
			},
			hasError: false,
		},
		{
			name: "valid float ID",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  []interface{}{1000},
				"id":      123.45,
			},
			hasError: false,
		},
		{
			name: "valid null ID",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  []interface{}{1000},
				"id":      nil,
			},
			hasError: false,
		},
		{
			name: "invalid ID type - object",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  []interface{}{1000},
				"id":      map[string]interface{}{"key": "value"},
			},
			hasError: true,
		},
		{
			name: "invalid ID type - array",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  []interface{}{1000},
				"id":      []interface{}{1, 2, 3},
			},
			hasError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateJSONRPCRequest(tt.request)

			if tt.hasError && err == nil {
				t.Errorf("expected error but got none")
			}

			if !tt.hasError && err != nil {
				t.Errorf("unexpected error: %v", err)
			}
		})
	}
}

func TestValidateJSONRPCRequestParamsTypes(t *testing.T) {
	tests := []struct {
		name     string
		request  map[string]interface{}
		hasError bool
	}{
		{
			name: "valid array params",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  []interface{}{1000},
				"id":      1,
			},
			hasError: false,
		},
		{
			name: "valid object params",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  map[string]interface{}{"block_num": 1000},
				"id":      1,
			},
			hasError: false,
		},
		{
			name: "valid null params",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  nil,
				"id":      1,
			},
			hasError: false,
		},
		{
			name: "invalid params type - string",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  "invalid",
				"id":      1,
			},
			hasError: true,
		},
		{
			name: "invalid params type - number",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "get_block",
				"params":  123,
				"id":      1,
			},
			hasError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateJSONRPCRequest(tt.request)

			if tt.hasError && err == nil {
				t.Errorf("expected error but got none")
			}

			if !tt.hasError && err != nil {
				t.Errorf("unexpected error: %v", err)
			}
		})
	}
}
