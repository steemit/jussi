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

// Note: These functions are not currently implemented in validators.go
// Commenting out tests for now

/*
func TestIsGetBlockRequest(t *testing.T) {
	// Implementation needed in validators.go
}

func TestIsGetDynamicGlobalPropertiesRequest(t *testing.T) {
	// Implementation needed in validators.go  
}

func TestBlockNumFromID(t *testing.T) {
	// Implementation needed in validators.go
}
*/
