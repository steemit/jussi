package cache

import (
	"testing"
	"time"
)

func TestCalculateTTL(t *testing.T) {
	tests := []struct {
		name                    string
		configTTL              int
		expectedTTL            time.Duration
	}{
		{
			name:                   "TTL no cache",
			configTTL:             TTLNoCache,
			expectedTTL:           0,
		},
		{
			name:                   "TTL no expire",
			configTTL:             TTLNoExpire,
			expectedTTL:           0,
		},
		{
			name:                   "TTL expire if irreversible",
			configTTL:             TTLExpireIfIrreversible,
			expectedTTL:           0 * time.Second,
		},
		{
			name:                   "Fixed TTL",
			configTTL:             300,
			expectedTTL:           300 * time.Second,
		},
		{
			name:                   "Default TTL",
			configTTL:             TTLDefault,
			expectedTTL:           3 * time.Second,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ttl := CalculateTTL(tt.configTTL, false, 0)
			
			if ttl != tt.expectedTTL {
				t.Errorf("expected TTL %v, got %v", tt.expectedTTL, ttl)
			}
		})
	}
}

func TestIsCacheable(t *testing.T) {
	tests := []struct {
		name      string
		ttl       int
		expected  bool
	}{
		{
			name:     "no cache",
			ttl:      TTLNoCache,
			expected: false,
		},
		{
			name:     "no expire",
			ttl:      TTLNoExpire,
			expected: true,
		},
		{
			name:     "expire if irreversible",
			ttl:      TTLExpireIfIrreversible,
			expected: true,
		},
		{
			name:     "fixed TTL",
			ttl:      300,
			expected: true,
		},
		{
			name:     "default TTL",
			ttl:      TTLDefault,
			expected: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsCacheable(tt.ttl)
			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
		})
	}
}

func TestShouldExpire(t *testing.T) {
	tests := []struct {
		name     string
		ttl      int
		expected bool
	}{
		{
			name:     "no expire",
			ttl:      TTLNoExpire,
			expected: false,
		},
		{
			name:     "expire if irreversible",
			ttl:      TTLExpireIfIrreversible,
			expected: true,
		},
		{
			name:     "fixed TTL",
			ttl:      300,
			expected: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := ShouldExpire(tt.ttl)
			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
		})
	}
}

func TestIrreversibleTTL(t *testing.T) {
	validResponse := map[string]interface{}{
		"id": 1,
		"result": map[string]interface{}{
			"block_id": "000003e8b922f4906a45af8e99d86b3511acd7a5", // Block 1000
			"previous": "000003e7c4fd3221cf407efcf7c1730e2ca54b05",
		},
	}

	tests := []struct {
		name                      string
		response                  map[string]interface{}
		lastIrreversibleBlockNum  int
		expected                  int
	}{
		{
			name:                     "block not irreversible - last_block < response_block",
			response:                 validResponse,
			lastIrreversibleBlockNum: 1,
			expected:                 TTLNoCache,
		},
		{
			name:                     "block not irreversible - last_block < response_block",
			response:                 validResponse,
			lastIrreversibleBlockNum: 999,
			expected:                 TTLNoCache,
		},
		{
			name:                     "block irreversible - last_block >= response_block",
			response:                 validResponse,
			lastIrreversibleBlockNum: 1000,
			expected:                 TTLDefault,
		},
		{
			name:                     "block irreversible - last_block > response_block",
			response:                 validResponse,
			lastIrreversibleBlockNum: 1001,
			expected:                 TTLDefault,
		},
		{
			name:                     "invalid response - empty",
			response:                 map[string]interface{}{},
			lastIrreversibleBlockNum: 2000,
			expected:                 TTLNoCache,
		},
		{
			name:                     "invalid response - nil",
			response:                 nil,
			lastIrreversibleBlockNum: 2000,
			expected:                 TTLNoCache,
		},
		{
			name:                     "invalid last_block_num - zero",
			response:                 validResponse,
			lastIrreversibleBlockNum: 0,
			expected:                 TTLNoCache,
		},
		{
			name:                     "invalid last_block_num - negative",
			response:                 validResponse,
			lastIrreversibleBlockNum: -1,
			expected:                 TTLNoCache,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IrreversibleTTL(tt.response, tt.lastIrreversibleBlockNum)
			if result != tt.expected {
				t.Errorf("expected TTL %d, got %d", tt.expected, result)
			}
		})
	}
}

func TestBlockNumFromJSONRPCResponse(t *testing.T) {
	tests := []struct {
		name      string
		response  map[string]interface{}
		expected  int
		hasError  bool
	}{
		{
			name: "steemd get_block response",
			response: map[string]interface{}{
				"result": map[string]interface{}{
					"block_id": "000003e8b922f4906a45af8e99d86b3511acd7a5", // Block 1000
				},
			},
			expected: 1000,
			hasError: false,
		},
		{
			name: "appbase get_block response with nested block",
			response: map[string]interface{}{
				"result": map[string]interface{}{
					"block": map[string]interface{}{
						"block_id": "000003e8b922f4906a45af8e99d86b3511acd7a5",
					},
				},
			},
			expected: 1000,
			hasError: false,
		},
		{
			name: "response with block_num field",
			response: map[string]interface{}{
				"result": map[string]interface{}{
					"block_num": 1000,
				},
			},
			expected: 1000,
			hasError: false,
		},
		{
			name: "invalid response - no result",
			response: map[string]interface{}{
				"error": map[string]interface{}{
					"code": -32603,
				},
			},
			hasError: true,
		},
		{
			name:     "invalid response - empty",
			response: map[string]interface{}{},
			hasError: true,
		},
		{
			name: "invalid response - no block_id or block_num",
			response: map[string]interface{}{
				"result": map[string]interface{}{
					"previous": "000003e7c4fd3221cf407efcf7c1730e2ca54b05",
				},
			},
			hasError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := BlockNumFromJSONRPCResponse(tt.response)
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
				t.Errorf("expected block number %d, got %d", tt.expected, result)
			}
		})
	}
}

func TestIsBlockIrreversible(t *testing.T) {
	tests := []struct {
		name                      string
		responseBlockNum          int
		lastIrreversibleBlockNum  int
		expected                  bool
	}{
		{
			name:                     "block is irreversible",
			responseBlockNum:         1000,
			lastIrreversibleBlockNum: 1000,
			expected:                 true,
		},
		{
			name:                     "block is irreversible - last > response",
			responseBlockNum:         1000,
			lastIrreversibleBlockNum: 1001,
			expected:                 true,
		},
		{
			name:                     "block is not irreversible",
			responseBlockNum:         1000,
			lastIrreversibleBlockNum: 999,
			expected:                 false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsBlockIrreversible(tt.responseBlockNum, tt.lastIrreversibleBlockNum)
			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
		})
	}
}
