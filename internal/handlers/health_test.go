package handlers

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
	"github.com/steemit/jussi/internal/config"
	"github.com/steemit/jussi/internal/upstream"
)

// healthResponse runs HandleHealth against a registry seeded with
// breakers for the given URLs and returns the raw JSON body.
func healthResponse(t *testing.T, aliases map[string]string, urls ...string) string {
	t.Helper()
	gin.SetMode(gin.TestMode)

	reg := upstream.NewRegistry(upstream.DefaultBreakerConfig())
	for _, u := range urls {
		reg.For(u)
	}

	h := NewHealthHandler("c", "t", cache.NewBlockNumberTracker())
	h.Breakers = reg
	h.BreakerNames = aliases

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest(http.MethodGet, "/health", nil)
	h.HandleHealth(c)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	return w.Body.String()
}

func TestBreakerAliases(t *testing.T) {
	raw := &config.UpstreamRawConfig{
		Upstreams: []config.UpstreamDefinition{
			{
				Name: "hivemind",
				URLs: [][]interface{}{
					{"hivemind", "https://hivemind.internal.example"},
				},
			},
			{
				Name: "namespace",
				URLs: [][]interface{}{
					{"namespace", "wss://a.internal.example"},
					{"namespace.method", "wss://b.internal.example"},
					{"prefix", "not-a-url"},
				},
			},
		},
	}

	aliases := BreakerAliases(raw)

	if got := aliases["https://hivemind.internal.example"]; got != "hivemind" {
		t.Errorf("hivemind host aliased to %q", got)
	}
	// Multiple hosts under one name get sorted -2/-3 suffixes.
	if got := aliases["wss://a.internal.example"]; got != "namespace" {
		t.Errorf("first namespace host aliased to %q", got)
	}
	if got := aliases["wss://b.internal.example"]; got != "namespace-2" {
		t.Errorf("second namespace host aliased to %q", got)
	}
	if len(aliases) != 3 {
		t.Errorf("non-URL pairs must be skipped; got %d aliases: %v", len(aliases), aliases)
	}

	if got := BreakerAliases(nil); got != nil {
		t.Errorf("nil config must yield nil aliases, got %v", got)
	}
}

// TestBreakerAliasesPoolEntries mirrors the production config shape: a
// pool-style upstream whose urls array repeats the same few hosts across
// many routing lines (32 rows on 3 hosts), plus single-host entries that
// share hosts with the pool. Duplicate rows must not inflate suffix
// numbers, and the alphabetically-latest name must win a shared host.
func TestBreakerAliasesPoolEntries(t *testing.T) {
	rows := func(prefix, host string, n int) [][]interface{} {
		out := make([][]interface{}, 0, n)
		for i := 0; i < n; i++ {
			out = append(out, []interface{}{fmt.Sprintf("%s.api%d", prefix, i), host})
		}
		return out
	}
	raw := &config.UpstreamRawConfig{
		Upstreams: []config.UpstreamDefinition{
			{
				// prod shape: 32 rows — ahnode x8, hive x23, steemd x1
				Name: "appbase",
				URLs: append(append(
					rows("appbase", "https://ahnode.secret.internal", 8),
					rows("appbase", "https://hive.secret.internal", 23)...),
					[]interface{}{"appbase.condenser_api", "https://steemd.secret.internal"}),
			},
			{
				Name: "hive",
				URLs: [][]interface{}{{"hive", "https://hive.secret.internal"}},
			},
			{
				Name: "steemd",
				URLs: [][]interface{}{{"steemd", "https://steemd.secret.internal"}},
			},
			{
				// prod shape: the same host listed 3x under its own name
				Name: "conveyor",
				URLs: rows("conveyor", "https://conveyor.secret.internal", 3),
			},
		},
	}

	aliases := BreakerAliases(raw)

	// Duplicate rows count once: suffixes number UNIQUE hosts.
	if got := aliases["https://ahnode.secret.internal"]; got != "appbase" {
		t.Errorf("pool host ahnode aliased to %q, want appbase (no duplicate inflation)", got)
	}
	// Shared hosts keep the alphabetically-latest name.
	if got := aliases["https://hive.secret.internal"]; got != "hive" {
		t.Errorf("shared hive host aliased to %q, want hive", got)
	}
	if got := aliases["https://steemd.secret.internal"]; got != "steemd" {
		t.Errorf("shared steemd host aliased to %q, want steemd", got)
	}
	if got := aliases["https://conveyor.secret.internal"]; got != "conveyor" {
		t.Errorf("conveyor host aliased to %q, want conveyor (no -3 suffix)", got)
	}
}

// /health is public and CORS-open: circuit states must never carry a
// backend hostname, whether the key is aliased or unknown.
func TestHandleHealthHidesHostnames(t *testing.T) {
	raw := &config.UpstreamRawConfig{
		Upstreams: []config.UpstreamDefinition{
			{
				Name: "hivemind",
				URLs: [][]interface{}{
					{"hivemind", "https://hivemind.secret.internal"},
				},
			},
		},
	}
	aliases := BreakerAliases(raw)

	body := healthResponse(t, aliases,
		"https://hivemind.secret.internal",     // aliased
		"https://unconfigured.secret.internal", // digest fallback
	)

	if strings.Contains(body, "secret.internal") || strings.Contains(body, "://") {
		t.Fatalf("health body leaks a hostname: %s", body)
	}
	if !strings.Contains(body, `"hivemind":"closed"`) {
		t.Fatalf("aliased state missing from body: %s", body)
	}
	if !strings.Contains(body, `"upstream-`) {
		t.Fatalf("unconfigured key must get an opaque digest alias: %s", body)
	}
}
