package config

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/spf13/viper"
)

// Config holds the application configuration
type Config struct {
	Server      ServerConfig      `mapstructure:"server"`
	Upstream    UpstreamConfig    `mapstructure:"upstream"`
	Cache       CacheConfig       `mapstructure:"cache"`
	Logging     LoggingConfig     `mapstructure:"logging"`
	Telemetry   TelemetryConfig   `mapstructure:"telemetry"`
	Prometheus  PrometheusConfig  `mapstructure:"prometheus"`
	Limits      LimitsConfig      `mapstructure:"limits"`
}

// ServerConfig holds server configuration
type ServerConfig struct {
	Host            string `mapstructure:"host"`
	Port            int    `mapstructure:"port"`
	Workers         int    `mapstructure:"workers"`
	TCPBacklog      int    `mapstructure:"tcp_backlog"`
	BatchSizeLimit  int    `mapstructure:"batch_size_limit"`
}

// UpstreamConfig holds upstream configuration
type UpstreamConfig struct {
	TestURLs         bool                `mapstructure:"test_urls"`
	WebSocketEnabled bool                `mapstructure:"websocket_enabled"`
	WebSocketPool    WebSocketPoolConfig  `mapstructure:"websocket_pool"`
	RawConfig        *UpstreamRawConfig   `mapstructure:"-"`
}

// WebSocketPoolConfig holds WebSocket pool configuration
type WebSocketPoolConfig struct {
	MinSize      int `mapstructure:"min_size"`
	MaxSize      int `mapstructure:"max_size"`
	QueueSize    int `mapstructure:"queue_size"`
	ReadLimit    int `mapstructure:"read_limit"`
	WriteLimit   int `mapstructure:"write_limit"`
	MaxMsgSize   int `mapstructure:"max_msg_size"`
}

// CacheConfig holds cache configuration
type CacheConfig struct {
	Enabled         bool              `mapstructure:"enabled"`
	Memory          MemoryCacheConfig `mapstructure:"memory"`
	Redis           RedisConfig       `mapstructure:"redis"`
	RedisURL        string            `mapstructure:"redis_url"` // Direct URL from environment variable
	ReadReplicaURLs []string         `mapstructure:"read_replica_urls"`
	ReadTimeout     float64           `mapstructure:"read_timeout"`
	TestBeforeAdd   bool              `mapstructure:"test_before_add"`
}

// MemoryCacheConfig holds in-memory cache configuration
type MemoryCacheConfig struct {
	MaxSize int `mapstructure:"max_size"`
}

// RedisConfig holds Redis cache configuration
type RedisConfig struct {
	Address     string `mapstructure:"address"`
	Password    string `mapstructure:"password"`
	DB          int    `mapstructure:"db"`
	PoolSize    int    `mapstructure:"pool_size"`
	ReadTimeout int    `mapstructure:"read_timeout"`
	WriteTimeout int   `mapstructure:"write_timeout"`
	DialTimeout  int   `mapstructure:"dial_timeout"`
	Compression  bool  `mapstructure:"compression"`
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
	AllowedIPs   []string `mapstructure:"allowed_ips"`
}

// LimitsConfig holds rate limiting configuration
type LimitsConfig struct {
	BlacklistAccounts    []string `mapstructure:"blacklist_accounts"`
	AccountHistoryLimit  int      `mapstructure:"account_history_limit"`
}

// LoadConfig loads configuration from environment variables and config file
func LoadConfig() (*Config, error) {
	viper.SetEnvPrefix("JUSSI")
	viper.AutomaticEnv()

	// Set defaults
	setDefaults()

	// Load config file if specified
	configFile := viper.GetString("UPSTREAM_CONFIG_FILE")
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

// UpstreamRawConfig represents the raw upstream configuration from JSON
// Supports both Legacy format (upstreams array) and simplified format (upstreams object)
type UpstreamRawConfig struct {
	Limits     map[string]interface{} `json:"limits"`
	Upstreams  []UpstreamDefinition   `json:"upstreams"`  // Legacy format: array of upstream definitions
	UpstreamsMap map[string]interface{} `json:"upstreams"` // Simplified format: object map (when upstreams is not an array)
}

// UpstreamDefinition represents a single upstream configuration
type UpstreamDefinition struct {
	Name              string          `json:"name"`
	TranslateToAppbase bool           `json:"translate_to_appbase"`
	URLs              [][]interface{} `json:"urls"`
	TTLs              [][]interface{} `json:"ttls"`
	Timeouts          [][]interface{} `json:"timeouts"`
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
	
	// Check if upstreams exists and what format it is
	if upstreamsRaw, ok := raw["upstreams"]; ok {
		// Try to determine if it's an array (Legacy format) or object (simplified format)
		switch v := upstreamsRaw.(type) {
		case []interface{}:
			// Legacy format: array of upstream definitions
			upstreamsJSON, _ := json.Marshal(v)
			if err := json.Unmarshal(upstreamsJSON, &config.Upstreams); err != nil {
				return nil, fmt.Errorf("failed to parse upstreams array: %w", err)
			}
		case map[string]interface{}:
			// Simplified format: object map
			config.UpstreamsMap = v
		default:
			return nil, fmt.Errorf("upstreams must be either an array or an object, got %T", v)
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
	viper.SetDefault("SERVER_HOST", "0.0.0.0")
	viper.SetDefault("SERVER_PORT", 9000)
	viper.SetDefault("SERVER_WORKERS", 0) // 0 means use CPU count
	viper.SetDefault("SERVER_TCP_BACKLOG", 100)
	viper.SetDefault("JSONRPC_BATCH_SIZE_LIMIT", 50)

	// WebSocket pool defaults
	viper.SetDefault("WEBSOCKET_POOL_MINSIZE", 8)
	viper.SetDefault("WEBSOCKET_POOL_MAXSIZE", 8)
	viper.SetDefault("WEBSOCKET_QUEUE_SIZE", 1)
	viper.SetDefault("WEBSOCKET_READ_LIMIT", 65536)
	viper.SetDefault("WEBSOCKET_WRITE_LIMIT", 65536)

	// Cache defaults
	viper.SetDefault("CACHE_ENABLED", true)
	viper.SetDefault("CACHE_READ_TIMEOUT", 1.0)
	viper.SetDefault("CACHE_TEST_BEFORE_ADD", false)

	// Logging defaults
	viper.SetDefault("LOG_LEVEL", "INFO")
	viper.SetDefault("LOG_FORMAT", "json")
	viper.SetDefault("LOG_OUTPUT", "stdout")
	viper.SetDefault("LOG_INCLUDE_CALLER", false)
	viper.SetDefault("LOG_TIMESTAMP_FORMAT", "rfc3339")

	// Telemetry defaults
	viper.SetDefault("TELEMETRY_ENABLED", true)
	viper.SetDefault("OTEL_SERVICE_NAME", "jussi")
	viper.SetDefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

	// Prometheus defaults
	viper.SetDefault("PROMETHEUS_ENABLED", true)
	viper.SetDefault("PROMETHEUS_PATH", "/metrics")
	viper.SetDefault("PROMETHEUS_LOCALHOST_ONLY", true)

	// Upstream defaults
	viper.SetDefault("TEST_UPSTREAM_URLS", true)
	viper.SetDefault("WEBSOCKET_ENABLED", false)
}

