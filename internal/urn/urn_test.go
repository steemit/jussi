package urn

import (
	"fmt"
	"testing"
)

func TestFromRequest(t *testing.T) {
	tests := []struct {
		name     string
		request  map[string]interface{}
		expected URN
		hasError bool
	}{
		{
			name: "simple steemd method",
			request: map[string]interface{}{
				"method": "get_block",
				"params": []interface{}{1000},
			},
			expected: URN{
				Namespace: "steemd",
				API:       "database_api",
				Method:    "get_block",
				Params:    []interface{}{1000},
			},
			hasError: false,
		},
		{
			name: "appbase method",
			request: map[string]interface{}{
				"method": "condenser_api.get_block",
				"params": []interface{}{1000},
			},
			expected: URN{
				Namespace: "appbase",
				API:       "condenser_api",
				Method:    "get_block",
				Params:    []interface{}{1000},
			},
			hasError: false,
		},
		{
			name: "nested appbase method",
			request: map[string]interface{}{
				"method": "database_api.get_dynamic_global_properties",
				"params": map[string]interface{}{},
			},
			expected: URN{
				Namespace: "appbase",
				API:       "database_api",
				Method:    "get_dynamic_global_properties",
				Params:    map[string]interface{}{},
			},
			hasError: false,
		},
		{
			name: "missing method",
			request: map[string]interface{}{
				"params": []interface{}{1000},
			},
			expected: URN{},
			hasError: true,
		},
		{
			name: "invalid method type",
			request: map[string]interface{}{
				"method": 123,
				"params": []interface{}{1000},
			},
			expected: URN{},
			hasError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := FromRequest(tt.request)
			
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
			
			if result.Namespace != tt.expected.Namespace {
				t.Errorf("expected namespace %s, got %s", tt.expected.Namespace, result.Namespace)
			}
			
			if result.API != tt.expected.API {
				t.Errorf("expected API %s, got %s", tt.expected.API, result.API)
			}
			
			if result.Method != tt.expected.Method {
				t.Errorf("expected method %s, got %s", tt.expected.Method, result.Method)
			}
			
			// Compare params using string representation for consistency
			expectedParamsStr := fmt.Sprintf("%v", tt.expected.Params)
			resultParamsStr := fmt.Sprintf("%v", result.Params)
			if resultParamsStr != expectedParamsStr {
				t.Errorf("expected params %s, got %s", expectedParamsStr, resultParamsStr)
			}
		})
	}
}

func TestURNString(t *testing.T) {
	tests := []struct {
		name     string
		urn      URN
		expected string
	}{
		{
			name: "steemd method",
			urn: URN{
				Namespace: "steemd",
				API:       "",
				Method:    "get_block",
				Params:    "1000",
			},
			expected: "steemd.get_block",
		},
		{
			name: "appbase method",
			urn: URN{
				Namespace: "appbase",
				API:       "condenser_api",
				Method:    "get_block",
				Params:    "1000",
			},
			expected: "appbase.condenser_api.get_block",
		},
		{
			name: "empty params",
			urn: URN{
				Namespace: "steemd",
				API:       "",
				Method:    "get_dynamic_global_properties",
				Params:    "",
			},
			expected: "steemd.get_dynamic_global_properties",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := tt.urn.String()
			if result != tt.expected {
				t.Errorf("expected %s, got %s", tt.expected, result)
			}
		})
	}
}
