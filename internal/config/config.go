package config

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/spf13/viper"
)

// Config holds the application configuration
type Config struct {
	Server     ServerConfig     `mapstructure:"server"`
	Upstream   UpstreamConfig   `mapstructure:"upstream"`
	Cache      CacheConfig      `mapstructure:"cache"`
	Logging    LoggingConfig    `mapstructure:"logging"`
	Telemetry  TelemetryConfig  `mapstructure:"telemetry"`
	Prometheus PrometheusConfig `mapstructure:"prometheus"`
	Limits     LimitsConfig     `mapstructure:"limits"`
}

// ServerConfig holds server configuration
type ServerConfig struct {
	Host           string `mapstructure:"host"`
	Port           int    `mapstructure:"port"`
	Workers        int    `mapstructure:"workers"`
	TCPBacklog     int    `mapstructure:"tcp_backlog"`
	BatchSizeLimit int    `mapstructure:"batch_size_limit"`
}

// UpstreamConfig holds upstream configuration
type UpstreamConfig struct {
	TestURLs         bool                `mapstructure:"test_urls"`
	WebSocketEnabled bool                `mapstructure:"websocket_enabled"`
	WebSocketPool    WebSocketPoolConfig `mapstructure:"websocket_pool"`
	RawConfig        *UpstreamRawConfig  `mapstructure:"-"`
}

// WebSocketPoolConfig holds WebSocket pool configuration
type WebSocketPoolConfig struct {
	MinSize    int `mapstructure:"min_size"`
	MaxSize    int `mapstructure:"max_size"`
	QueueSize  int `mapstructure:"queue_size"`
	ReadLimit  int `mapstructure:"read_limit"`
	WriteLimit int `mapstructure:"write_limit"`
	MaxMsgSize int `mapstructure:"max_msg_size"`
}

// CacheConfig holds cache configuration
type CacheConfig struct {
	Enabled         bool              `mapstructure:"enabled"`
	Memory          MemoryCacheConfig `mapstructure:"memory"`
	Redis           RedisConfig       `mapstructure:"redis"`
	RedisURL        string            `mapstructure:"redis_url"` // Direct URL from environment variable
	ReadReplicaURLs []string          `mapstructure:"read_replica_urls"`
	ReadTimeout     float64           `mapstructure:"read_timeout"`
	TestBeforeAdd   bool              `mapstructure:"test_before_add"`
}

// MemoryCacheConfig holds in-memory cache configuration
type MemoryCacheConfig struct {
	MaxSize int `mapstructure:"max_size"`
}

// RedisConfig holds Redis cache configuration
type RedisConfig struct {
	Address      string `mapstructure:"address"`
	Password     string `mapstructure:"password"`
	DB           int    `mapstructure:"db"`
	PoolSize     int    `mapstructure:"pool_size"`
	ReadTimeout  int    `mapstructure:"read_timeout"`
	WriteTimeout int    `mapstructure:"write_timeout"`
	DialTimeout  int    `mapstructure:"dial_timeout"`
	Compression  bool   `mapstructure:"compression"`
}

// GetRedisURL returns the Redis URL, either from direct RedisURL or constructed from Redis config
func (c *CacheConfig) GetRedisURL() string {
	// Priority: direct RedisURL (from env) > constructed from Redis config
	if c.RedisURL != "" {
		return c.RedisURL
	}

	// Construct URL from Redis config
	if c.Redis.Address == "" {
		return ""
	}

	url := "redis://"
	if c.Redis.Password != "" {
		url += c.Redis.Password + "@"
	}
	url += c.Redis.Address
	if c.Redis.DB > 0 {
		url += "/" + fmt.Sprintf("%d", c.Redis.DB)
	}

	return url
}

// LoggingConfig holds logging configuration
type LoggingConfig struct {
	Level         string `mapstructure:"level"`
	Format        string `mapstructure:"format"`
	Output        string `mapstructure:"output"`
	IncludeCaller bool   `mapstructure:"include_caller"`
	TimestampFmt  string `mapstructure:"timestamp_format"`
}

// TelemetryConfig holds OpenTelemetry configuration
type TelemetryConfig struct {
	Enabled            bool   `mapstructure:"enabled"`
	ServiceName        string `mapstructure:"service_name"`
	OTLPEndpoint       string `mapstructure:"otlp_endpoint"`
	TracesEndpoint     string `mapstructure:"traces_endpoint"`
	ResourceAttributes string `mapstructure:"resource_attributes"`
}

// PrometheusConfig holds Prometheus configuration
type PrometheusConfig struct {
	Enabled       bool     `mapstructure:"enabled"`
	Path          string   `mapstructure:"path"`
	LocalhostOnly bool     `mapstructure:"localhost_only"`
	AllowedIPs    []string `mapstructure:"allowed_ips"`
}

