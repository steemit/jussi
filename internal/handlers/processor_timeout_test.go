package handlers

import (
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
