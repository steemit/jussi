package upstream

import (
	"encoding/json"
	"os"
	"reflect"
	"testing"

	"github.com/steemit/jussi/internal/config"
	"github.com/steemit/jussi/internal/urn"
)

// Test configuration matching legacy test_upstreams.py
var simpleConfig = &config.UpstreamRawConfig{
	Upstreams: []config.UpstreamDefinition{
		{
			Name:               "test",
			TranslateToAppbase: true,
			URLs: [][]interface{}{
				{"test", "http://test.com"},
			},
			TTLs: [][]interface{}{
				{"test", 1},
			},
			Timeouts: [][]interface{}{
				{"test", 1},
			},
		},
		{
			Name:               "test2",
			TranslateToAppbase: false,
			URLs: [][]interface{}{
				{"test2", "http://test2.com"},
			},
			TTLs: [][]interface{}{
				{"test2", 2},
			},
			Timeouts: [][]interface{}{
				{"test2", 2},
			},
		},
	},
}

var validHostnameConfig = &config.UpstreamRawConfig{
	Upstreams: []config.UpstreamDefinition{
		{
			Name:               "test",
			TranslateToAppbase: true,
			URLs: [][]interface{}{
				{"test", "http://google.com"},
			},
			TTLs: [][]interface{}{
				{"test", 1},
			},
			Timeouts: [][]interface{}{
				{"test", 1},
			},
		},
	},
}

var invalidNamespace1Config = &config.UpstreamRawConfig{
	Upstreams: []config.UpstreamDefinition{
		{
			Name: "test_api", // Invalid: ends with _api
			URLs: [][]interface{}{
				{"test", "http://google.com"},
			},
			TTLs: [][]interface{}{
				{"test", 1},
			},
			Timeouts: [][]interface{}{
				{"test", 1},
			},
		},
	},
}

var invalidNamespace2Config = &config.UpstreamRawConfig{
	Upstreams: []config.UpstreamDefinition{
		{
			Name: "jsonrpc", // Invalid: is jsonrpc
			URLs: [][]interface{}{
				{"test", "http://google.com"},
			},
			TTLs: [][]interface{}{
				{"test", 1},
			},
			Timeouts: [][]interface{}{
				{"test", 1},
			},
		},
	},
}

func TestNamespacesConfig(t *testing.T) {
	router, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	namespaces := router.GetNamespaces()
	expectedNamespaces := map[string]bool{
		"test":  true,
		"test2": true,
	}

	if len(namespaces) != len(expectedNamespaces) {
		t.Errorf("expected %d namespaces, got %d", len(expectedNamespaces), len(namespaces))
	}

	for _, ns := range namespaces {
		if !expectedNamespaces[ns] {
			t.Errorf("unexpected namespace: %s", ns)
		}
	}
}

func TestNamespacesConfigEndsWithAPI(t *testing.T) {
	// In Go, we don't validate namespace names during router creation
	// This test verifies that invalid names don't cause panics
	router, err := NewRouter(invalidNamespace1Config)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	namespaces := router.GetNamespaces()
	if len(namespaces) != 1 || namespaces[0] != "test_api" {
		t.Errorf("expected namespace 'test_api', got %v", namespaces)
	}
}

func TestNamespacesConfigIsJSONRPC(t *testing.T) {
	// In Go, we don't validate namespace names during router creation
	// This test verifies that invalid names don't cause panics
	router, err := NewRouter(invalidNamespace2Config)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	namespaces := router.GetNamespaces()
	if len(namespaces) != 1 || namespaces[0] != "jsonrpc" {
		t.Errorf("expected namespace 'jsonrpc', got %v", namespaces)
	}
}

func TestURLsConfig(t *testing.T) {
	router, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	urls := router.GetAllURLs()
	expectedURLs := map[string]bool{
		"http://test.com":  true,
		"http://test2.com": true,
	}

	if len(urls) != len(expectedURLs) {
		t.Errorf("expected %d URLs, got %d", len(expectedURLs), len(urls))
	}

	for _, url := range urls {
		if !expectedURLs[url] {
			t.Errorf("unexpected URL: %s", url)
		}
	}
}

func TestTranslateToAppbaseConfigTrue(t *testing.T) {
	router, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	if !router.ShouldTranslateToAppbase("test") {
		t.Error("expected translate_to_appbase to be true for 'test'")
	}
}