// LimitsConfig holds rate limiting configuration
type LimitsConfig struct {
	AccountHistoryLimit int `mapstructure:"account_history_limit"`
}

// LoadConfig loads configuration from environment variables and config file
func LoadConfig() (*Config, error) {
	viper.SetEnvPrefix("JUSSI")

	// Use explicit env binding instead of AutomaticEnv() because Viper's
	// default key replacer converts ALL underscores to dots (e.g.,
	// TELEMETRY_OTLP_ENDPOINT → telemetry.otlp.endpoint instead of
	// telemetry.otlp_endpoint), which breaks nested struct unmarshaling.
	bindEnvOverrides()

	// Set defaults
	setDefaults()

	// Load config file if specified
	configFile := viper.GetString("upstream_config_file")
	if configFile == "" {
		configFile = "DEV_config.json"
	}

	if _, err := os.Stat(configFile); err == nil {
		viper.SetConfigFile(configFile)
		if err := viper.ReadInConfig(); err != nil {
			return nil, fmt.Errorf("failed to read config file: %w", err)
		}
	}

	var config Config
	if err := viper.Unmarshal(&config); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	// Load upstream config from JSON file
	upstreamConfig, err := loadUpstreamConfig(configFile)
	if err != nil {
		return nil, fmt.Errorf("failed to load upstream config: %w", err)
	}
	config.Upstream.RawConfig = upstreamConfig

	return &config, nil
}

// bindEnvOverrides reads JUSSI_* environment variables and sets them as Viper
// config values using correct dot-separated keys. Viper's AutomaticEnv() uses
// a key replacer that converts ALL underscores to dots, which breaks mapping
// for nested fields that contain underscores (e.g., otlp_endpoint).
func bindEnvOverrides() {
	envMappings := []struct {
		envKey string
		cfgKey string
	}{
		// Server
		{"JUSSI_SERVER_HOST", "server.host"},
		{"JUSSI_SERVER_PORT", "server.port"},
		{"JUSSI_SERVER_WORKERS", "server.workers"},
		{"JUSSI_SERVER_TCP_BACKLOG", "server.tcp_backlog"},
		{"JUSSI_JSONRPC_BATCH_SIZE_LIMIT", "server.batch_size_limit"},

		// Upstream
		{"JUSSI_UPSTREAM_CONFIG_FILE", "upstream_config_file"},
		{"JUSSI_TEST_UPSTREAM_URLS", "upstream.test_urls"},
		{"JUSSI_WEBSOCKET_ENABLED", "upstream.websocket_enabled"},
		{"JUSSI_WEBSOCKET_POOL_MINSIZE", "upstream.websocket_pool.min_size"},
		{"JUSSI_WEBSOCKET_POOL_MAXSIZE", "upstream.websocket_pool.max_size"},
		{"JUSSI_WEBSOCKET_QUEUE_SIZE", "upstream.websocket_pool.queue_size"},
		{"JUSSI_WEBSOCKET_READ_LIMIT", "upstream.websocket_pool.read_limit"},
		{"JUSSI_WEBSOCKET_WRITE_LIMIT", "upstream.websocket_pool.write_limit"},

		// Cache
		{"JUSSI_CACHE_ENABLED", "cache.enabled"},
		{"JUSSI_CACHE_READ_TIMEOUT", "cache.read_timeout"},
		{"JUSSI_CACHE_TEST_BEFORE_ADD", "cache.test_before_add"},
		{"JUSSI_CACHE_REDIS_URL", "cache.redis_url"},
		{"JUSSI_CACHE_REDIS_POOL_SIZE", "cache.redis.pool_size"},

		// Logging
		{"JUSSI_LOGGING_LEVEL", "logging.level"},
		{"JUSSI_LOGGING_FORMAT", "logging.format"},
		{"JUSSI_LOGGING_OUTPUT", "logging.output"},
		{"JUSSI_LOGGING_INCLUDE_CALLER", "logging.include_caller"},
		{"JUSSI_LOGGING_TIMESTAMP_FORMAT", "logging.timestamp_format"},

		// Telemetry
		{"JUSSI_TELEMETRY_ENABLED", "telemetry.enabled"},
		{"JUSSI_TELEMETRY_SERVICE_NAME", "telemetry.service_name"},
		{"JUSSI_TELEMETRY_OTLP_ENDPOINT", "telemetry.otlp_endpoint"},
		{"JUSSI_TELEMETRY_TRACES_ENDPOINT", "telemetry.traces_endpoint"},
		{"JUSSI_TELEMETRY_RESOURCE_ATTRIBUTES", "telemetry.resource_attributes"},

		// Prometheus
		{"JUSSI_PROMETHEUS_ENABLED", "prometheus.enabled"},
		{"JUSSI_PROMETHEUS_PATH", "prometheus.path"},
		{"JUSSI_PROMETHEUS_LOCALHOST_ONLY", "prometheus.localhost_only"},

		// Limits
		{"JUSSI_LIMITS_ACCOUNT_HISTORY_LIMIT", "limits.account_history_limit"},

		// Cache key prefix for workaround sub-request caching
		// Read at init() time in get_state_workaround.go, not via viper.
		// Documented here for reference.
	}

	for _, m := range envMappings {
		if val, ok := os.LookupEnv(m.envKey); ok {
			viper.Set(m.cfgKey, val)
		}
	}
}

