package handlers

import (
	"time"

	"github.com/steemit/jussi/internal/config"
	"github.com/steemit/jussi/internal/upstream"
)

// breakerConfig converts the viper-facing config.CircuitConfig into the
// breaker's runtime config, falling back to the tuned defaults for any
// unset value. Lives here (not in config) to keep the config package
// free of upstream internals.
func breakerConfig(cfg config.CircuitConfig) upstream.BreakerConfig {
	out := upstream.DefaultBreakerConfig()
	if cfg.Window > 0 {
		out.Window = time.Duration(cfg.Window) * time.Second
	}
	if cfg.FailureRate > 0 {
		out.FailureRate = cfg.FailureRate
	}
	if cfg.MinSamples > 0 {
		out.MinSamples = cfg.MinSamples
	}
	if cfg.OpenDuration > 0 {
		out.OpenDuration = time.Duration(cfg.OpenDuration) * time.Second
	}
	if cfg.JitterFraction > 0 {
		out.JitterFraction = cfg.JitterFraction
	}
	return out
}
