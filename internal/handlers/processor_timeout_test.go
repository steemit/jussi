package handlers

import (
	"sync"
	"testing"
	"time"

	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/urn"
)

func TestSelectUpstreamTimeout(t *testing.T) {
	mkReq := func(method string, cfgTimeoutSec int) *request.JSONRPCRequest {
		return &request.JSONRPCRequest{
			URN: &urn.URN{
				Namespace: "appbase",
				API:       "condenser_api",
				Method:    method,
			},
			Upstream: &request.UpstreamConfig{
				Timeout: cfgTimeoutSec,
			},
		}
	}

	tests := []struct {
		name string
		req  *request.JSONRPCRequest
		want time.Duration
	}{
		{
			name: "non-broadcast with explicit 5s uses configured value",
			req:  mkReq("get_block", 5),
			want: 5 * time.Second,
		},
		{
			name: "non-broadcast with 0 falls back to default",
			req:  mkReq("get_block", 0),
			want: defaultUpstreamTimeout,
		},
		{
			name: "broadcast_transaction_synchronous with 0 raised to broadcast minimum",
			req:  mkReq("broadcast_transaction_synchronous", 0),
			want: broadcastMinimumTimeout,
		},
		{
			name: "broadcast_transaction with 0 raised to broadcast minimum",
			req:  mkReq("broadcast_transaction", 0),
			want: broadcastMinimumTimeout,
		},
		{
			name: "broadcast with sub-minimum configured value raised to broadcast minimum",
			req:  mkReq("broadcast_transaction_synchronous", 3),
			want: broadcastMinimumTimeout,
		},
		{
			name: "broadcast with above-minimum configured value preserved",
			req:  mkReq("broadcast_transaction_synchronous", 60),
			want: 60 * time.Second,
		},
		{
			name: "broadcast with configured value equal to minimum preserved",
			req:  mkReq("broadcast_transaction_synchronous", 30),
			want: broadcastMinimumTimeout,
		},
		{
			name: "broadcast with previous-15s config raised to new 30s minimum",
			req:  mkReq("broadcast_transaction_synchronous", 15),
			want: broadcastMinimumTimeout,
		},
		{
			name: "broadcast_block is detected as broadcast method",
			req:  mkReq("broadcast_block", 0),
			want: broadcastMinimumTimeout,
		},
		{
			name: "nil request falls back to default",
			req:  nil,
			want: defaultUpstreamTimeout,
		},
		{
			name: "request with nil URN falls back to default",
			req:  &request.JSONRPCRequest{Upstream: &request.UpstreamConfig{Timeout: 0}},
			want: defaultUpstreamTimeout,
		},
		{
			name: "request with nil Upstream falls back to default",
			req:  &request.JSONRPCRequest{URN: &urn.URN{Namespace: "appbase", Method: "get_block"}, Upstream: nil},
			want: defaultUpstreamTimeout,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := selectUpstreamTimeout(tt.req)
			if got != tt.want {
				t.Errorf("selectUpstreamTimeout = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestSelectUpstreamTimeoutSafetyConstants(t *testing.T) {
	// Both constants must cover at least one Steem block (~3s) plus network
	// and confirmation overhead. The production upstream config sets
	// broadcast timeouts to 15s; keeping the safety net at the same value
	// avoids surprise regressions when config and code drift.
	const blockPlusHeadroom = 10 * time.Second
	if defaultUpstreamTimeout < blockPlusHeadroom {
		t.Errorf("defaultUpstreamTimeout=%v is too small; must cover at least one block (~3s) plus headroom", defaultUpstreamTimeout)
	}
	if broadcastMinimumTimeout < blockPlusHeadroom {
		t.Errorf("broadcastMinimumTimeout=%v is too small; must cover at least one block (~3s) plus headroom", broadcastMinimumTimeout)
	}
}

func TestShouldLogBroadcastFloor(t *testing.T) {
	// Reset state before test
	broadcastFloorLastLog.Clear()

	// First call should always log.
	if !shouldLogBroadcastFloor("broadcast_transaction") {
		t.Error("first call should return true")
	}
	// Immediate second call should be suppressed.
	if shouldLogBroadcastFloor("broadcast_transaction") {
		t.Error("second call within interval should return false")
	}
	// Different method should log independently.
	if !shouldLogBroadcastFloor("broadcast_transaction_synchronous") {
		t.Error("different method should log independently")
	}
}

func TestShouldLogBroadcastFloorConcurrent(t *testing.T) {
	// Reset state
	broadcastFloorLastLog.Clear()

	// Hammer the same method from multiple goroutines.
	// With LoadOrStore, at most one goroutine gets true on the first
	// wave; the rest should see false.
	const goroutines = 32
	results := make([]bool, goroutines)
	var wg sync.WaitGroup
	wg.Add(goroutines)
	for i := 0; i < goroutines; i++ {
		go func(idx int) {
			defer wg.Done()
			results[idx] = shouldLogBroadcastFloor("concurrent_method")
		}(i)
	}
	wg.Wait()

	trueCount := 0
	for _, r := range results {
		if r {
			trueCount++
		}
	}
	if trueCount == 0 {
		t.Error("expected at least one goroutine to log")
	}
	if trueCount > 3 {
		t.Errorf("expected at most 3 true results under contention (got %d); LoadOrStore should suppress most duplicates", trueCount)
	}
}
