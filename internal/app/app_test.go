package app

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/steemit/jussi/internal/config"
)

// The build fingerprint only reaches /metrics if SetupRouter publishes it.
// The unit test of telemetry.SetBuildInfo cannot catch a dropped call here,
// so this pins the wiring end to end: config → app → route → payload.
func TestSetupRouterPublishesBuildInfo(t *testing.T) {
	t.Setenv("JUSSI_UPSTREAM_CONFIG_FILE", "../../tests/data/configs/TEST_UPSTREAM_CONFIG.json")
	t.Setenv("JUSSI_PROMETHEUS_ENABLED", "true")
	t.Setenv("JUSSI_PROMETHEUS_LOCALHOST_ONLY", "true")
	t.Setenv("SOURCE_COMMIT", "deadbee")
	t.Setenv("DOCKER_TAG", "next-deadbee")

	cfg, err := config.LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig failed: %v", err)
	}

	application, err := NewApp(cfg)
	if err != nil {
		t.Fatalf("NewApp failed: %v", err)
	}

	router, err := application.SetupRouter()
	if err != nil {
		t.Fatalf("SetupRouter failed: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/metrics", nil)
	req.RemoteAddr = "127.0.0.1:12345" // pass the localhost-only gate
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("GET /metrics = %d, want 200: %s", w.Code, w.Body.String())
	}

	want := `jussi_build_info{commit="deadbee",tag="next-deadbee"} 1`
	if !strings.Contains(w.Body.String(), want) {
		t.Fatalf("metrics body is missing %q", want)
	}
}

// A build that never received the CI build args falls back to the literal
// "unknown" in both /health and the metric. Nothing is redacted any more, so
// that literal now has exactly one meaning: the image carries no metadata
// (see the decision record in handlers.HealthHandler.versionInfo).
func TestSetupRouterBuildMetadataFallback(t *testing.T) {
	t.Setenv("JUSSI_UPSTREAM_CONFIG_FILE", "../../tests/data/configs/TEST_UPSTREAM_CONFIG.json")
	t.Setenv("JUSSI_PROMETHEUS_ENABLED", "true")
	t.Setenv("JUSSI_PROMETHEUS_LOCALHOST_ONLY", "true")
	t.Setenv("SOURCE_COMMIT", "")
	t.Setenv("DOCKER_TAG", "")

	cfg, err := config.LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig failed: %v", err)
	}
	application, err := NewApp(cfg)
	if err != nil {
		t.Fatalf("NewApp failed: %v", err)
	}
	router, err := application.SetupRouter()
	if err != nil {
		t.Fatalf("SetupRouter failed: %v", err)
	}

	get := func(path string) string {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		req.RemoteAddr = "127.0.0.1:12345"
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("GET %s = %d, want 200", path, w.Code)
		}
		return w.Body.String()
	}

	health := get("/health")
	for _, want := range []string{`"source_commit":"unknown"`, `"docker_tag":"unknown"`} {
		if !strings.Contains(health, want) {
			t.Fatalf("/health is missing %s: %s", want, health)
		}
	}
	if want := `jussi_build_info{commit="unknown",tag="unknown"} 1`; !strings.Contains(get("/metrics"), want) {
		t.Fatalf("/metrics is missing %q", want)
	}
}

// An empty allowlist is NOT a restriction: with localhost_only=false and no
// allowed_ips the app mounts no middleware at all, so the endpoint stays
// open (network controls have to cover it). Asserted here because the two
// knobs are easy to misread as "deny by default".
func TestSetupRouterMetricsOpenWhenNoAccessKnobIsSet(t *testing.T) {
	t.Setenv("JUSSI_UPSTREAM_CONFIG_FILE", "../../tests/data/configs/TEST_UPSTREAM_CONFIG.json")
	t.Setenv("JUSSI_PROMETHEUS_ENABLED", "true")
	t.Setenv("JUSSI_PROMETHEUS_LOCALHOST_ONLY", "false")
	t.Setenv("JUSSI_PROMETHEUS_ALLOWED_IPS", "")

	cfg, err := config.LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig failed: %v", err)
	}

	application, err := NewApp(cfg)
	if err != nil {
		t.Fatalf("NewApp failed: %v", err)
	}

	router, err := application.SetupRouter()
	if err != nil {
		t.Fatalf("SetupRouter failed: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/metrics", nil)
	req.RemoteAddr = "203.0.113.7:41234" // not loopback
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("GET /metrics from a non-loopback address = %d, want 200 (no middleware when both knobs are unset)", w.Code)
	}
}

// A non-empty allowlist must actually be enforced.
func TestSetupRouterMetricsAllowlistRejectsOtherClients(t *testing.T) {
	t.Setenv("JUSSI_UPSTREAM_CONFIG_FILE", "../../tests/data/configs/TEST_UPSTREAM_CONFIG.json")
	t.Setenv("JUSSI_PROMETHEUS_ENABLED", "true")
	t.Setenv("JUSSI_PROMETHEUS_LOCALHOST_ONLY", "false")
	t.Setenv("JUSSI_PROMETHEUS_ALLOWED_IPS", "10.123.2.0/23")

	cfg, err := config.LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig failed: %v", err)
	}

	application, err := NewApp(cfg)
	if err != nil {
		t.Fatalf("NewApp failed: %v", err)
	}

	router, err := application.SetupRouter()
	if err != nil {
		t.Fatalf("SetupRouter failed: %v", err)
	}

	scrape := func(remoteAddr string) int {
		req := httptest.NewRequest(http.MethodGet, "/metrics", nil)
		req.RemoteAddr = remoteAddr
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		return w.Code
	}

	if code := scrape("10.123.3.50:5555"); code != http.StatusOK {
		t.Fatalf("scraper inside the allowlist got %d, want 200", code)
	}
	if code := scrape("203.0.113.7:41234"); code != http.StatusForbidden {
		t.Fatalf("client outside the allowlist got %d, want 403", code)
	}
}
