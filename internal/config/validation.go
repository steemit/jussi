package config

import (
	"fmt"
	"net/url"
	"strings"
)

// ValidateConfig validates the configuration
func ValidateConfig(cfg *Config) error {
	// Validate server configuration
	if cfg.Server.Port <= 0 || cfg.Server.Port > 65535 {
		return fmt.Errorf("invalid server port: %d", cfg.Server.Port)
	}

	if cfg.Server.Host == "" {
		return fmt.Errorf("server host cannot be empty")
	}

	if cfg.Server.BatchSizeLimit <= 0 {
		return fmt.Errorf("jsonrpc batch size limit must be positive")
	}

	// Validate logging configuration
	validLogLevels := map[string]bool{
		"debug": true,
		"info":  true,
		"warn":  true,
		"error": true,
	}
	if !validLogLevels[strings.ToLower(cfg.Logging.Level)] {
		return fmt.Errorf("invalid log level: %s", cfg.Logging.Level)
	}

	validLogFormats := map[string]bool{
		"json": true,
		"text": true,
	}
	if !validLogFormats[strings.ToLower(cfg.Logging.Format)] {
		return fmt.Errorf("invalid log format: %s", cfg.Logging.Format)
	}

	// Validate OpenTelemetry configuration
	if cfg.Telemetry.ServiceName == "" {
		return fmt.Errorf("otel service name cannot be empty")
	}

	if cfg.Telemetry.TracesEndpoint != "" {
		if _, err := url.Parse(cfg.Telemetry.TracesEndpoint); err != nil {
			return fmt.Errorf("invalid otel collector endpoint: %w", err)
		}
	}

	// Validate Prometheus configuration
	if cfg.Prometheus.Enabled {
		if cfg.Prometheus.Path == "" {
			return fmt.Errorf("prometheus path cannot be empty when enabled")
		}
		if cfg.Prometheus.Port <= 0 || cfg.Prometheus.Port > 65535 {
			return fmt.Errorf("invalid prometheus port: %d", cfg.Prometheus.Port)
		}
	}

	// Validate upstream configuration
	if cfg.Upstream.RawConfig != nil {
		if err := ValidateUpstreamConfig(cfg.Upstream.RawConfig); err != nil {
			return fmt.Errorf("upstream configuration validation failed: %w", err)
		}
	}

	// Validate cache configuration
	if cfg.Cache.RedisURL != "" {
		if _, err := url.Parse(cfg.Cache.RedisURL); err != nil {
			return fmt.Errorf("invalid redis URL: %w", err)
		}
	}

	return nil
}

// ValidateUpstreamConfig validates upstream configuration
func ValidateUpstreamConfig(rawConfig *UpstreamRawConfig) error {
	if rawConfig == nil {
		return fmt.Errorf("upstream raw config is nil")
	}

	if len(rawConfig.Upstreams) == 0 {
		return fmt.Errorf("at least one upstream must be configured")
	}

	for i, upstream := range rawConfig.Upstreams {
		if upstream.Name == "" {
			return fmt.Errorf("upstream[%d]: name cannot be empty", i)
		}

		if len(upstream.URLs) == 0 {
			return fmt.Errorf("upstream[%d]: at least one URL must be configured", i)
		}

		// Validate URLs
		for j, urlEntry := range upstream.URLs {
			if len(urlEntry) < 2 {
				return fmt.Errorf("upstream[%d].urls[%d]: invalid format, expected [prefix, url]", i, j)
			}

			prefix, ok := urlEntry[0].(string)
			if !ok || prefix == "" {
				return fmt.Errorf("upstream[%d].urls[%d]: prefix must be a non-empty string", i, j)
			}

			urlStr, ok := urlEntry[1].(string)
			if !ok || urlStr == "" {
				return fmt.Errorf("upstream[%d].urls[%d]: URL must be a non-empty string", i, j)
			}

			// Validate URL format
			parsedURL, err := url.Parse(urlStr)
			if err != nil {
				return fmt.Errorf("upstream[%d].urls[%d]: invalid URL format: %w", i, j, err)
			}

			// Check if URL scheme is supported
			scheme := strings.ToLower(parsedURL.Scheme)
			validSchemes := map[string]bool{
				"http":  true,
				"https": true,
				"ws":    true,
				"wss":   true,
			}
			if !validSchemes[scheme] {
				return fmt.Errorf("upstream[%d].urls[%d]: unsupported URL scheme: %s", i, j, scheme)
			}
		}

		// Validate TTLs
		for j, ttlEntry := range upstream.TTLs {
			if len(ttlEntry) < 2 {
				return fmt.Errorf("upstream[%d].ttls[%d]: invalid format, expected [prefix, ttl]", i, j)
			}

			prefix, ok := ttlEntry[0].(string)
			if !ok || prefix == "" {
				return fmt.Errorf("upstream[%d].ttls[%d]: prefix must be a non-empty string", i, j)
			}

			// TTL can be int, float64, or string (for special values)
			switch v := ttlEntry[1].(type) {
			case int:
				if v < -2 {
					return fmt.Errorf("upstream[%d].ttls[%d]: invalid TTL value: %d", i, j, v)
				}
			case float64:
				ttlInt := int(v)
				if ttlInt < -2 {
					return fmt.Errorf("upstream[%d].ttls[%d]: invalid TTL value: %f", i, j, v)
				}
			default:
				// Allow string for special values like "no-cache"
				if str, ok := v.(string); !ok || str == "" {
					return fmt.Errorf("upstream[%d].ttls[%d]: TTL must be a number or special string", i, j)
				}
			}
		}

		// Validate timeouts
		for j, timeoutEntry := range upstream.Timeouts {
			if len(timeoutEntry) < 2 {
				return fmt.Errorf("upstream[%d].timeouts[%d]: invalid format, expected [prefix, timeout]", i, j)
			}

			prefix, ok := timeoutEntry[0].(string)
			if !ok || prefix == "" {
				return fmt.Errorf("upstream[%d].timeouts[%d]: prefix must be a non-empty string", i, j)
			}

			// Timeout can be int or float64
			switch v := timeoutEntry[1].(type) {
			case int:
				if v < -1 {
					return fmt.Errorf("upstream[%d].timeouts[%d]: invalid timeout value: %d", i, j, v)
				}
			case float64:
				timeoutInt := int(v)
				if timeoutInt < -1 {
					return fmt.Errorf("upstream[%d].timeouts[%d]: invalid timeout value: %f", i, j, v)
				}
			default:
				return fmt.Errorf("upstream[%d].timeouts[%d]: timeout must be a number", i, j)
			}
		}
	}

	return nil
}

