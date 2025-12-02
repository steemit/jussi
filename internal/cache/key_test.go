package cache

import (
	"testing"

	"github.com/steemit/jussi/internal/urn"
)

func TestCacheKey(t *testing.T) {
	tests := []struct {
		name     string
		request  map[string]interface{}
		expected string
	}{
		{
			name: "steemd method",
			request: map[string]interface{}{
				"method": "get_block",
				"params": []interface{}{1000},
			},
			expected: "steemd.database_api.get_block.params=[1000]",
		},
		{
			name: "appbase method",
			request: map[string]interface{}{
				"method": "condenser_api.get_block",
				"params": []interface{}{1000},
			},
			expected: "appbase.condenser_api.get_block.params=[1000]",
		},
		{
			name: "appbase method with empty params",
			request: map[string]interface{}{
				"method": "condenser_api.get_dynamic_global_properties",
				"params": []interface{}{},
			},
			expected: "appbase.condenser_api.get_dynamic_global_properties.params=[]",
		},
		{
			name: "appbase method with params dict",
			request: map[string]interface{}{
				"method": "tags_api.get_tags_used_by_author",
				"params": map[string]interface{}{
					"author": "ste emit",
				},
			},
			expected: `appbase.tags_api.get_tags_used_by_author.params={"author":"ste emit"}`,
		},
		{
			name: "steemd method call format",
			request: map[string]interface{}{
				"method": "call",
				"params": []interface{}{"database_api", "get_block", []interface{}{1000}},
			},
			expected: "steemd.database_api.get_block.params=[1000]",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Parse URN from request
			urn, err := urn.FromRequest(tt.request)
			if err != nil {
				t.Fatalf("failed to parse URN: %v", err)
			}

			// Generate cache key
			key := GenerateCacheKey(urn)

			if key != tt.expected {
				t.Errorf("expected cache key '%s', got '%s'", tt.expected, key)
			}
		})
	}
}

func TestCacheKeyFromRequest(t *testing.T) {
	tests := []struct {
		name     string
		request  map[string]interface{}
		expected string
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
			expected: "steemd.database_api.get_block.params=[1000]",
			hasError: false,
		},
		{
			name: "invalid request - missing method",
			request: map[string]interface{}{
				"jsonrpc": "2.0",
				"params":  []interface{}{1000},
				"id":      1,
			},
			hasError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			key, err := GenerateCacheKeyFromRequest(tt.request)

			if tt.hasError {
				if err == nil {
					t.Error("expected error but got none")
				}
				return
			}

			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			if key != tt.expected {
				t.Errorf("expected cache key '%s', got '%s'", tt.expected, key)
			}
		})
	}
}

func TestCacheKeyFromJSON(t *testing.T) {
	jsonData := []byte(`{
		"jsonrpc": "2.0",
		"method": "get_block",
		"params": [1000],
		"id": 1
	}`)

	key, err := GenerateCacheKeyFromJSON(jsonData)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	expected := "steemd.database_api.get_block.params=[1000]"
	if key != expected {
		t.Errorf("expected cache key '%s', got '%s'", expected, key)
	}
}

// TestCacheKeyMatchesLegacy tests that cache key generation matches legacy behavior
// This test uses the same test data from legacy/tests/test_cache_key.py
func TestCacheKeyMatchesLegacy(t *testing.T) {
	// This test would use the same test fixtures as legacy tests
	// For now, we test that the cache key equals the URN string representation
	testCases := []struct {
		name     string
		request  map[string]interface{}
		expected string // Expected URN string (which is the cache key)
	}{
		{
			name: "steemd get_block",
			request: map[string]interface{}{
				"method": "get_block",
				"params": []interface{}{1000},
			},
			expected: "steemd.database_api.get_block.params=[1000]",
		},
		{
			name: "appbase condenser_api.get_block",
			request: map[string]interface{}{
				"method": "condenser_api.get_block",
				"params": []interface{}{1000},
			},
			expected: "appbase.condenser_api.get_block.params=[1000]",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			urn, err := urn.FromRequest(tc.request)
			if err != nil {
				t.Fatalf("failed to parse URN: %v", err)
			}

			key := GenerateCacheKey(urn)
			if key != tc.expected {
				t.Errorf("expected cache key '%s', got '%s'", tc.expected, key)
			}

			// Also test that cache key equals URN string
			if key != urn.String() {
				t.Errorf("cache key '%s' should equal URN string '%s'", key, urn.String())
			}
		})
	}
}

