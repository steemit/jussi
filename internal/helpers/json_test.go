package helpers

import (
	"encoding/json"
	"testing"
)

func TestMarshalJSONWithoutHTMLEscape(t *testing.T) {
	tests := []struct {
		name     string
		input    interface{}
		wantErr  bool
		checkFn  func(t *testing.T, got []byte)
	}{
		{
			name: "basic map without HTML chars",
			input: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "call",
				"id":      1,
			},
			wantErr: false,
			checkFn: func(t *testing.T, got []byte) {
				// Should parse successfully
				var result map[string]interface{}
				if err := json.Unmarshal(got, &result); err != nil {
					t.Fatalf("failed to unmarshal result: %v", err)
				}
				if result["method"] != "call" {
					t.Errorf("method = %v, want call", result["method"])
				}
			},
		},
		{
			name: "markdown body with greater-than sign",
			input: map[string]interface{}{
				"params": []interface{}{
					"network_broadcast_api",
					"broadcast_transaction_synchronous",
					map[string]interface{}{
						"body": "> **Key Observation**\n> Some quote",
					},
				},
			},
			wantErr: false,
			checkFn: func(t *testing.T, got []byte) {
				// Critical: '>' must NOT be escaped to \u003e
				if contains(got, []byte(`\u003e`)) {
					t.Errorf("output contains \\u003e escape; '>' should remain literal")
				}
				// Verify literal '>' is present
				if !contains(got, []byte(`">`)) {
					t.Errorf("literal '>' not found in output")
				}
			},
		},
		{
			name: "body with less-than sign",
			input: map[string]interface{}{
				"body": "5 < 10",
			},
			wantErr: false,
			checkFn: func(t *testing.T, got []byte) {
				if contains(got, []byte(`\u003c`)) {
					t.Errorf("output contains \\u003c escape; '<' should remain literal")
				}
			},
		},
		{
			name: "body with ampersand",
			input: map[string]interface{}{
				"body": "A & B",
			},
			wantErr: false,
			checkFn: func(t *testing.T, got []byte) {
				if contains(got, []byte(`\u0026`)) {
					t.Errorf("output contains \\u0026 escape; '&' should remain literal")
				}
			},
		},
		{
			name: "combined HTML special chars",
			input: map[string]interface{}{
				"body": "<div>Hello & Welcome></div>",
			},
			wantErr: false,
			checkFn: func(t *testing.T, got []byte) {
				// None of the chars should be escaped
				if contains(got, []byte(`\u003c`)) || contains(got, []byte(`\u003e`)) || contains(got, []byte(`\u0026`)) {
					t.Errorf("HTML special chars were escaped; should remain literal")
				}
			},
		},
		{
			name:    "nil input",
			input:   nil,
			wantErr: false,
			checkFn: func(t *testing.T, got []byte) {
				if string(got) != "null" {
					t.Errorf("nil serialized to %q, want null", string(got))
				}
			},
		},
		{
			name: "no trailing newline",
			input: map[string]interface{}{
				"test": "value",
			},
			wantErr: false,
			checkFn: func(t *testing.T, got []byte) {
				if len(got) > 0 && got[len(got)-1] == '\n' {
					t.Errorf("output ends with newline; should be stripped")
				}
			},
		},
		{
			name: "byte-exact match with json.Marshal for non-HTML",
			input: map[string]interface{}{
				"a": "hello",
				"b": 123,
				"c": true,
			},
			wantErr: false,
			checkFn: func(t *testing.T, got []byte) {
				// For data without HTML chars, output should match json.Marshal
				want, err := json.Marshal(map[string]interface{}{
					"a": "hello",
					"b": 123,
					"c": true,
				})
				if err != nil {
					t.Fatalf("json.Marshal failed: %v", err)
				}
				if string(got) != string(want) {
					t.Errorf("output mismatch\ngot:  %s\nwant: %s", got, want)
				}
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := MarshalJSONWithoutHTMLEscape(tt.input)
			if (err != nil) != tt.wantErr {
				t.Fatalf("MarshalJSONWithoutHTMLEscape() error = %v, wantErr %v", err, tt.wantErr)
			}
			if tt.checkFn != nil {
				tt.checkFn(t, got)
			}
		})
	}
}

// contains checks if haystack contains needle as a substring.
func contains(haystack, needle []byte) bool {
	return len(haystack) >= len(needle) && indexOf(haystack, needle) >= 0
}

// indexOf returns the index of the first occurrence of needle in haystack,
// or -1 if not found.
func indexOf(haystack, needle []byte) int {
	for i := 0; i <= len(haystack)-len(needle); i++ {
		match := true
		for j := 0; j < len(needle); j++ {
			if haystack[i+j] != needle[j] {
				match = false
				break
			}
		}
		if match {
			return i
		}
	}
	return -1
}
