package handlers

import (
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
