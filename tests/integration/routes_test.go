package integration

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/handlers"
	"github.com/steemit/jussi/internal/middleware"
)

// contains checks if a string contains a substring
func contains(s, substr string) bool {
	return strings.Contains(s, substr)
}

// setupRoutesTestServer creates a test server with all routes
func setupRoutesTestServer() *httptest.Server {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.Use(middleware.RequestIDMiddleware())

	// Create health handler
	healthHandler := handlers.NewHealthHandler("test-commit", "test-tag", "test-service")

	// Setup routes
	r.GET("/health", healthHandler.HandleHealth)
	r.GET("/.well-known/healthcheck.json", healthHandler.HandleHealth)
	r.POST("/", func(c *gin.Context) {
		c.JSON(http.StatusOK, map[string]interface{}{
			"jsonrpc": "2.0",
			"id":      nil,
			"error": map[string]interface{}{
				"code":    -32600,
				"message": "Invalid Request",
			},
		})
	})

	return httptest.NewServer(r)
}

// TestHealthCheckRoute tests the health check endpoint
func TestHealthCheckRoute(t *testing.T) {
	server := setupRoutesTestServer()
	defer server.Close()

	// Test GET /health
	resp, err := http.Get(server.URL + "/health")
	if err != nil {
		t.Fatalf("Failed to make request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Errorf("Expected status 200, got %d", resp.StatusCode)
	}

	contentType := resp.Header.Get("Content-Type")
	if contentType != "application/json" && !contains(contentType, "application/json") {
		t.Errorf("Expected Content-Type application/json, got %s", contentType)
	}
}

// TestHealthCheckWellKnownRoute tests the .well-known/healthcheck.json endpoint
func TestHealthCheckWellKnownRoute(t *testing.T) {
	server := setupRoutesTestServer()
	defer server.Close()

	// Test GET /.well-known/healthcheck.json
	resp, err := http.Get(server.URL + "/.well-known/healthcheck.json")
	if err != nil {
		t.Fatalf("Failed to make request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Errorf("Expected status 200, got %d", resp.StatusCode)
	}
}

// TestRestrictedRoutes tests that certain HTTP methods work correctly
// Note: Gin allows all methods by default, so we test that GET works
func TestRestrictedRoutes(t *testing.T) {
	server := setupRoutesTestServer()
	defer server.Close()

	tests := []struct {
		name           string
		method         string
		path           string
		expectedStatus int
	}{
		{
			name:           "GET /health allowed",
			method:         "GET",
			path:           "/health",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "GET /.well-known/healthcheck.json allowed",
			method:         "GET",
			path:           "/.well-known/healthcheck.json",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "POST /health returns 404 (no handler)",
			method:         "POST",
			path:           "/health",
			expectedStatus: http.StatusNotFound,
		},
		{
			name:           "PUT /health returns 404 (no handler)",
			method:         "PUT",
			path:           "/health",
			expectedStatus: http.StatusNotFound,
		},
		{
			name:           "DELETE /health returns 404 (no handler)",
			method:         "DELETE",
			path:           "/health",
			expectedStatus: http.StatusNotFound,
		},
		{
			name:           "POST /.well-known/healthcheck.json returns 404 (no handler)",
			method:         "POST",
			path:           "/.well-known/healthcheck.json",
			expectedStatus: http.StatusNotFound,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req, err := http.NewRequest(tt.method, server.URL+tt.path, nil)
			if err != nil {
				t.Fatalf("Failed to create request: %v", err)
			}

			client := &http.Client{}
			resp, err := client.Do(req)
			if err != nil {
				t.Fatalf("Failed to send request: %v", err)
			}
			defer resp.Body.Close()

			if resp.StatusCode != tt.expectedStatus {
				t.Errorf("Expected status %d, got %d", tt.expectedStatus, resp.StatusCode)
			}
		})
	}
}

// TestRootRoute tests the root POST route
func TestRootRoute(t *testing.T) {
	server := setupRoutesTestServer()
	defer server.Close()

	// Test POST / (should be allowed)
	req, err := http.NewRequest("POST", server.URL+"/", nil)
	if err != nil {
		t.Fatalf("Failed to create request: %v", err)
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("Failed to send request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Errorf("Expected status 200, got %d", resp.StatusCode)
	}
}
