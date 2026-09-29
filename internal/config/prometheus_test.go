package config

import "testing"

// The /metrics allowlist must be settable from the environment: deployments
// configure JUSSI_* env vars, not config keys, and before this mapping the
// variable was silently ignored (leaving the endpoint unrestricted whenever
// localhost_only was false).
func TestPrometheusAllowedIPsFromEnv(t *testing.T) {
	t.Setenv("JUSSI_UPSTREAM_CONFIG_FILE", "../../tests/data/configs/TEST_UPSTREAM_CONFIG.json")
	t.Setenv("JUSSI_PROMETHEUS_ALLOWED_IPS", "10.123.2.0/23, 10.123.4.0/23,")

	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig failed: %v", err)
	}

	got := cfg.Prometheus.AllowedIPs
	if len(got) != 2 || got[0] != "10.123.2.0/23" || got[1] != "10.123.4.0/23" {
		t.Fatalf("AllowedIPs = %#v, want the two CIDRs (split on comma, whitespace trimmed, empties dropped)", got)
	}
}

func TestPrometheusAllowedIPsEmptyByDefault(t *testing.T) {
	t.Setenv("JUSSI_UPSTREAM_CONFIG_FILE", "../../tests/data/configs/TEST_UPSTREAM_CONFIG.json")
	t.Setenv("JUSSI_PROMETHEUS_ALLOWED_IPS", "")

	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig failed: %v", err)
	}

	if len(cfg.Prometheus.AllowedIPs) != 0 {
		t.Fatalf("AllowedIPs = %#v, want empty (no allowlist configured)", cfg.Prometheus.AllowedIPs)
	}
}
