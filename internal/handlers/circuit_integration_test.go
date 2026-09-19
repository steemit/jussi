package handlers

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/steemit/jussi/internal/config"
	jussiErrors "github.com/steemit/jussi/internal/errors"
	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/upstream"
	"github.com/steemit/jussi/internal/urn"
)

// circuitIntegrationEnv wires a RequestProcessor against an
// httptest upstream whose responses are controlled by the caller.
type circuitIntegrationEnv struct {
	processor *RequestProcessor
	upstream  *httptest.Server
	// hits counts every request that actually reached the upstream.
	hits *atomic.Int64
	// mode is read by the upstream handler each request: "ok" returns
	// a valid JSON-RPC result, "fail" returns a 500.
	mode *atomic.Value
}

func newCircuitEnv(t *testing.T) *circuitIntegrationEnv {
	t.Helper()
	hits := &atomic.Int64{}
	mode := &atomic.Value{}
	mode.Store("ok")

	upstreamServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits.Add(1)
		if mode.Load().(string) == "fail" {
			w.WriteHeader(http.StatusInternalServerError)
			_, _ = w.Write([]byte(`{"jsonrpc":"2.0","error":{"code":-32000,"message":"boom"},"id":1}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"jsonrpc":"2.0","result":{"ok":true},"id":1}`))
	}))
	t.Cleanup(upstreamServer.Close)

	rawCfg := &config.UpstreamRawConfig{
		Upstreams: []config.UpstreamDefinition{
			{
				Name: "appbase",
				URLs: [][]interface{}{
					{"appbase", upstreamServer.URL},
				},
				TTLs:     [][]interface{}{{"appbase", -1}}, // -1 = no caching
				Timeouts: [][]interface{}{{"appbase", 2}},
			},
		},
	}
	router, err := upstream.NewRouter(rawCfg)
	if err != nil {
		t.Fatalf("NewRouter failed: %v", err)
	}

	// Fast breaker tuning so the test does not need real time windows.
	circuitCfg := config.CircuitConfig{
		Enabled:        true,
		Window:         2,
		FailureRate:    0.5,
		MinSamples:     4,
		OpenDuration:   1,
		JitterFraction: 0,
	}

	processor := NewRequestProcessor(nil, router, upstream.NewHTTPClient(), nil, circuitCfg)
	return &circuitIntegrationEnv{
		processor: processor,
		upstream:  upstreamServer,
		hits:      hits,
		mode:      mode,
	}
}

func (e *circuitIntegrationEnv) call(t *testing.T) (map[string]interface{}, error) {
	t.Helper()
	req := &request.JSONRPCRequest{
		URN: &urn.URN{Namespace: "appbase", API: "condenser_api", Method: "get_block"},
	}
	return e.processor.ProcessSingleRequest(context.Background(), req)
}

func errorText(t *testing.T, resp map[string]interface{}) string {
	t.Helper()
	if resp == nil {
		return ""
	}
	e, ok := resp["error"].(map[string]interface{})
	if !ok {
		t.Fatalf("no error object in response: %v", resp)
	}
	msg, _ := e["message"].(string)
	return msg
}

// TestCircuitIntegration_TripsAndStopsHittingUpstream verifies the
// core promise: once the failure window trips the breaker, requests
// fail fast and STOP arriving at the upstream.
func TestCircuitIntegration_TripsAndStopsHittingUpstream(t *testing.T) {
	env := newCircuitEnv(t)
	env.mode.Store("fail")

	// Drive failures until the breaker opens. MinSamples=4, rate=0.5:
	// each call records 1-2 upstream attempts (retry), so the window
	// fills within a handful of calls. While the breaker is closed,
	// upstream 5xx failures surface as wrapped transport errors (err);
	// once open, rejections surface as the typed circuit-open error in
	// the error return.
	tripped := false
	for i := 0; i < 30; i++ {
		resp, err := env.call(t)
		if isCircuitOpen(t, err, resp) {
			tripped = true
			break
		}
	}
	if !tripped {
		t.Fatal("breaker never tripped after 30 failing calls")
	}

	hitsWhileOpenStart := env.hits.Load()

	// While open, calls must be rejected locally: the upstream hit
	// counter must not move.
	for i := 0; i < 10; i++ {
		resp, err := env.call(t)
		if !isCircuitOpen(t, err, resp) {
			t.Fatalf("call %d while open was not rejected: err=%v resp=%v", i, err, resp)
		}
	}
	if got := env.hits.Load(); got != hitsWhileOpenStart {
		t.Fatalf("upstream received %d extra requests while breaker open, want 0", got-hitsWhileOpenStart)
	}
}

// TestCircuitIntegration_RecoversViaProbe verifies the recovery path:
// after the open period, a single probe reaches the upstream, and a
// successful probe closes the breaker so normal traffic resumes.
func TestCircuitIntegration_RecoversViaProbe(t *testing.T) {
	env := newCircuitEnv(t)

	// Trip the breaker.
	env.mode.Store("fail")
	tripped := false
	for i := 0; i < 30; i++ {
		resp, err := env.call(t)
		if isCircuitOpen(t, err, resp) {
			tripped = true
			break
		}
	}
	if !tripped {
		t.Fatal("breaker never tripped")
	}

	// Heal the upstream BEFORE the open period ends.
	env.mode.Store("ok")

	// Wait out the open period (1s + jitter up to 25%) so the breaker
	// is ready to admit the probe.
	time.Sleep(1400 * time.Millisecond)

	// The next call is the probe: it must reach the upstream and
	// succeed, closing the breaker for subsequent traffic.
	resp, err := env.call(t)
	if err != nil {
		t.Fatalf("probe call failed: %v", err)
	}
	if errMsg := errText(t, resp); errMsg != "" {
		t.Fatalf("probe returned error after upstream healed: %v", resp)
	}
	result, _ := resp["result"].(map[string]interface{})
	if result == nil || result["ok"] != true {
		t.Fatalf("probe response missing result: %v", resp)
	}

	// Normal traffic resumed: another plain success, no rejections.
	for i := 0; i < 3; i++ {
		resp, _ := env.call(t)
		if msg := errText(t, resp); msg != "" {
			t.Fatalf("post-recovery call %d failed: %v", i, resp)
		}
	}
}

