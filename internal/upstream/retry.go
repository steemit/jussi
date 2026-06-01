package upstream

import (
	"context"
	"errors"
	"io"
	"math/rand"
	"net"
	"strings"
	"time"
)

// RetryConfig configures bounded-attempt retry for idempotent upstream
// requests. Non-idempotent paths (notably broadcast_transaction*) must
// NOT use retry — see handlers.RequestProcessor.callHTTPUpstream.
type RetryConfig struct {
	// MaxAttempts is the total number of attempts including the first
	// (so MaxAttempts=2 means up to 1 retry after the original failure).
	// Values < 1 are treated as 1 (no retry).
	MaxAttempts int

	// InitialBackoff is the sleep before the first retry. Subsequent
	// retries double up to MaxBackoff.
	InitialBackoff time.Duration

	// MaxBackoff caps the per-attempt sleep.
	MaxBackoff time.Duration

	// JitterFraction adds up to (JitterFraction * backoff) of random
	// extra sleep to avoid thundering-herd on transient upstream blips.
	JitterFraction float64
}

// DefaultRetryConfig is intentionally tighter than legacy jussi's
// (3 retries / multi-second backoff) so the worst-case retry budget
// stays well under typical wallet timeouts.
func DefaultRetryConfig() RetryConfig {
	return RetryConfig{
		MaxAttempts:    2,
		InitialBackoff: 100 * time.Millisecond,
		MaxBackoff:     500 * time.Millisecond,
		JitterFraction: 0.25,
	}
}

// IsRetriableUpstreamError reports whether an error from HTTPClient.Request
// indicates a transient transport-layer or upstream-side failure that
// is safe to retry for an idempotent request.
//
// We deliberately do NOT retry on context cancellation or deadline:
// the caller's budget is gone; another attempt cannot succeed within it
// and just burns context for nothing.
func IsRetriableUpstreamError(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
		return false
	}
	if errors.Is(err, io.EOF) || errors.Is(err, io.ErrUnexpectedEOF) {
		return true
	}
	var netErr net.Error
	if errors.As(err, &netErr) && netErr.Timeout() {
		return true
	}
	// Match UpstreamStatusError via types — avoids fragile string matching.
	var statusErr *UpstreamStatusError
	if errors.As(err, &statusErr) {
		return statusErr.StatusCode >= 500 && statusErr.StatusCode < 600
	}
	msg := err.Error()
	for _, s := range []string{
		"connection reset",
		"connection refused",
		"broken pipe",
		"no such host",
		"i/o timeout",
		"network is unreachable",
	} {
		if strings.Contains(msg, s) {
			return true
		}
	}
	return false
}

// BackoffFor returns the sleep duration before the n-th retry (1-based).
// Capped at MaxBackoff; adds up to JitterFraction * backoff jitter.
func (c RetryConfig) BackoffFor(retryNum int) time.Duration {
	if retryNum < 1 {
		retryNum = 1
	}
	base := c.InitialBackoff
	for i := 1; i < retryNum; i++ {
		base *= 2
		if base > c.MaxBackoff || base < 0 {
			base = c.MaxBackoff
			break
		}
	}
	if base > c.MaxBackoff {
		base = c.MaxBackoff
	}
	if c.JitterFraction <= 0 {
		return base
	}
	jitter := time.Duration(float64(base) * c.JitterFraction * rand.Float64())
	return base + jitter
}
