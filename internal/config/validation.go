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

	// Validate OpenTelemetry configuration (only if enabled)
	if cfg.Telemetry.Enabled {
		if cfg.Telemetry.ServiceName == "" {
			return fmt.Errorf("otel service name cannot be empty when telemetry is enabled")
		}

		if cfg.Telemetry.TracesEndpoint != "" {
			if _, err := url.Parse(cfg.Telemetry.TracesEndpoint); err != nil {
				return fmt.Errorf("invalid otel collector endpoint: %w", err)
			}
		}
	}

	// Validate Prometheus configuration
	if cfg.Prometheus.Enabled {
		if cfg.Prometheus.Path == "" {
			return fmt.Errorf("prometheus path cannot be empty")
		}
	}

	// Skip cache validation for now
	// TODO: Implement cache validation based on actual config structure

	// Validate upstream configuration
	if cfg.Upstream.RawConfig != nil {
		if err := ValidateUpstreamConfig(cfg.Upstream.RawConfig); err != nil {
			return fmt.Errorf("upstream configuration validation failed: %w", err)
		}
	} else {
		return fmt.Errorf("upstream configuration is required but not found")
	}

	return nil
}

// ValidateUpstreamConfig validates upstream configuration
// Ensures that steemd upstream is configured (required for global params)
func ValidateUpstreamConfig(rawConfig *UpstreamRawConfig) error {
	if rawConfig == nil {
		return fmt.Errorf("upstream configuration is nil")
	}

	// Check if steemd is configured in Legacy format
	if len(rawConfig.Upstreams) > 0 {
		steemdFound := false
		for _, upstream := range rawConfig.Upstreams {
			if upstream.Name == "steemd" && len(upstream.URLs) > 0 {
				steemdFound = true
				break
			}
		}
		if !steemdFound {
			return fmt.Errorf("steemd upstream is required but not found in configuration")
		}
		return nil
	}

	// Check if steemd is configured in simplified format
	if rawConfig.UpstreamsMap == nil {
		return fmt.Errorf("upstreams configuration is required but not found")
	}

	steemdRaw, ok := rawConfig.UpstreamsMap["steemd"]
	if !ok {
		return fmt.Errorf("steemd upstream is required but not found in configuration")
	}

	// Validate that steemd has at least one URL
	if urlList, ok := steemdRaw.([]interface{}); ok {
		if len(urlList) == 0 {
			return fmt.Errorf("steemd upstream is configured but contains no URLs")
		}
		// Validate that URLs are valid strings
		for _, urlEntry := range urlList {
			if urlArray, ok := urlEntry.([]interface{}); ok && len(urlArray) >= 1 {
				if urlStr, ok := urlArray[0].(string); ok {
					if urlStr == "" {
						return fmt.Errorf("steemd upstream contains empty URL")
					}
				} else {
					return fmt.Errorf("steemd upstream URL must be a string")
				}
			}
		}
	} else {
		return fmt.Errorf("steemd upstream configuration has invalid format")
	}

	return nil
}