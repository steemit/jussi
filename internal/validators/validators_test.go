package validators

import (
	"testing"

	"github.com/steemit/jussi/internal/errors"
	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/urn"
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

// Helper function to create a JSONRPCRequest for testing
func createTestRequest(method string, params interface{}) *request.JSONRPCRequest {
	urn, _ := urn.FromRequest(map[string]interface{}{
		"method": method,
		"params": params,
	})
	return &request.JSONRPCRequest{
		URN:    urn,
		Method: method,
		Params: params,
	}
}

func TestIsGetBlockRequest(t *testing.T) {
	tests := []struct {
		name     string
		request  *request.JSONRPCRequest
		expected bool
	}{
		{
			name:     "steemd get_block",
			request:  createTestRequest("get_block", []interface{}{1000}),
			expected: true,
		},
		{
			name:     "appbase condenser_api.get_block",
			request:  createTestRequest("condenser_api.get_block", []interface{}{1000}),
			expected: true,
		},
		{
			name:     "non-get_block method",
			request:  createTestRequest("get_accounts", []interface{}{[]string{"steemit"}}),
			expected: false,
		},
		{
			name:     "nil request",
			request:  nil,
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsGetBlockRequest(tt.request)
			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
		})
	}
}

func TestIsGetBlockHeaderRequest(t *testing.T) {
	tests := []struct {
		name     string
		request  *request.JSONRPCRequest
		expected bool
	}{
		{
			name:     "steemd get_block_header",
			request:  createTestRequest("get_block_header", []interface{}{1000}),
			expected: true,
		},
		{
			name:     "appbase get_block_header",
			request:  createTestRequest("database_api.get_block_header", []interface{}{1000}),
			expected: true,
		},
		{
			name:     "non-get_block_header method",
			request:  createTestRequest("get_block", []interface{}{1000}),
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsGetBlockHeaderRequest(tt.request)
			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
		})
	}
}

func TestIsBroadcastTransactionRequest(t *testing.T) {
	tests := []struct {
		name     string
		request  *request.JSONRPCRequest
		expected bool
	}{
		{
			name: "broadcast_transaction_synchronous via call",
			request: createTestRequest("call", []interface{}{
				"condenser_api",
				"broadcast_transaction_synchronous",
				[]interface{}{},
			}),
			expected: true,
		},
		{
			name:     "network_broadcast_api.broadcast_transaction_synchronous",
			request:  createTestRequest("network_broadcast_api.broadcast_transaction_synchronous", map[string]interface{}{}),
			expected: true,
		},
		{
			name:     "non-broadcast method",
			request:  createTestRequest("get_block", []interface{}{1000}),
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsBroadcastTransactionRequest(tt.request)
			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
		})
	}
}

func TestBlockNumFromID(t *testing.T) {
	tests := []struct {
		name      string
		blockID   string
		expected  int
		hasError  bool
	}{
		{
			name:     "valid block ID",
			blockID:  "000003e8b922f4906a45af8e99d86b3511acd7a5",
			expected: 1000, // 0x000003e8 = 1000
			hasError: false,
		},
		{
			name:     "short block ID",
			blockID:  "000003e8",
			expected: 1000,
			hasError: false,
		},
		{
			name:     "invalid block ID - too short",
			blockID:  "000003",
			expected: 0,
			hasError: true,
		},
		{
			name:     "invalid block ID - non-hex",
			blockID:  "ggggggggb922f4906a45af8e99d86b3511acd7a5",
			expected: 0,
			hasError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := BlockNumFromID(tt.blockID)
			if tt.hasError {
				if err == nil {
					t.Errorf("expected error but got none")
				}
				return
			}

			if err != nil {
				t.Errorf("unexpected error: %v", err)
				return
			}

			if result != tt.expected {
				t.Errorf("expected %d, got %d", tt.expected, result)
			}
		})
	}
}

func TestIsValidGetBlockResponse(t *testing.T) {
	// Create a valid get_block request
	req := createTestRequest("get_block", []interface{}{1000})

	tests := []struct {
		name     string
		request  *request.JSONRPCRequest
		response map[string]interface{}
		expected bool
	}{
		{
			name:    "valid get_block response",
			request: req,
			response: map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      1,
				"result": map[string]interface{}{
					"block_id": "000003e8b922f4906a45af8e99d86b3511acd7a5", // Block 1000
					"previous": "000003e7c4fd3221cf407efcf7c1730e2ca54b05",
				},
			},
			expected: true,
		},
		{
			name:    "invalid - block number mismatch",
			request: req,
			response: map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      1,
				"result": map[string]interface{}{
					"block_id": "000003e9b922f4906a45af8e99d86b3511acd7a5", // Block 1001, not 1000
				},
			},
			expected: false,
		},
		{
			name:    "invalid - no block_id",
			request: req,
			response: map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      1,
				"result":  map[string]interface{}{},
			},
			expected: false,
		},
		{
			name:    "invalid - error response",
			request: req,
			response: map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      1,
				"error": map[string]interface{}{
					"code":    -32603,
					"message": "Internal error",
				},
			},
			expected: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsValidGetBlockResponse(tt.request, tt.response)
			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
		})
	}
}

