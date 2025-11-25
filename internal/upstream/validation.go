package upstream

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/steemit/jussi/internal/config"
)

// ValidateUpstreamURLs validates that all upstream URLs are reachable
// This is optional and can be disabled via TestURLs config
func ValidateUpstreamURLs(cfg *config.Config) error {
	if !cfg.Upstream.TestURLs {
		return nil // Skip validation if disabled
	}

	if cfg.Upstream.RawConfig == nil {
		return fmt.Errorf("upstream raw config is nil")
	}

	router, err := NewRouter(cfg.Upstream.RawConfig)
	if err != nil {
		return fmt.Errorf("failed to create router for validation: %w", err)
	}

	// Get all unique URLs from router
	urls := router.GetAllURLs()

	// Test each URL
	for _, urlStr := range urls {
		if err := testUpstreamURL(urlStr); err != nil {
			return fmt.Errorf("upstream URL validation failed for %s: %w", urlStr, err)
		}
	}

	return nil
}

// testUpstreamURL tests if an upstream URL is reachable
func testUpstreamURL(urlStr string) error {
	// For HTTP/HTTPS URLs, try to make a HEAD request
	if urlStr[:4] == "http" {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		req, err := http.NewRequestWithContext(ctx, "HEAD", urlStr, nil)
		if err != nil {
			return fmt.Errorf("failed to create request: %w", err)
		}

		client := &http.Client{
			Timeout: 5 * time.Second,
		}

		resp, err := client.Do(req)
		if err != nil {
			return fmt.Errorf("connection failed: %w", err)
		}
		defer resp.Body.Close()

		// Any response (even 404) means the server is reachable
		return nil
	}

	// For WebSocket URLs, we can't easily test without establishing a connection
	// Just validate the URL format
	if urlStr[:2] == "ws" {
		// WebSocket URLs will be validated when pools are created
		return nil
	}

	return fmt.Errorf("unsupported URL scheme")
}