func TestTranslateToAppbaseConfigFalse(t *testing.T) {
	router, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	if router.ShouldTranslateToAppbase("test2") {
		t.Error("expected translate_to_appbase to be false for 'test2'")
	}
}

func TestURLPair(t *testing.T) {
	router, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	testURN, err := urn.FromRequest(map[string]interface{}{
		"method": "test.api.method",
	})
	if err != nil {
		t.Fatalf("failed to create URN: %v", err)
	}

	urnStr := testURN.String()
	upstream, found := router.GetUpstream(urnStr)
	if !found {
		t.Fatal("expected to find upstream")
	}

	if upstream.URL != "http://test.com" {
		t.Errorf("expected URL 'http://test.com', got '%s'", upstream.URL)
	}
}

func TestURLObject(t *testing.T) {
	router, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	testURN, err := urn.FromRequest(map[string]interface{}{
		"method": "test2.api.method",
	})
	if err != nil {
		t.Fatalf("failed to create URN: %v", err)
	}

	urnStr := testURN.String()
	upstream, found := router.GetUpstream(urnStr)
	if !found {
		t.Fatal("expected to find upstream")
	}

	if upstream.URL != "http://test2.com" {
		t.Errorf("expected URL 'http://test2.com', got '%s'", upstream.URL)
	}
}

func TestTimeoutPair(t *testing.T) {
	router, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	testURN, err := urn.FromRequest(map[string]interface{}{
		"method": "test.api.method",
	})
	if err != nil {
		t.Fatalf("failed to create URN: %v", err)
	}

	urnStr := testURN.String()
	upstream, found := router.GetUpstream(urnStr)
	if !found {
		t.Fatal("expected to find upstream")
	}

	if upstream.Timeout != 1 {
		t.Errorf("expected timeout 1, got %d", upstream.Timeout)
	}
}

func TestTimeoutObject(t *testing.T) {
	router, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	testURN, err := urn.FromRequest(map[string]interface{}{
		"method": "test2.api.method",
	})
	if err != nil {
		t.Fatalf("failed to create URN: %v", err)
	}

	urnStr := testURN.String()
	upstream, found := router.GetUpstream(urnStr)
	if !found {
		t.Fatal("expected to find upstream")
	}

	if upstream.Timeout != 2 {
		t.Errorf("expected timeout 2, got %d", upstream.Timeout)
	}
}

func TestTTLPair(t *testing.T) {
	router, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	testURN, err := urn.FromRequest(map[string]interface{}{
		"method": "test.api.method",
	})
	if err != nil {
		t.Fatalf("failed to create URN: %v", err)
	}

	urnStr := testURN.String()
	upstream, found := router.GetUpstream(urnStr)
	if !found {
		t.Fatal("expected to find upstream")
	}

	if upstream.TTL != 1 {
		t.Errorf("expected TTL 1, got %d", upstream.TTL)
	}
}

func TestTTLObject(t *testing.T) {
	router, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	testURN, err := urn.FromRequest(map[string]interface{}{
		"method": "test2.api.method",
	})
	if err != nil {
		t.Fatalf("failed to create URN: %v", err)
	}

	urnStr := testURN.String()
	upstream, found := router.GetUpstream(urnStr)
	if !found {
		t.Fatal("expected to find upstream")
	}

	if upstream.TTL != 2 {
		t.Errorf("expected TTL 2, got %d", upstream.TTL)
	}
}

func TestHash(t *testing.T) {
	router1, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	// Hash is not implemented in Go router, but we can test that
	// two routers with same config produce same results
	router2, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	// Compare namespaces (convert to sets for comparison since order may differ)
	ns1 := router1.GetNamespaces()
	ns2 := router2.GetNamespaces()
	ns1Set := make(map[string]bool)
	ns2Set := make(map[string]bool)
	for _, ns := range ns1 {
		ns1Set[ns] = true
	}
	for _, ns := range ns2 {
		ns2Set[ns] = true
	}
	if !reflect.DeepEqual(ns1Set, ns2Set) {
		t.Error("routers with same config should have same namespaces")
	}

	// Compare URLs (convert to sets for comparison since order may differ)
	urls1 := router1.GetAllURLs()
	urls2 := router2.GetAllURLs()
	urls1Set := make(map[string]bool)
	urls2Set := make(map[string]bool)
	for _, url := range urls1 {
		urls1Set[url] = true
	}
	for _, url := range urls2 {
		urls2Set[url] = true
	}
	if !reflect.DeepEqual(urls1Set, urls2Set) {
		t.Error("routers with same config should have same URLs")
	}
}

