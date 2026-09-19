package config

import (
	"testing"
)

// TestCircuitDefaults verifies the built-in breaker defaults.
func TestCircuitDefaults(t *testing.T) {
	t.Setenv("JUSSI_UPSTREAM_CONFIG_FILE", "../../tests/data/configs/TEST_UPSTREAM_CONFIG.json")
	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig failed: %v", err)
	}
	c := cfg.Upstream.Circuit
	if !c.Enabled {
		t.Errorf("Enabled = false, want true (default)")
	}
	if c.Window != 30 {
		t.Errorf("Window = %d, want 30", c.Window)
	}
	if c.FailureRate != 0.5 {
		t.Errorf("FailureRate = %v, want 0.5", c.FailureRate)
	}
	if c.MinSamples != 20 {
		t.Errorf("MinSamples = %d, want 20", c.MinSamples)
	}
	if c.OpenDuration != 10 {
		t.Errorf("OpenDuration = %d, want 10", c.OpenDuration)
	}
	if c.JitterFraction != 0.25 {
		t.Errorf("JitterFraction = %v, want 0.25", c.JitterFraction)
	}
}

// TestCircuitEnvOverride verifies the JUSSI_UPSTREAM_CIRCUIT_* env vars
// actually reach the config struct through the LoadConfig path.
func TestCircuitEnvOverride(t *testing.T) {
	t.Setenv("JUSSI_UPSTREAM_CONFIG_FILE", "../../tests/data/configs/TEST_UPSTREAM_CONFIG.json")
	t.Setenv("JUSSI_UPSTREAM_CIRCUIT_ENABLED", "false")
	t.Setenv("JUSSI_UPSTREAM_CIRCUIT_WINDOW_SECONDS", "60")
	t.Setenv("JUSSI_UPSTREAM_CIRCUIT_FAILURE_RATE", "0.7")
	t.Setenv("JUSSI_UPSTREAM_CIRCUIT_MIN_SAMPLES", "50")
	t.Setenv("JUSSI_UPSTREAM_CIRCUIT_OPEN_DURATION_SECONDS", "25")
	t.Setenv("JUSSI_UPSTREAM_CIRCUIT_JITTER_FRACTION", "0.1")

	cfg, err := LoadConfig()
	if err != nil {
		t.Fatalf("LoadConfig failed: %v", err)
	}
	c := cfg.Upstream.Circuit
	if c.Enabled {
		t.Errorf("Enabled = true, want false from env override")
	}
	if c.Window != 60 {
		t.Errorf("Window = %d, want 60", c.Window)
	}
	if c.FailureRate != 0.7 {
		t.Errorf("FailureRate = %v, want 0.7", c.FailureRate)
	}
	if c.MinSamples != 50 {
		t.Errorf("MinSamples = %d, want 50", c.MinSamples)
	}
	if c.OpenDuration != 25 {
		t.Errorf("OpenDuration = %d, want 25", c.OpenDuration)
	}
	if c.JitterFraction != 0.1 {
		t.Errorf("JitterFraction = %v, want 0.1", c.JitterFraction)
	}
}