func TestLimitCustomJSONOpLength(t *testing.T) {
	tests := []struct {
		name      string
		ops       []interface{}
		sizeLimit int
		hasError  bool
	}{
		{
			name: "valid custom_json op",
			ops: []interface{}{
				[]interface{}{
					"custom_json",
					map[string]interface{}{
						"json": `{"follower":"steemit","following":"steem","what":["posts"]}`,
					},
				},
			},
			sizeLimit: 8192,
			hasError: false,
		},
		{
			name: "invalid - exceeds size limit",
			ops: []interface{}{
				[]interface{}{
					"custom_json",
					map[string]interface{}{
						"json": string(make([]byte, 8193)), // 8193 bytes
					},
				},
			},
			sizeLimit: 8192,
			hasError:  true,
		},
		{
			name: "non-custom_json op - should pass",
			ops: []interface{}{
				[]interface{}{
					"transfer",
					map[string]interface{}{
						"from": "steemit",
					},
				},
			},
			sizeLimit: 100,
			hasError:  false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := LimitCustomJSONOpLength(tt.ops, tt.sizeLimit)
			if tt.hasError {
				if err == nil {
					t.Errorf("expected error but got none")
				} else if _, ok := err.(*errors.JSONRPCError); !ok {
					t.Errorf("expected JSONRPCError, got %T", err)
				}
			} else {
				if err != nil {
					t.Errorf("unexpected error: %v", err)
				}
			}
		})
	}
}

func TestLimitCustomJSONAccount(t *testing.T) {
	tests := []struct {
		name              string
		ops               []interface{}
		blacklistAccounts map[string]bool
		hasError          bool
	}{
		{
			name: "valid account",
			ops: []interface{}{
				[]interface{}{
					"custom_json",
					map[string]interface{}{
						"required_posting_auths": []interface{}{"steemit"},
					},
				},
			},
			blacklistAccounts: map[string]bool{"not_steemit": true},
			hasError:          false,
		},
		{
			name: "blacklisted account",
			ops: []interface{}{
				[]interface{}{
					"custom_json",
					map[string]interface{}{
						"required_posting_auths": []interface{}{"not_steemit"},
					},
				},
			},
			blacklistAccounts: map[string]bool{"not_steemit": true},
			hasError:          true,
		},
		{
			name: "empty blacklist",
			ops: []interface{}{
				[]interface{}{
					"custom_json",
					map[string]interface{}{
						"required_posting_auths": []interface{}{"steemit"},
					},
				},
			},
			blacklistAccounts: nil,
			hasError:          false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := LimitCustomJSONAccount(tt.ops, tt.blacklistAccounts)
			if tt.hasError {
				if err == nil {
					t.Errorf("expected error but got none")
				} else if _, ok := err.(*errors.JSONRPCError); !ok {
					t.Errorf("expected JSONRPCError, got %T", err)
				}
			} else {
				if err != nil {
					t.Errorf("unexpected error: %v", err)
				}
			}
		})
	}
}

func TestLimitBroadcastTransactionRequest(t *testing.T) {
	validOps := []interface{}{
		[]interface{}{
			"custom_json",
			map[string]interface{}{
				"required_auths": []interface{}{},
				"id":             "follow",
				"json":           `{"follower":"steemit","following":"steem","what":["posts"]}`,
				"required_posting_auths": []interface{}{"steemit"},
			},
		},
	}

	invalidOps := []interface{}{
		[]interface{}{
			"custom_json",
			map[string]interface{}{
				"required_auths": []interface{}{},
				"id":             "follow",
				"json":           string(make([]byte, 8193)), // Too large
				"required_posting_auths": []interface{}{"steemit"},
			},
		},
	}

	tests := []struct {
		name     string
		request  *request.JSONRPCRequest
		limits   map[string]interface{}
		hasError bool
	}{
		{
			name:    "valid broadcast transaction",
			request: createTestRequest("call", []interface{}{"condenser_api", "broadcast_transaction_synchronous", []interface{}{map[string]interface{}{"operations": validOps}}}),
			limits: map[string]interface{}{
				"custom_json_size_limit": 8192,
				"accounts_blacklist":    []interface{}{"not_steemit"},
			},
			hasError: false,
		},
		{
			name:    "invalid - custom_json too large",
			request: createTestRequest("call", []interface{}{"condenser_api", "broadcast_transaction_synchronous", []interface{}{map[string]interface{}{"operations": invalidOps}}}),
			limits: map[string]interface{}{
				"custom_json_size_limit": 8192,
			},
			hasError: true,
		},
		{
			name:    "non-broadcast request - should pass",
			request: createTestRequest("get_block", []interface{}{1000}),
			limits:  map[string]interface{}{},
			hasError: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := LimitBroadcastTransactionRequest(tt.request, tt.limits)
			if tt.hasError {
				if err == nil {
					t.Errorf("expected error but got none")
				}
			} else {
				if err != nil {
					t.Errorf("unexpected error: %v", err)
				}
			}
		})
	}
}
