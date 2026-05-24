package upstream

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/gobwas/ws"
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

	// For WebSocket URLs, try to establish a connection
	if strings.HasPrefix(urlStr, "ws://") || strings.HasPrefix(urlStr, "wss://") {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		// Try to dial WebSocket connection
		conn, _, _, err := ws.Dial(ctx, urlStr)
		if err != nil {
			return fmt.Errorf("websocket connection failed: %w", err)
		}
		conn.Close()
		return nil
	}

	return fmt.Errorf("unsupported URL scheme")
}

