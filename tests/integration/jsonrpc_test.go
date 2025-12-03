package integration

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestCase represents a single JSON-RPC test case
type TestCase struct {
	Request  interface{} `json:"request"`
	Expected interface{} `json:"expected"`
}

// loadTestCases loads test cases from a JSON file
func loadTestCases(t *testing.T, filename string) []TestCase {
	// Try multiple possible paths
	possiblePaths := []string{
		filepath.Join("legacy", "tests", "data", "jsonrpc", filename),
		filepath.Join("..", "legacy", "tests", "data", "jsonrpc", filename),
		filepath.Join("..", "..", "legacy", "tests", "data", "jsonrpc", filename),
		filepath.Join("tests", "legacy", "tests", "data", "jsonrpc", filename),
	}

	var testDataPath string
	var found bool
	for _, path := range possiblePaths {
		if _, err := os.Stat(path); err == nil {
			testDataPath = path
			found = true
			break
		}
	}

	if !found {
		t.Skipf("Test data file not found: %s (tried: %v)", filename, possiblePaths)
		return nil
	}

	data, err := os.ReadFile(testDataPath)
	require.NoError(t, err, "Failed to read test data file")

	// Parse JSON array of [request, expected] pairs
	var testCases [][]interface{}
	err = json.Unmarshal(data, &testCases)
	require.NoError(t, err, "Failed to parse test data")

	// Convert to TestCase slice
	cases := make([]TestCase, 0, len(testCases))
	for _, pair := range testCases {
		if len(pair) >= 2 {
			cases = append(cases, TestCase{
				Request:  pair[0],
				Expected: pair[1],
			})
		}
	}

	return cases
}

// TestAppbaseJSONRPC tests appbase.json test cases
func TestAppbaseJSONRPC(t *testing.T) {
	testCases := loadTestCases(t, "appbase.json")
	if len(testCases) == 0 {
		t.Skip("No test cases loaded")
	}

	// Load all test cases (appbase.json has 77 cases)
	// Can be limited if needed for faster test runs
	maxCases := len(testCases)
	// Uncomment to limit test cases:
	// maxCases := 50
	if len(testCases) > maxCases {
		testCases = testCases[:maxCases]
	}

	// Create mock upstream server
	mockResponses := make(map[string]interface{})
	for _, tc := range testCases {
		// Extract method from request
		if reqMap, ok := tc.Request.(map[string]interface{}); ok {
			if method, ok := reqMap["method"].(string); ok {
				// Store expected response keyed by method
				if expectedMap, ok := tc.Expected.(map[string]interface{}); ok {
					mockResponses[method] = expectedMap
				}
			}
		}
	}

	mockUpstream := mockUpstreamServer(t, mockResponses)
	defer mockUpstream.Close()

	// Create test server
	server, _ := setupTestServerWithUpstream(t, mockUpstream.URL)
	defer server.Close()

	// Run test cases
	for i, tc := range testCases {
		t.Run(fmt.Sprintf("case_%d", i), func(t *testing.T) {
			// Make request
			resp, responseBody := makeRequest(t, server, tc.Request)

			// Check status
			assert.Equal(t, 200, resp.StatusCode, "Expected status 200")

			// Check response structure matches expected
			// Note: We're doing a simplified comparison here
			// Full comparison would need to handle ID matching and result comparison
			if expectedMap, ok := tc.Expected.(map[string]interface{}); ok {
				// Check jsonrpc version
				if expectedJSONRPC, ok := expectedMap["jsonrpc"].(string); ok {
					assert.Equal(t, expectedJSONRPC, responseBody["jsonrpc"], "JSON-RPC version mismatch")
				}

				// Check ID matches request
				if reqMap, ok := tc.Request.(map[string]interface{}); ok {
					if reqID, ok := reqMap["id"]; ok {
						assert.Equal(t, reqID, responseBody["id"], "ID mismatch")
					}
				}
			}
		})
	}
}

// TestSteemdJSONRPC tests steemd.json test cases
func TestSteemdJSONRPC(t *testing.T) {
	testCases := loadTestCases(t, "steemd.json")
	if len(testCases) == 0 {
		t.Skip("No test cases loaded")
	}

	// Load all test cases (steemd.json has 84 cases)
	// All test cases will be run
	t.Logf("Loading %d test cases from steemd.json", len(testCases))

	// Create mock upstream server
	mockResponses := make(map[string]interface{})
	for _, tc := range testCases {
		if reqMap, ok := tc.Request.(map[string]interface{}); ok {
			if method, ok := reqMap["method"].(string); ok {
				if expectedMap, ok := tc.Expected.(map[string]interface{}); ok {
					mockResponses[method] = expectedMap
				}
			}
		}
	}

	mockUpstream := mockUpstreamServer(t, mockResponses)
	defer mockUpstream.Close()

	// Create test server
	server, _ := setupTestServerWithUpstream(t, mockUpstream.URL)
	defer server.Close()

	// Run test cases
	for i, tc := range testCases {
		t.Run(fmt.Sprintf("case_%d", i), func(t *testing.T) {
			// Make request
			resp, responseBody := makeRequest(t, server, tc.Request)

			// Check status
			assert.Equal(t, 200, resp.StatusCode, "Expected status 200")

			// Check response structure
			if expectedMap, ok := tc.Expected.(map[string]interface{}); ok {
				if expectedJSONRPC, ok := expectedMap["jsonrpc"].(string); ok {
					assert.Equal(t, expectedJSONRPC, responseBody["jsonrpc"], "JSON-RPC version mismatch")
				}

				if reqMap, ok := tc.Request.(map[string]interface{}); ok {
					if reqID, ok := reqMap["id"]; ok {
						assert.Equal(t, reqID, responseBody["id"], "ID mismatch")
					}
				}
			}
		})
	}
}