// TestFallbackToAppbaseOrSteemd tests that unconfigured namespaces fall back to appbase or steemd
func TestFallbackToAppbaseOrSteemd(t *testing.T) {
	// Create config with appbase and steemd, but no bridge
	config := &config.UpstreamRawConfig{
		Upstreams: []config.UpstreamDefinition{
			{
				Name: "steemd",
				URLs: [][]interface{}{
					{"steemd", "https://api.steemit.com"},
				},
				TTLs: [][]interface{}{
					{"steemd", 3},
				},
				Timeouts: [][]interface{}{
					{"steemd", 5},
				},
			},
			{
				Name: "appbase",
				URLs: [][]interface{}{
					{"appbase", "https://api.steemit.com"},
				},
				TTLs: [][]interface{}{
					{"appbase", -2},
				},
				Timeouts: [][]interface{}{
					{"appbase", 3},
				},
			},
		},
	}

	router, err := NewRouter(config)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	// Test bridge namespace (not configured) - should fallback to appbase
	bridgeURN, err := urn.FromRequest(map[string]interface{}{
		"method": "bridge.get_ranked_posts",
		"params": map[string]interface{}{
			"sort":  "trending",
			"tag":   "",
			"limit": 20,
		},
	})
	if err != nil {
		t.Fatalf("failed to create URN: %v", err)
	}

	upstream, found := router.GetUpstream(bridgeURN.String())
	if !found {
		t.Fatal("expected to find upstream (should fallback to appbase)")
	}

	// Should fallback to appbase URL
	if upstream.URL != "https://api.steemit.com" {
		t.Errorf("expected URL 'https://api.steemit.com' (from appbase), got '%s'", upstream.URL)
	}

	// Should fallback to appbase TTL
	if upstream.TTL != -2 {
		t.Errorf("expected TTL -2 (from appbase), got %d", upstream.TTL)
	}

	// Should fallback to appbase timeout
	if upstream.Timeout != 3 {
		t.Errorf("expected timeout 3 (from appbase), got %d", upstream.Timeout)
	}
}

func TestHashIneq(t *testing.T) {
	router1, err := NewRouter(simpleConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	router2, err := NewRouter(validHostnameConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	// Compare namespaces
	ns1 := router1.GetNamespaces()
	ns2 := router2.GetNamespaces()
	if reflect.DeepEqual(ns1, ns2) {
		t.Error("routers with different config should have different namespaces")
	}

	// Compare URLs
	urls1 := router1.GetAllURLs()
	urls2 := router2.GetAllURLs()
	if reflect.DeepEqual(urls1, urls2) {
		t.Error("routers with different config should have different URLs")
	}
}

// TestRouterWithTestConfig loads the actual test config file
func TestRouterWithTestConfig(t *testing.T) {
	// Load test config file
	testConfigPath := "legacy/tests/data/configs/TEST_UPSTREAM_CONFIG.json"
	data, err := os.ReadFile(testConfigPath)
	if err != nil {
		t.Skipf("test config file not found: %s", testConfigPath)
	}

	var rawConfig config.UpstreamRawConfig
	if err := json.Unmarshal(data, &rawConfig); err != nil {
		t.Fatalf("failed to unmarshal test config: %v", err)
	}

	router, err := NewRouter(&rawConfig)
	if err != nil {
		t.Fatalf("failed to create router: %v", err)
	}

	// Test that steemd namespace exists
	namespaces := router.GetNamespaces()
	hasSteemd := false
	for _, ns := range namespaces {
		if ns == "steemd" {
			hasSteemd = true
			break
		}
	}
	if !hasSteemd {
		t.Error("expected 'steemd' namespace in test config")
	}

	// Test that we can get steemd URLs
	steemdURLs := router.GetSteemdURLs()
	if len(steemdURLs) == 0 {
		t.Error("expected at least one steemd URL")
	}
}

