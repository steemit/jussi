package integration

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
	"github.com/steemit/jussi/internal/config"
	"github.com/steemit/jussi/internal/handlers"
	"github.com/steemit/jussi/internal/middleware"
	"github.com/steemit/jussi/internal/upstream"
)

// setupTestServer creates a test HTTP server with handlers
func setupTestServer(t *testing.T) (*httptest.Server, *handlers.JSONRPCHandler) {
	// Create test upstream config
	upstreamConfig := &config.UpstreamRawConfig{
		Upstreams: []config.UpstreamDefinition{
			{
				Name: "test",
				URLs: [][]interface{}{
					{"test", "http://localhost:8080"},
				},
				TTLs: [][]interface{}{
					{"test", 3},
				},
				Timeouts: [][]interface{}{
					{"test", 5},
				},
			},
		},
	}

	// Create router
	router, err := upstream.NewRouter(upstreamConfig)
	if err != nil {
		t.Fatalf("Failed to create router: %v", err)
	}

	// Create cache group (memory only for testing)
	memoryCache := cache.NewMemoryCache()
	cacheGroup := cache.NewCacheGroup(memoryCache, nil)

	// Create HTTP client
	httpClient := upstream.NewHTTPClient()

	// Create handler
	handler := &handlers.JSONRPCHandler{
		CacheGroup: cacheGroup,
		Router:     router,
		HTTPClient: httpClient,
		WSPools:    nil,
	}

	// Setup Gin router
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(middleware.RequestIDMiddleware())
	r.POST("/", handler.HandleJSONRPC)

	// Create test server
	server := httptest.NewServer(r)

	return server, handler
}

// makeRequest sends a JSON-RPC request to the test server
func makeRequest(t *testing.T, server *httptest.Server, requestBody interface{}) (*http.Response, map[string]interface{}) {
	bodyBytes, err := json.Marshal(requestBody)
	if err != nil {
		t.Fatalf("Failed to marshal request: %v", err)
	}

	req, err := http.NewRequest("POST", server.URL+"/", bytes.NewBuffer(bodyBytes))
	if err != nil {
		t.Fatalf("Failed to create request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("Failed to send request: %v", err)
	}

	var responseBody map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&responseBody); err != nil {
		resp.Body.Close()
		t.Fatalf("Failed to decode response: %v", err)
	}
	resp.Body.Close()

	return resp, responseBody
}