// UpstreamRawConfig represents the raw upstream configuration from JSON
// Uses Legacy format: upstreams array with urls/ttls/timeouts
type UpstreamRawConfig struct {
	Limits    map[string]interface{} `json:"limits"`
	Upstreams []UpstreamDefinition   `json:"upstreams"` // Legacy format: array of upstream definitions
}

// UpstreamDefinition represents a single upstream configuration
type UpstreamDefinition struct {
	Name               string          `json:"name"`
	TranslateToAppbase bool            `json:"translate_to_appbase"`
	URLs               [][]interface{} `json:"urls"`
	TTLs               [][]interface{} `json:"ttls"`
	Timeouts           [][]interface{} `json:"timeouts"`
}

func loadUpstreamConfig(filename string) (*UpstreamRawConfig, error) {
	data, err := os.ReadFile(filename)
	if err != nil {
		return nil, err
	}

	// First, try to parse as generic JSON to detect format
	var raw map[string]interface{}
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, err
	}

	var config UpstreamRawConfig

	// Load upstreams (must be array format)
	if upstreamsRaw, ok := raw["upstreams"]; ok {
		upstreamsJSON, _ := json.Marshal(upstreamsRaw)
		if err := json.Unmarshal(upstreamsJSON, &config.Upstreams); err != nil {
			return nil, fmt.Errorf("failed to parse upstreams array: %w", err)
		}
	}

	// Load limits if present
	if limitsRaw, ok := raw["limits"]; ok {
		if limitsMap, ok := limitsRaw.(map[string]interface{}); ok {
			config.Limits = limitsMap
		}
	}

	return &config, nil
}

func setDefaults() {
	// Server defaults
	viper.SetDefault("server.host", "0.0.0.0")
	viper.SetDefault("server.port", 9000)
	viper.SetDefault("server.workers", 0) // 0 means use CPU count
	viper.SetDefault("server.tcp_backlog", 100)
	viper.SetDefault("server.batch_size_limit", 50)

	// WebSocket pool defaults
	viper.SetDefault("upstream.websocket_pool.min_size", 8)
	viper.SetDefault("upstream.websocket_pool.max_size", 8)
	viper.SetDefault("upstream.websocket_pool.queue_size", 1)
	viper.SetDefault("upstream.websocket_pool.read_limit", 65536)
	viper.SetDefault("upstream.websocket_pool.write_limit", 65536)

	// Cache defaults
	viper.SetDefault("cache.enabled", true)
	viper.SetDefault("cache.read_timeout", 1.0)
	viper.SetDefault("cache.test_before_add", false)

	// Logging defaults
	viper.SetDefault("logging.level", "INFO")
	viper.SetDefault("logging.format", "json")
	viper.SetDefault("logging.output", "stdout")
	viper.SetDefault("logging.include_caller", false)
	viper.SetDefault("logging.timestamp_format", "rfc3339")

	// Telemetry defaults
	viper.SetDefault("telemetry.enabled", true)
	viper.SetDefault("telemetry.service_name", "jussi")
	viper.SetDefault("telemetry.otlp_endpoint", "http://localhost:4317")

	// Prometheus defaults
	viper.SetDefault("prometheus.enabled", true)
	viper.SetDefault("prometheus.path", "/metrics")
	viper.SetDefault("prometheus.localhost_only", true)

	// Limits defaults
	// account_history_limit: temporary protection for ahnode backend.
	// Ported from legacy Python jussi (commit 94e3ef2, PR #235).
	// get_account_history with large limit values severely degrades ahnode
	// performance, so we cap it at 100 at the gateway level.
	viper.SetDefault("limits.account_history_limit", 100)

	// Upstream defaults
	viper.SetDefault("upstream.test_urls", true)
	viper.SetDefault("upstream.websocket_enabled", false)
}
