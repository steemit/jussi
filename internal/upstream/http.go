package upstream

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/steemit/jussi/internal/helpers"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
)

// HTTPClient handles HTTP upstream requests
type HTTPClient struct {
	client *http.Client
}

// UpstreamStatusError is a typed error carrying the HTTP status code from
// an upstream response (>= 500). Callers can use errors.As to reliably
// extract the code without string matching.
type UpstreamStatusError struct {
	StatusCode int
}

func (e *UpstreamStatusError) Error() string {
	return fmt.Sprintf("upstream server error: %d", e.StatusCode)
}

// NewHTTPClient creates a new HTTP client
func NewHTTPClient() *HTTPClient {
	return &HTTPClient{
		client: &http.Client{
			// Do not set a global timeout here; each request uses
			// context.WithTimeout in callHTTPUpstream to avoid nested
			// timeout conflicts between transport and context.
			Transport: &http.Transport{
				// Force HTTP/1.1 to avoid HTTP/2 multiplexing which causes
				// all requests to share a single TCP connection to the ALB.
				// With HTTP/1.1, the connection pool distributes requests
				// across multiple connections for better load balancing.
				ForceAttemptHTTP2: false,
				TLSClientConfig: &tls.Config{
					NextProtos: []string{"http/1.1"},
				},
				MaxIdleConns:        100,
				MaxIdleConnsPerHost: 10,
				// Limit total connections per host to force connection
				// rotation and prevent sticky connections to a single
				// backend instance behind the ALB.
				MaxConnsPerHost:   20,
				IdleConnTimeout:   90 * time.Second,
				DisableKeepAlives: false,
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
	// Marshal payload with HTML escaping disabled.
	// Go's json.Marshal escapes HTML special chars (<, >, &) to \uXXXX by
	// default.  steemd's FC JSON parser does not understand \u escapes, so
	// a body containing '>' would be received as 'u003e', breaking transaction
	// signatures.  Using json.Encoder with SetEscapeHTML(false) preserves the
	// literal characters.
	body, err := helpers.MarshalJSONWithoutHTMLEscape(payload)
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
		return nil, &UpstreamStatusError{StatusCode: resp.StatusCode}
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

// RequestWithRetry sends a request with bounded-attempt retry, but only
// retries when IsRetriableUpstreamError returns true for the most recent
// error. The total wall-clock budget is still bounded by ctx — once ctx
// is Done we stop immediately, even if attempts remain.
//
// This is for IDEMPOTENT requests only. Broadcast methods must call
// Request directly so a transient transport error never causes a duplicate
// submission.
func (c *HTTPClient) RequestWithRetry(
	ctx context.Context,
	url string,
	payload map[string]interface{},
	headers map[string]string,
	cfg RetryConfig,
) (map[string]interface{}, error) {
	if cfg.MaxAttempts < 1 {
		cfg.MaxAttempts = 1
	}
	var lastErr error
	for attempt := 1; attempt <= cfg.MaxAttempts; attempt++ {
		if attempt > 1 {
			select {
			case <-time.After(cfg.BackoffFor(attempt - 1)):
			case <-ctx.Done():
				return nil, ctx.Err()
			}
		}
		result, err := c.Request(ctx, url, payload, headers)
		if err == nil {
			return result, nil
		}
		lastErr = err
		if !IsRetriableUpstreamError(err) {
			return nil, err
		}
	}
	return nil, lastErr
}

// Close closes the HTTP client
func (c *HTTPClient) Close() error {
	// HTTP client doesn't need explicit closing
	return nil
}