// makeBatchRequest sends a JSON-RPC batch request to the test server
func makeBatchRequest(t *testing.T, server *httptest.Server, requestBody []interface{}) (*http.Response, []interface{}) {
	bodyBytes, err := json.Marshal(requestBody)
	if err != nil {
		t.Fatalf("Failed to marshal request: %v", err)
	}

	req, err := http.NewRequest("POST", server.URL+"/", bytes.NewBuffer(bodyBytes))
	if err != nil {
		t.Fatalf("Failed to create request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("Failed to send request: %v", err)
	}

	var responseBody []interface{}
	if err := json.NewDecoder(resp.Body).Decode(&responseBody); err != nil {
		resp.Body.Close()
		t.Fatalf("Failed to decode response: %v", err)
	}
	resp.Body.Close()

	return resp, responseBody
}

// TestJSONRPCSingleRequest tests a single JSON-RPC request
func TestJSONRPCSingleRequest(t *testing.T) {
	server, _ := setupTestServer(t)
	defer server.Close()

	requestBody := map[string]interface{}{
		"jsonrpc": "2.0",
		"method":  "test.method",
		"params":  []interface{}{},
		"id":      1,
	}

	resp, responseBody := makeRequest(t, server, requestBody)

	if resp.StatusCode != http.StatusOK {
		t.Errorf("Expected status 200, got %d", resp.StatusCode)
	}

	// Check response structure
	if jsonrpc, ok := responseBody["jsonrpc"].(string); !ok || jsonrpc != "2.0" {
		t.Errorf("Expected jsonrpc '2.0', got %v", responseBody["jsonrpc"])
	}

	if id, ok := responseBody["id"]; !ok || id != float64(1) {
		t.Errorf("Expected id 1, got %v", id)
	}
}

// TestJSONRPCBatchRequest tests a batch JSON-RPC request
func TestJSONRPCBatchRequest(t *testing.T) {
	server, _ := setupTestServer(t)
	defer server.Close()

	requestBody := []interface{}{
		map[string]interface{}{
			"jsonrpc": "2.0",
			"method":  "test.method1",
			"params":  []interface{}{},
			"id":      1,
		},
		map[string]interface{}{
			"jsonrpc": "2.0",
			"method":  "test.method2",
			"params":  []interface{}{},
			"id":      2,
		},
	}

	resp, responseBody := makeBatchRequest(t, server, requestBody)

	if resp.StatusCode != http.StatusOK {
		t.Errorf("Expected status 200, got %d", resp.StatusCode)
	}

	if len(responseBody) != 2 {
		t.Errorf("Expected 2 responses, got %d", len(responseBody))
	}
}

// TestJSONRPCInvalidRequest tests invalid JSON-RPC requests
func TestJSONRPCInvalidRequest(t *testing.T) {
	server, _ := setupTestServer(t)
	defer server.Close()

	tests := []struct {
		name        string
		requestBody interface{}
		expectError bool
	}{
		{
			name: "missing jsonrpc",
			requestBody: map[string]interface{}{
				"method": "test.method",
				"id":     1,
			},
			expectError: true,
		},
		{
			name: "invalid jsonrpc version",
			requestBody: map[string]interface{}{
				"jsonrpc": "1.0",
				"method":  "test.method",
				"id":      1,
			},
			expectError: true,
		},
		{
			name: "missing method",
			requestBody: map[string]interface{}{
				"jsonrpc": "2.0",
				"id":     1,
			},
			expectError: true,
		},
		{
			name: "empty method",
			requestBody: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "",
				"id":      1,
			},
			expectError: true,
		},
		{
			name: "invalid params type",
			requestBody: map[string]interface{}{
				"jsonrpc": "2.0",
				"method":  "test.method",
				"params":  "invalid",
				"id":      1,
			},
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			resp, responseBody := makeRequest(t, server, tt.requestBody)

			if tt.expectError {
				if resp.StatusCode != http.StatusOK {
					t.Errorf("Expected status 200 for error response, got %d", resp.StatusCode)
				}
				if _, ok := responseBody["error"]; !ok {
					t.Errorf("Expected error in response, got %v", responseBody)
				}
			} else {
				if resp.StatusCode != http.StatusOK {
					t.Errorf("Expected status 200, got %d", resp.StatusCode)
				}
				if _, ok := responseBody["error"]; ok {
					t.Errorf("Unexpected error in response: %v", responseBody)
				}
			}
		})
	}
}

// TestRequestIDMiddleware tests that request ID middleware works
func TestRequestIDMiddleware(t *testing.T) {
	server, _ := setupTestServer(t)
	defer server.Close()

	requestBody := map[string]interface{}{
		"jsonrpc": "2.0",
		"method":  "test.method",
		"params":  []interface{}{},
		"id":      1,
	}

	req, err := http.NewRequest("POST", server.URL+"/", bytes.NewBuffer(mustMarshal(t, requestBody)))
	if err != nil {
		t.Fatalf("Failed to create request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-jussi-request-id", "test-request-id-123")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("Failed to send request: %v", err)
	}
	defer resp.Body.Close()

	// Check that request ID header is set in response
	if resp.Header.Get("x-jussi-request-id") != "test-request-id-123" {
		t.Errorf("Expected x-jussi-request-id header to be 'test-request-id-123', got '%s'",
			resp.Header.Get("x-jussi-request-id"))
	}
}

// Helper function to marshal JSON
func mustMarshal(t *testing.T, v interface{}) []byte {
	bytes, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("Failed to marshal: %v", err)
	}
	return bytes
}

