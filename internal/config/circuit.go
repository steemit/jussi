package config

// CircuitConfig holds the tunable circuit-breaker parameters, exposed
// through the viper tree as upstream.circuit and overridable via
// environment variables (JUSSI_UPSTREAM_CIRCUIT_*, see envBindings in
// config.go). The struct lives in the config package because
// internal/upstream already imports config (router.go); the conversion
// to the breaker's runtime config happens in the handlers package.
type CircuitConfig struct {
	// Enabled turns the breaker into a pass-through when false. Exists
	// so a bad interaction can be switched off in production without a
	// rollback.
	Enabled bool `mapstructure:"enabled"`
	// Window is the sliding failure-rate window, in seconds.
	Window int `mapstructure:"window_seconds"`
	// FailureRate is the failure ratio (0..1) that opens the breaker.
	FailureRate float64 `mapstructure:"failure_rate"`
	// MinSamples is the minimum requests in the window before the rate
	// is evaluated.
	MinSamples int `mapstructure:"min_samples"`
	// OpenDuration is how long the breaker stays open before admitting
	// a probe, in seconds.
	OpenDuration int `mapstructure:"open_duration_seconds"`
	// JitterFraction adds up to (JitterFraction * OpenDuration) of
	// random extra open time to desynchronise jussi instances probing a
	// recovering backend.
	JitterFraction float64 `mapstructure:"jitter_fraction"`
}
