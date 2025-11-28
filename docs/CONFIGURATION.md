# Jussi Configuration Guide

## Overview

Jussi supports configuration through JSON files and environment variables. This guide covers all available configuration options.

## Configuration Sources and Priority

Configuration is loaded in the following order (later sources override earlier ones):

1. **Default values** - Hardcoded defaults in the application
2. **Configuration file** (`DEV_config.json`) - Base configuration
3. **Environment variables** - **Highest priority**, overrides configuration file values

**Important**: Environment variables with the `JUSSI_` prefix will override values from the configuration file. This allows you to:
- Use configuration files for base settings
- Override sensitive values (like Redis passwords) via environment variables
- Deploy the same configuration file across environments with different overrides

Example:
```bash
# Configuration file has: "redis": { "address": "redis:6379" }
# Environment variable overrides: JUSSI_CACHE_REDIS_URL=redis://prod-redis:6379/1
# Result: Uses prod-redis:6379/1 instead of redis:6379
```

## Configuration File Format

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080,
    "batch_size_limit": 50,
    "request_timeout": 30,
    "response_timeout": 30
  },
  "logging": {
    "level": "info",
    "format": "json",
    "output": "stdout",
    "caller": true,
    "timestamp_format": "2006-01-02T15:04:05.000Z07:00"
  },
  "telemetry": {
    "jaeger": {
      "endpoint": "http://localhost:14268/api/traces",
      "service_name": "jussi",
      "environment": "production"
    }
  },
  "prometheus": {
    "enabled": true,
    "port": 9090,
    "path": "/metrics"
  },
  "cache": {
    "memory": {
      "enabled": true,
      "max_size": 1000000,
      "default_ttl": 300
    },
    "redis": {
      "enabled": true,
      "url": "redis://localhost:6379",
      "db": 0,
      "pool_size": 10,
      "compression": true
    }
  },
  "limits": {
    "batch_size": 50,
    "account_history_limit": 1000,
    "custom_json_op_length": 8192
  },
  "upstreams": {
    "steemd": [
      ["https://api.steemit.com", 1, 30]
    ]
  }
}
```

## Configuration Sections

### Server Configuration

Controls the HTTP server behavior.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | string | `"0.0.0.0"` | Server bind address |
| `port` | int | `8080` | Server port |
| `batch_size_limit` | int | `50` | Maximum batch request size |
| `request_timeout` | int | `30` | Request timeout in seconds |
| `response_timeout` | int | `30` | Response timeout in seconds |

**Environment Variables:**
- `JUSSI_SERVER_HOST`
- `JUSSI_SERVER_PORT`
- `JUSSI_SERVER_BATCH_SIZE_LIMIT`
- `JUSSI_SERVER_REQUEST_TIMEOUT`
- `JUSSI_SERVER_RESPONSE_TIMEOUT`

### Logging Configuration

Controls application logging behavior.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | string | `"info"` | Log level (debug, info, warn, error) |
| `format` | string | `"json"` | Log format (json, text) |
| `output` | string | `"stdout"` | Log output (stdout, stderr, file path) |
| `caller` | bool | `true` | Include caller information |
| `timestamp_format` | string | RFC3339 | Timestamp format |

**Environment Variables:**
- `JUSSI_LOGGING_LEVEL`
- `JUSSI_LOGGING_FORMAT`
- `JUSSI_LOGGING_OUTPUT`
- `JUSSI_LOGGING_CALLER`
- `JUSSI_LOGGING_TIMESTAMP_FORMAT`

### Telemetry Configuration

Controls OpenTelemetry tracing. Can be disabled for minimal overhead.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Enable OpenTelemetry tracing |
| `service_name` | string | `"jussi"` | Service name for tracing |
| `otlp_endpoint` | string | `""` | OTLP collector endpoint (e.g., `jaeger:4318`) |
| `resource_attributes` | string | `""` | Additional resource attributes |

**To disable telemetry:**
```json
{
  "telemetry": {
    "enabled": false
  }
}
```

**Environment Variables:**
- `JUSSI_TELEMETRY_ENABLED` - Enable/disable telemetry
- `JUSSI_TELEMETRY_SERVICE_NAME`
- `JUSSI_TELEMETRY_OTLP_ENDPOINT`
- `JUSSI_TELEMETRY_RESOURCE_ATTRIBUTES`

### Prometheus Configuration

Controls Prometheus metrics collection. Metrics are exposed on the same HTTP server as the main application. Can be disabled for minimal overhead.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Enable Prometheus metrics |
| `path` | string | `"/metrics"` | Metrics endpoint path (e.g., `http://localhost:8080/metrics`) |
| `localhost_only` | bool | `true` | Restrict metrics endpoint to localhost only |
| `allowed_ips` | array | `[]` | List of allowed IP addresses (if `localhost_only` is false) |

**To disable Prometheus:**
```json
{
  "prometheus": {
    "enabled": false
  }
}
```

**Note**: Metrics are served on the same port as the main application. There is no separate metrics port. Use the `path` to access metrics (e.g., `http://your-server:8080/metrics`).

