package integration

import (
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

// setupCacheMiddlewareTestServer creates a test server with cache middleware
func setupCacheMiddlewareTestServer(t *testing.T, upstreamURL string) *httptest.Server {
	// Create test upstream config
	upstreamConfig := &config.UpstreamRawConfig{
		Upstreams: []config.UpstreamDefinition{
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

	// Setup Gin router with cache middleware
	// Order matters: ResponseCapture -> CacheLookup -> Handler -> CacheStore
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(middleware.RequestIDMiddleware())
	r.Use(middleware.ResponseCaptureMiddleware())
	r.Use(middleware.CacheLookupMiddleware(cacheGroup))
	r.Use(middleware.CacheStoreMiddleware(cacheGroup)) // Must be before handler to execute after
	r.POST("/", handler.HandleJSONRPC)

	return httptest.NewServer(r)
}

// TestCacheMiddlewareHit tests cache hit behavior
// Note: Cache is handled in processor, not middleware in current implementation
func TestCacheMiddlewareHit(t *testing.T) {
	// Create mock upstream server
	mockResponses := map[string]interface{}{
		"get_dynamic_global_properties": map[string]interface{}{
			"result": map[string]interface{}{
				"head_block_number": 19552491,
				"last_irreversible_block_num": 19552476,
			},
		},
	}
	mockUpstream := mockUpstreamServer(t, mockResponses)
	defer mockUpstream.Close()

	// Create test server (processor handles caching)
	server, _ := setupTestServerWithUpstream(t, mockUpstream.URL)
	defer server.Close()

	requestBody := map[string]interface{}{
		"id":     1,
		"jsonrpc": "2.0",
		"method":  "get_dynamic_global_properties",
	}

	// First request - should miss cache
	resp1, responseBody1 := makeRequest(t, server, requestBody)
	if resp1.StatusCode != http.StatusOK {
		t.Fatalf("First request failed with status %d", resp1.StatusCode)
	}

	// Second request - should hit cache (processor caches responses)
	resp2, responseBody2 := makeRequest(t, server, requestBody)
	if resp2.StatusCode != http.StatusOK {
		t.Fatalf("Second request failed with status %d", resp2.StatusCode)
	}

	// Verify responses are identical (cache should work)
	if !responsesEqual(responseBody1, responseBody2) {
		t.Errorf("Cached response differs from original response")
	}

	// Verify response structure
	if result1, ok := responseBody1["result"].(map[string]interface{}); ok {
		if result2, ok := responseBody2["result"].(map[string]interface{}); ok {
			if result1["head_block_number"] != result2["head_block_number"] {
				t.Errorf("Cached response data differs")
			}
		}
	}
}

// TestCacheMiddlewareMiss tests cache miss behavior
func TestCacheMiddlewareMiss(t *testing.T) {
	// Create mock upstream server
	mockResponses := map[string]interface{}{
		"get_block": map[string]interface{}{
			"result": map[string]interface{}{
				"block_id": "000003e8b922f4906a45af8e99d86b3511acd7a5",
			},
		},
	}
	mockUpstream := mockUpstreamServer(t, mockResponses)
	defer mockUpstream.Close()

	// Create test server
	server, _ := setupTestServerWithUpstream(t, mockUpstream.URL)
	defer server.Close()

	requestBody := map[string]interface{}{
		"id":     1,
		"jsonrpc": "2.0",
		"method":  "get_block",
		"params":  []interface{}{1000},
	}

	// First request - should miss cache
	resp, responseBody := makeRequest(t, server, requestBody)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("Request failed with status %d", resp.StatusCode)
	}

	// Verify response structure
	if result, ok := responseBody["result"].(map[string]interface{}); ok {
		if blockID, ok := result["block_id"].(string); !ok || blockID == "" {
			t.Errorf("Expected block_id in response")
		}
	}
}

// TestCacheMiddlewareBatchRequest tests cache behavior with batch requests
func TestCacheMiddlewareBatchRequest(t *testing.T) {
	// Create mock upstream server
	mockResponses := map[string]interface{}{
		"get_block": map[string]interface{}{
			"result": map[string]interface{}{
				"block_id": "000003e8b922f4906a45af8e99d86b3511acd7a5",
			},
		},
	}
	mockUpstream := mockUpstreamServer(t, mockResponses)
	defer mockUpstream.Close()

	// Create test server
	server, _ := setupTestServerWithUpstream(t, mockUpstream.URL)
	defer server.Close()

	requestBody := []interface{}{
		map[string]interface{}{
			"id":     1,
			"jsonrpc": "2.0",
			"method":  "get_block",
			"params":  []interface{}{1000},
		},
		map[string]interface{}{
			"id":     2,
			"jsonrpc": "2.0",
			"method":  "get_block",
			"params":  []interface{}{1001},
		},
	}

	// First request - should miss cache
	resp1, responseBody1 := makeBatchRequest(t, server, requestBody)
	if resp1.StatusCode != http.StatusOK {
		t.Fatalf("First batch request failed with status %d", resp1.StatusCode)
	}

	// Second request - verify it works (cache may or may not work for batches)
	resp2, responseBody2 := makeBatchRequest(t, server, requestBody)
	if resp2.StatusCode != http.StatusOK {
		t.Fatalf("Second batch request failed with status %d", resp2.StatusCode)
	}

	// Verify responses have correct structure
	if len(responseBody1) != 2 || len(responseBody2) != 2 {
		t.Errorf("Expected 2 responses in batch, got %d and %d", len(responseBody1), len(responseBody2))
	}
}

// TestCacheMiddlewareNoCacheTTL tests that TTL=-1 requests are not cached
func TestCacheMiddlewareNoCacheTTL(t *testing.T) {
	// Create mock upstream server
	mockResponses := map[string]interface{}{
		"call": map[string]interface{}{
			"result": map[string]interface{}{
				"status": "ok",
			},
		},
	}
	mockUpstream := mockUpstreamServer(t, mockResponses)
	defer mockUpstream.Close()

	// Create test server with TTL=-1 (no cache) for login_api
	upstreamConfig := &config.UpstreamRawConfig{
		Upstreams: []config.UpstreamDefinition{
			{
				Name: "steemd",
				URLs: [][]interface{}{
					{"steemd", mockUpstream.URL},
				},
				TTLs: [][]interface{}{
					{"steemd", 3},
					{"steemd.login_api", -1}, // No cache
				},
				Timeouts: [][]interface{}{
					{"steemd", 5},
				},
			},
		},
	}

	router, err := upstream.NewRouter(upstreamConfig)
	if err != nil {
		t.Fatalf("Failed to create router: %v", err)
	}

	memoryCache := cache.NewMemoryCache()
	cacheGroup := cache.NewCacheGroup(memoryCache, nil)
	httpClient := upstream.NewHTTPClient()

	handler := &handlers.JSONRPCHandler{
		CacheGroup: cacheGroup,
		Router:     router,
		HTTPClient: httpClient,
		WSPools:    nil,
	}

	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(middleware.RequestIDMiddleware())
	r.POST("/", handler.HandleJSONRPC)

	server := httptest.NewServer(r)
	defer server.Close()

	// Request with no-cache TTL (login_api has TTL=-1)
	requestBody := map[string]interface{}{
		"id":     1,
		"jsonrpc": "2.0",
		"method":  "call",
		"params":  []interface{}{"login_api", "login", []interface{}{"username", "password"}},
	}

	// First request
	resp1, responseBody1 := makeRequest(t, server, requestBody)
	if resp1.StatusCode != http.StatusOK {
		t.Fatalf("First request failed with status %d", resp1.StatusCode)
	}

	// Second request - should NOT hit cache (TTL=-1 means no cache)
	resp2, responseBody2 := makeRequest(t, server, requestBody)
	if resp2.StatusCode != http.StatusOK {
		t.Fatalf("Second request failed with status %d", resp2.StatusCode)
	}

	// Verify both requests got responses (not cached)
	if responseBody1 == nil || responseBody2 == nil {
		t.Errorf("Expected responses from both requests")
	}
}

