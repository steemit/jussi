package upstream

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
)

// HTTPClient handles HTTP upstream requests
type HTTPClient struct {
	client *http.Client
}

// NewHTTPClient creates a new HTTP client
func NewHTTPClient() *HTTPClient {
	return &HTTPClient{
		client: &http.Client{
			// Do not set a global timeout here; each request uses
			// context.WithTimeout in callHTTPUpstream to avoid nested
			// timeout conflicts between transport and context.
			Transport: &http.Transport{
				MaxIdleConns:        100,
				MaxIdleConnsPerHost: 10,
				IdleConnTimeout:     90 * time.Second,
			},
		},
	}
}

// Request sends an HTTP POST request to upstream (fail-fast, no retry).
// As a proxy/routing layer, jussi should return errors immediately and
// let the caller decide whether to retry. Retrying at the proxy level
// is dangerous for non-idempotent requests (e.g. broadcast_transaction)
// and adds latency for all requests.
func (c *HTTPClient) Request(ctx context.Context, url string, payload map[string]interface{}, headers map[string]string) (map[string]interface{}, error) {
	// Marshal payload
	body, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Create request
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")

	// Inject OpenTelemetry trace context into HTTP headers
	// This ensures trace continuity across service boundaries
	propagator := otel.GetTextMapPropagator()
	propagator.Inject(ctx, propagation.HeaderCarrier(req.Header))

	// Set custom headers (after trace context to avoid conflicts)
	for k, v := range headers {
		req.Header.Set(k, v)
	}

	// Send request
	resp, err := c.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("upstream request failed: %w", err)
	}
	defer resp.Body.Close()

	// Check for server errors
	if resp.StatusCode >= 500 {
		return nil, fmt.Errorf("upstream server error: %d", resp.StatusCode)
	}

	// Read response
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	// Parse JSON response
	var result map[string]interface{}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return result, nil
}

// Close closes the HTTP client
func (c *HTTPClient) Close() error {
	// HTTP client doesn't need explicit closing
	return nil
}
