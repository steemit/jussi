package upstream

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

// newRetryTestClient returns an HTTPClient pointed at the given test
// server URL with retry/backoff tuned to make tests fast.
func newRetryTestClient() *HTTPClient {
	c := NewHTTPClient()
	c.client.Timeout = 2 * time.Second
	return c
}

func TestRequestWithRetrySucceedsAfterTransient500(t *testing.T) {
	var attempts int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := atomic.AddInt32(&attempts, 1)
		if n == 1 {
			w.WriteHeader(http.StatusBadGateway)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"jsonrpc": "2.0", "result": "ok"})
	}))
	defer srv.Close()

	c := newRetryTestClient()
	cfg := RetryConfig{MaxAttempts: 2, InitialBackoff: time.Millisecond, MaxBackoff: time.Millisecond}
	resp, err := c.RequestWithRetry(context.Background(), srv.URL, map[string]interface{}{"x": 1}, nil, cfg)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got := resp["result"]; got != "ok" {
		t.Errorf("got result=%v, want ok", got)
	}
	if got := atomic.LoadInt32(&attempts); got != 2 {
		t.Errorf("attempts=%d, want 2", got)
	}
}

func TestRequestWithRetryStopsOnNonRetriable4xx(t *testing.T) {
	var attempts int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&attempts, 1)
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"error": "bad"})
	}))
	defer srv.Close()

	c := newRetryTestClient()
	cfg := RetryConfig{MaxAttempts: 3, InitialBackoff: time.Millisecond, MaxBackoff: time.Millisecond}
	resp, err := c.RequestWithRetry(context.Background(), srv.URL, map[string]interface{}{"x": 1}, nil, cfg)
	// 4xx is returned as a parsed response (not an error) by HTTPClient.Request
	// because Request only treats >=500 as errors. Either way, no retry.
	_ = err
	_ = resp
	if got := atomic.LoadInt32(&attempts); got != 1 {
		t.Errorf("attempts=%d, want 1 (no retry on 4xx)", got)
	}
}

func TestRequestWithRetryGivesUpAfterMaxAttempts(t *testing.T) {
	var attempts int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&attempts, 1)
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer srv.Close()

	c := newRetryTestClient()
	cfg := RetryConfig{MaxAttempts: 3, InitialBackoff: time.Millisecond, MaxBackoff: time.Millisecond}
	_, err := c.RequestWithRetry(context.Background(), srv.URL, map[string]interface{}{"x": 1}, nil, cfg)
	if err == nil {
		t.Fatal("expected error after maxAttempts exhausted")
	}
	if got := atomic.LoadInt32(&attempts); got != 3 {
		t.Errorf("attempts=%d, want 3", got)
	}
}

func TestRequestWithRetryRespectsContextCancellation(t *testing.T) {
	var attempts int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&attempts, 1)
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer srv.Close()

	c := newRetryTestClient()
	cfg := RetryConfig{MaxAttempts: 5, InitialBackoff: 50 * time.Millisecond, MaxBackoff: 50 * time.Millisecond}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Millisecond)
	defer cancel()
	_, err := c.RequestWithRetry(ctx, srv.URL, map[string]interface{}{"x": 1}, nil, cfg)
	if err == nil {
		t.Fatal("expected context error")
	}
	// We should have stopped well before exhausting MaxAttempts.
	if got := atomic.LoadInt32(&attempts); got >= 5 {
		t.Errorf("attempts=%d, want < 5 (context should stop us)", got)
	}
}