**Environment Variables:**
- `JUSSI_PROMETHEUS_ENABLED` - Enable/disable Prometheus metrics
- `JUSSI_PROMETHEUS_PATH`
- `JUSSI_PROMETHEUS_LOCALHOST_ONLY`

### Cache Configuration

Controls caching behavior.

#### Memory Cache

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Enable in-memory cache |
| `max_size` | int | `1000000` | Maximum cache entries |
| `default_ttl` | int | `300` | Default TTL in seconds |

#### Redis Cache

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `false` | Enable Redis cache |
| `url` | string | `"redis://localhost:6379"` | Redis connection URL |
| `db` | int | `0` | Redis database number |
| `pool_size` | int | `10` | Connection pool size |
| `compression` | bool | `true` | Enable response compression |

**Environment Variables:**
- `JUSSI_CACHE_MEMORY_ENABLED`
- `JUSSI_CACHE_MEMORY_MAX_SIZE`
- `JUSSI_CACHE_MEMORY_DEFAULT_TTL`
- `JUSSI_CACHE_REDIS_ENABLED`
- `JUSSI_CACHE_REDIS_URL`
- `JUSSI_CACHE_REDIS_DB`
- `JUSSI_CACHE_REDIS_POOL_SIZE`
- `JUSSI_CACHE_REDIS_COMPRESSION`

### Limits Configuration

Controls request processing limits.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `batch_size` | int | `50` | Maximum batch request size |
| `account_history_limit` | int | `1000` | Account history request limit |
| `custom_json_op_length` | int | `8192` | Custom JSON operation length limit |

**Environment Variables:**
- `JUSSI_LIMITS_BATCH_SIZE`
- `JUSSI_LIMITS_ACCOUNT_HISTORY_LIMIT`
- `JUSSI_LIMITS_CUSTOM_JSON_OP_LENGTH`

## Environment Variable Override

All configuration values can be overridden using environment variables with the prefix `JUSSI_` and nested keys separated by underscores.

Examples:
- `JUSSI_SERVER_PORT=8080`
- `JUSSI_CACHE_REDIS_URL=redis://localhost:6379`
- `JUSSI_LOGGING_LEVEL=debug`

## Configuration Validation

Jussi validates configuration on startup and will exit with an error if:

- Required fields are missing
- Values are out of valid ranges
- JSON syntax is invalid

## Example Configurations

### Development Configuration

```json
{
  "server": {
    "host": "127.0.0.1",
    "port": 8080
  },
  "logging": {
    "level": "debug",
    "format": "text"
  },
  "cache": {
    "memory": {
      "enabled": true,
      "max_size": 10000
    },
    "redis": {
      "enabled": false
    }
  },
  "telemetry": {
    "jaeger": {
      "endpoint": ""
    }
  }
}
```

### Production Configuration

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080,
    "batch_size_limit": 100
  },
  "logging": {
    "level": "info",
    "format": "json"
  },
  "cache": {
    "memory": {
      "enabled": true,
      "max_size": 1000000
    },
    "redis": {
      "enabled": true,
      "url": "redis://redis-cluster:6379",
      "pool_size": 20
    }
  },
  "telemetry": {
    "jaeger": {
      "endpoint": "http://jaeger:14268/api/traces",
      "environment": "production"
    }
  },
  "prometheus": {
    "enabled": true,
    "port": 9090
  }
}
```

### High-Performance Configuration

```json
{
  "server": {
    "batch_size_limit": 200,
    "request_timeout": 60,
    "response_timeout": 60
  },
  "cache": {
    "memory": {
      "max_size": 5000000
    },
    "redis": {
      "pool_size": 50,
      "compression": true
    }
  },
  "limits": {
    "batch_size": 200,
    "account_history_limit": 10000
  }
}
```

## Best Practices

### Security

1. **Bind Address**: Use `127.0.0.1` for local-only access, `0.0.0.0` for external access
2. **Timeouts**: Set reasonable timeouts to prevent resource exhaustion
3. **Limits**: Configure appropriate batch size and request limits

### Performance

1. **Caching**: Enable both memory and Redis caching for best performance
2. **Pool Sizes**: Adjust Redis pool size based on expected load
3. **TTL Values**: Use appropriate TTL values for different data types

### Monitoring

1. **Logging**: Use JSON format for structured logging in production
2. **Metrics**: Enable Prometheus metrics for monitoring
3. **Tracing**: Configure Jaeger for distributed tracing

### Reliability

1. **Multiple Upstream URLs**: Configure multiple upstream URLs in the `upstreams` section for redundancy
2. **Health Checks**: Monitor upstream API health
3. **Graceful Degradation**: Configure fallback behavior for failures

## Troubleshooting

### Configuration Errors

1. **Invalid JSON**: Check JSON syntax with a validator
2. **Missing Fields**: Ensure required fields are present
3. **Type Mismatches**: Verify field types match expected values

### Runtime Issues

1. **Connection Errors**: Verify upstream URLs in the `upstreams` configuration are accessible
2. **Memory Issues**: Adjust cache sizes if memory usage is high
3. **Performance Issues**: Review timeout and limit settings

### Validation

Use the built-in configuration validation:

```bash
./jussi --validate-config
```

This will check configuration without starting the server.

