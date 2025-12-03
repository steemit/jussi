package integration

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
	"github.com/steemit/jussi/internal/config"
	"github.com/steemit/jussi/internal/handlers"
	"github.com/steemit/jussi/internal/middleware"
	"github.com/steemit/jussi/internal/upstream"
)

// mockUpstreamServer creates a mock upstream server that returns predefined responses
func mockUpstreamServer(t *testing.T, responses map[string]interface{}) *httptest.Server {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	
	r.POST("/", func(c *gin.Context) {
		var requestBody map[string]interface{}
		if err := c.ShouldBindJSON(&requestBody); err != nil {
			c.JSON(http.StatusBadRequest, map[string]interface{}{
				"error": "invalid request",
			})
			return
		}

		method, _ := requestBody["method"].(string)
		id, _ := requestBody["id"]

		// Look up response by method
		if response, ok := responses[method]; ok {
			responseMap := response.(map[string]interface{})
			responseMap["id"] = id
			responseMap["jsonrpc"] = "2.0"
			c.JSON(http.StatusOK, responseMap)
		} else {
			// Default response
			c.JSON(http.StatusOK, map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      id,
				"result":  map[string]interface{}{"status": "ok"},
			})
		}
	})

	return httptest.NewServer(r)
}

// setupTestServerWithUpstream creates a test server with a mock upstream
func setupTestServerWithUpstream(t *testing.T, upstreamURL string) (*httptest.Server, *handlers.JSONRPCHandler) {
	// Create test upstream config pointing to mock upstream
	// Support multiple namespaces: test, appbase, steemd
	upstreamConfig := &config.UpstreamRawConfig{
		Upstreams: []config.UpstreamDefinition{
			{
				Name: "test",
				URLs: [][]interface{}{
					{"test", upstreamURL},
				},
				TTLs: [][]interface{}{
					{"test", 3},
				},
				Timeouts: [][]interface{}{
					{"test", 5},
				},
			},
			{
				Name: "appbase",
				URLs: [][]interface{}{
					{"appbase", upstreamURL},
				},
				TTLs: [][]interface{}{
					{"appbase", 3},
				},
				Timeouts: [][]interface{}{
					{"appbase", 5},
				},
			},
			{
				Name: "steemd",
				URLs: [][]interface{}{
					{"steemd", upstreamURL},
				},
				TTLs: [][]interface{}{
					{"steemd", 3},
				},
				Timeouts: [][]interface{}{
					{"steemd", 5},
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

// TestUpstreamRequest tests a request that goes to upstream
func TestUpstreamRequest(t *testing.T) {
	// Create mock upstream server
	mockResponses := map[string]interface{}{
		"test.method": map[string]interface{}{
			"result": map[string]interface{}{
				"value": "test-response",
			},
		},
	}
	mockUpstream := mockUpstreamServer(t, mockResponses)
	defer mockUpstream.Close()

	// Create test server pointing to mock upstream
	server, _ := setupTestServerWithUpstream(t, mockUpstream.URL)
	defer server.Close()

	// Make request
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

	// Check response
	if result, ok := responseBody["result"].(map[string]interface{}); ok {
		if value, ok := result["value"].(string); !ok || value != "test-response" {
			t.Errorf("Expected result.value 'test-response', got %v", result)
		}
	} else {
		t.Errorf("Expected result in response, got %v", responseBody)
	}
}

// TestCacheHit tests that cached responses are returned
func TestCacheHit(t *testing.T) {
	// Create mock upstream server
	mockResponses := map[string]interface{}{
		"test.method": map[string]interface{}{
			"result": map[string]interface{}{
				"value": "cached-response",
			},
		},
	}
	mockUpstream := mockUpstreamServer(t, mockResponses)
	defer mockUpstream.Close()

	// Create test server pointing to mock upstream
	server, _ := setupTestServerWithUpstream(t, mockUpstream.URL)
	defer server.Close()

	// First request - should hit upstream
	requestBody := map[string]interface{}{
		"jsonrpc": "2.0",
		"method":  "test.method",
		"params":  []interface{}{},
		"id":      1,
	}

	resp1, responseBody1 := makeRequest(t, server, requestBody)
	if resp1.StatusCode != http.StatusOK {
		t.Fatalf("First request failed with status %d", resp1.StatusCode)
	}

	// Second request - should hit cache
	resp2, responseBody2 := makeRequest(t, server, requestBody)
	if resp2.StatusCode != http.StatusOK {
		t.Fatalf("Second request failed with status %d", resp2.StatusCode)
	}

	// Responses should be identical
	if !responsesEqual(responseBody1, responseBody2) {
		t.Errorf("Cached response differs from original response")
	}
}

// TestBatchRequestWithUpstream tests batch requests with upstream
func TestBatchRequestWithUpstream(t *testing.T) {
	// Create mock upstream server
	mockResponses := map[string]interface{}{
		"test.method1": map[string]interface{}{
			"result": map[string]interface{}{"value": "response1"},
		},
		"test.method2": map[string]interface{}{
			"result": map[string]interface{}{"value": "response2"},
		},
	}
	mockUpstream := mockUpstreamServer(t, mockResponses)
	defer mockUpstream.Close()

	// Create test server pointing to mock upstream
	server, _ := setupTestServerWithUpstream(t, mockUpstream.URL)
	defer server.Close()

	// Make batch request
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
		t.Fatalf("Expected 2 responses, got %d", len(responseBody))
	}

	// Check first response
	if resp1, ok := responseBody[0].(map[string]interface{}); ok {
		if result, ok := resp1["result"].(map[string]interface{}); ok {
			if value, ok := result["value"].(string); !ok || value != "response1" {
				t.Errorf("Expected first response value 'response1', got %v", result)
			}
		}
	}

	// Check second response
	if resp2, ok := responseBody[1].(map[string]interface{}); ok {
		if result, ok := resp2["result"].(map[string]interface{}); ok {
			if value, ok := result["value"].(string); !ok || value != "response2" {
				t.Errorf("Expected second response value 'response2', got %v", result)
			}
		}
	}
}

// Helper function to compare responses
func responsesEqual(a, b map[string]interface{}) bool {
	aBytes, _ := json.Marshal(a)
	bBytes, _ := json.Marshal(b)
	return string(aBytes) == string(bBytes)
}

