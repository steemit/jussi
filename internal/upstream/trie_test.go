package upstream

import (
	"reflect"
	"testing"
)

func TestTrieInsertAndLongestPrefix(t *testing.T) {
	trie := NewTrie()
	
	// Test data
	testData := []struct {
		key   string
		value interface{}
	}{
		{"steemd", "steemd_config"},
		{"steemd.get_block", "get_block_config"},
		{"appbase", "appbase_config"},
		{"appbase.condenser_api", "condenser_api_config"},
		{"appbase.condenser_api.get_block", "condenser_get_block_config"},
		{"appbase.database_api", "database_api_config"},
	}
	
	// Insert test data
	for _, data := range testData {
		trie.Insert(data.key, data.value)
	}
	
	// Test cases
	tests := []struct {
		name     string
		key      string
		expected interface{}
		found    bool
	}{
		{
			name:     "exact match - steemd",
			key:      "steemd",
			expected: "steemd_config",
			found:    true,
		},
		{
			name:     "exact match - get_block",
			key:      "steemd.get_block",
			expected: "get_block_config",
			found:    true,
		},
		{
			name:     "longest prefix - steemd method",
			key:      "steemd.get_dynamic_global_properties",
			expected: "steemd_config",
			found:    true,
		},
		{
			name:     "longest prefix - condenser api method",
			key:      "appbase.condenser_api.get_dynamic_global_properties",
			expected: "condenser_api_config",
			found:    true,
		},
		{
			name:     "exact match - condenser get_block",
			key:      "appbase.condenser_api.get_block",
			expected: "condenser_get_block_config",
			found:    true,
		},
		{
			name:     "longest prefix - database api method",
			key:      "appbase.database_api.get_block",
			expected: "database_api_config",
			found:    true,
		},
		{
			name:     "no match",
			key:      "unknown.method",
			expected: nil,
			found:    false,
		},
		{
			name:     "empty key",
			key:      "",
			expected: nil,
			found:    false,
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			key, value, found := trie.LongestPrefix(tt.key)
			_ = key // ignore returned key for now
			
			if found != tt.found {
				t.Errorf("expected found %v, got %v", tt.found, found)
			}
			
			if !reflect.DeepEqual(value, tt.expected) {
				t.Errorf("expected value %v, got %v", tt.expected, value)
			}
		})
	}
}

func TestTrieSplitAndJoinKey(t *testing.T) {
	// Test helper functions directly
	
	tests := []struct {
		name     string
		key      string
		expected []string
	}{
		{
			name:     "simple key",
			key:      "steemd",
			expected: []string{"steemd"},
		},
		{
			name:     "compound key",
			key:      "steemd.get_block",
			expected: []string{"steemd", "get_block"},
		},
		{
			name:     "nested key",
			key:      "appbase.condenser_api.get_block",
			expected: []string{"appbase", "condenser_api", "get_block"},
		},
		{
			name:     "empty key",
			key:      "",
			expected: []string{},
		},
		{
			name:     "key with empty parts",
			key:      "steemd..get_block",
			expected: []string{"steemd", "get_block"},
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			parts := splitKey(tt.key)
			
			if !reflect.DeepEqual(parts, tt.expected) {
				t.Errorf("expected parts %v, got %v", tt.expected, parts)
			}
			
			// Test join key (reverse operation)
			if len(tt.expected) > 0 {
				joined := joinKey(tt.expected)
				// Remove empty parts from original key for comparison
				expectedJoined := tt.key
				for expectedJoined != joined && len(expectedJoined) > 0 {
					if expectedJoined[0] == '.' {
						expectedJoined = expectedJoined[1:]
					} else if expectedJoined[len(expectedJoined)-1] == '.' {
						expectedJoined = expectedJoined[:len(expectedJoined)-1]
					} else {
						break
					}
				}
				// For keys with consecutive dots, we expect them to be cleaned up
				if tt.key == "steemd..get_block" {
					expectedJoined = "steemd.get_block"
				}
				if joined != expectedJoined && tt.key != "" {
					t.Errorf("expected joined key %s, got %s", expectedJoined, joined)
				}
			}
		})
	}
}

func TestTrieOverwrite(t *testing.T) {
	trie := NewTrie()
	
	// Insert initial value
	trie.Insert("steemd.get_block", "initial_config")
	
	// Verify initial value
	_, value, found := trie.LongestPrefix("steemd.get_block")
	if !found || value != "initial_config" {
		t.Errorf("expected initial_config, got %v (found: %v)", value, found)
	}
	
	// Overwrite with new value
	trie.Insert("steemd.get_block", "updated_config")
	
	// Verify updated value
	_, value, found = trie.LongestPrefix("steemd.get_block")
	if !found || value != "updated_config" {
		t.Errorf("expected updated_config, got %v (found: %v)", value, found)
	}
}