// TestCircuitIntegration_ClientSeesStructuredError verifies the error
// envelope: a breaker rejection surfaces as the structured
// "Upstream temporarily unavailable" JSON-RPC error (code 1100 class),
// not a generic Internal error — and the internal detail text does not
// leak to the client.
func TestCircuitIntegration_ClientSeesStructuredError(t *testing.T) {
	env := newCircuitEnv(t)
	env.mode.Store("fail")

	tripped := false
	var lastResp map[string]interface{}
	var lastErr error
	for i := 0; i < 30; i++ {
		lastResp, lastErr = env.call(t)
		if isCircuitOpen(t, lastErr, lastResp) {
			tripped = true
			break
		}
	}
	if !tripped {
		t.Fatal("breaker never tripped")
	}

	// The typed error must carry the client-safe message; the internal
	// detail text stays in data.details.
	var jerr *jussiErrors.JSONRPCError
	if !errors.As(lastErr, &jerr) {
		t.Fatalf("rejection not a *JSONRPCError: err=%v resp=%v", lastErr, lastResp)
	}
	if jerr.Message != "Upstream temporarily unavailable" {
		t.Fatalf("unexpected message: %v", jerr.Message)
	}
	if detail, _ := jerr.Data["details"].(string); detail == "" {
		t.Fatalf("expected data.details with breaker context: %v", jerr.Data)
	}
}

// TestCircuitIntegration_DisabledIsPassThrough verifies the
// upstream.circuit.enabled=false kill switch: failures never trip
// anything and traffic keeps flowing to the (broken) upstream.
func TestCircuitIntegration_DisabledIsPassThrough(t *testing.T) {
	env := newCircuitEnv(t)
	// Rebuild the processor with the breaker disabled.
	rawCfg := &config.UpstreamRawConfig{
		Upstreams: []config.UpstreamDefinition{
			{
				Name: "appbase",
				URLs: [][]interface{}{{"appbase", env.upstream.URL}},
				TTLs: [][]interface{}{{"appbase", -1}},
			},
		},
	}
	router, err := upstream.NewRouter(rawCfg)
	if err != nil {
		t.Fatalf("NewRouter failed: %v", err)
	}
	env.processor = NewRequestProcessor(nil, router, upstream.NewHTTPClient(), nil, config.CircuitConfig{Enabled: false})

	env.mode.Store("fail")
	for i := 0; i < 12; i++ {
		resp, _ := env.call(t)
		if msg := errText(t, resp); msg == "Upstream temporarily unavailable" {
			t.Fatalf("call %d rejected while breaker disabled", i)
		}
	}
	if env.hits.Load() == 0 {
		t.Fatal("disabled breaker must not intercept traffic")
	}
}

func errText(t *testing.T, resp map[string]interface{}) string {
	t.Helper()
	if resp == nil {
		return ""
	}
	e, ok := resp["error"].(map[string]interface{})
	if !ok {
		return ""
	}
	msg, _ := e["message"].(string)
	return msg
}

// isCircuitOpen reports whether a ProcessSingleRequest outcome is a
// breaker rejection. The rejection is a typed *JSONRPCError that
// arrives either as the returned error (wrapped by fmt.Errorf in
// ProcessSingleRequest) or — through the HandleError path in
// production — inside the response envelope.
func isCircuitOpen(t *testing.T, err error, resp map[string]interface{}) bool {
	t.Helper()
	var jerr *jussiErrors.JSONRPCError
	if err != nil && errors.As(err, &jerr) {
		return jerr.Message == "Upstream temporarily unavailable"
	}
	return errText(t, resp) == "Upstream temporarily unavailable"
}

func contains(haystack, needle string) bool {
	return len(needle) > 0 && len(haystack) >= len(needle) && indexOf(haystack, needle) >= 0
}

func indexOf(haystack, needle string) int {
	for i := 0; i+len(needle) <= len(haystack); i++ {
		if haystack[i:i+len(needle)] == needle {
			return i
		}
	}
	return -1
}

// TestCircuitIntegration_RejectionCarriesNoUpstreamURL guards the
// topology leak: the client-facing circuit-open error must not embed
// the upstream URL. The upstream identity lives in the metric label and
// the server-side warn log only.
func TestCircuitIntegration_RejectionCarriesNoUpstreamURL(t *testing.T) {
	env := newCircuitEnv(t)
	env.mode.Store("fail")

	var rejection *jussiErrors.JSONRPCError
	for i := 0; i < 30 && rejection == nil; i++ {
		_, err := env.call(t)
		var jerr *jussiErrors.JSONRPCError
		if errors.As(err, &jerr) && jerr.Message == "Upstream temporarily unavailable" {
			rejection = jerr
		}
	}
	if rejection == nil {
		t.Fatal("breaker never tripped after 30 failing calls")
	}

	rendered := fmt.Sprintf("%v", rejection.Data)
	if strings.Contains(rendered, env.upstream.URL) || strings.Contains(rendered, "://") {
		t.Fatalf("circuit-open error leaks the upstream URL: %s", rendered)
	}
}
