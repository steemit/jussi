package upstream

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"testing"
	"time"
)

type fakeTimeoutErr struct{}

func (fakeTimeoutErr) Error() string   { return "fake timeout" }
func (fakeTimeoutErr) Timeout() bool   { return true }
func (fakeTimeoutErr) Temporary() bool { return true }

var _ net.Error = fakeTimeoutErr{}

func TestIsRetriableUpstreamError(t *testing.T) {
	tests := []struct {
		name string
		err  error
		want bool
	}{
		{"nil", nil, false},
		{"context canceled", context.Canceled, false},
		{"context deadline exceeded", context.DeadlineExceeded, false},
		{"io.EOF bare", io.EOF, true},
		{"io.EOF wrapped", fmt.Errorf("upstream request failed: %w", io.EOF), true},
		{"io.ErrUnexpectedEOF", io.ErrUnexpectedEOF, true},
		{"net timeout", fakeTimeoutErr{}, true},
		{"connection reset string", errors.New("read tcp: connection reset by peer"), true},
		{"connection refused string", errors.New("dial tcp: connection refused"), true},
		{"i/o timeout string", errors.New("Get url: net/http: i/o timeout"), true},
		{"no such host string", errors.New("dial: no such host"), true},
		{"server error 500", errors.New("upstream server error: 500"), true},
		{"server error 502", errors.New("upstream server error: 502"), true},
		{"server error 503", errors.New("upstream server error: 503"), true},
		{"server error 504", errors.New("upstream server error: 504"), true},
		{"server error 4xx not retried", errors.New("upstream server error: 401"), false},
		{"context deadline wrapped not retried", fmt.Errorf("upstream request failed: %w", context.DeadlineExceeded), false},
		{"unknown error not retried", errors.New("parse error: unexpected character"), false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := IsRetriableUpstreamError(tt.err)
			if got != tt.want {
				t.Errorf("IsRetriableUpstreamError(%q) = %v, want %v", tt.err, got, tt.want)
			}
		})
	}
}

func TestRetryConfigBackoffExponentialCapped(t *testing.T) {
	cfg := RetryConfig{
		MaxAttempts:    5,
		InitialBackoff: 100 * time.Millisecond,
		MaxBackoff:     500 * time.Millisecond,
		JitterFraction: 0, // deterministic
	}
	tests := []struct {
		retryNum int
		want     time.Duration
	}{
		{1, 100 * time.Millisecond},
		{2, 200 * time.Millisecond},
		{3, 400 * time.Millisecond},
		{4, 500 * time.Millisecond},
		{5, 500 * time.Millisecond},
		{10, 500 * time.Millisecond},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("retry%d", tt.retryNum), func(t *testing.T) {
			got := cfg.BackoffFor(tt.retryNum)
			if got != tt.want {
				t.Errorf("BackoffFor(%d) = %v, want %v", tt.retryNum, got, tt.want)
			}
		})
	}
}

func TestRetryConfigBackoffJitterBoundedAndPositive(t *testing.T) {
	cfg := RetryConfig{
		MaxAttempts:    3,
		InitialBackoff: 100 * time.Millisecond,
		MaxBackoff:     500 * time.Millisecond,
		JitterFraction: 0.25,
	}
	for range 32 {
		got := cfg.BackoffFor(1)
		if got < 100*time.Millisecond || got > 125*time.Millisecond {
			t.Errorf("BackoffFor(1) with jitter = %v, want in [100ms, 125ms]", got)
		}
	}
}

func TestDefaultRetryConfigSafe(t *testing.T) {
	cfg := DefaultRetryConfig()
	if cfg.MaxAttempts < 1 {
		t.Errorf("MaxAttempts must be >= 1, got %d", cfg.MaxAttempts)
	}
	if cfg.MaxAttempts > 3 {
		t.Errorf("MaxAttempts=%d is too aggressive; legacy 3-retry pattern caused expiration-on-retry (see commit 9cf36ea)", cfg.MaxAttempts)
	}
	worstCase := cfg.InitialBackoff
	for i := 2; i <= cfg.MaxAttempts; i++ {
		worstCase += cfg.BackoffFor(i)
	}
	if worstCase > 2*time.Second {
		t.Errorf("worst-case retry budget %v exceeds 2s; risks pushing into wallet timeout", worstCase)
	}
}
