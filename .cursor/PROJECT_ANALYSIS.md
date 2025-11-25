# Jussi Project Analysis

## Project Overview

Jussi is a high-performance JSON-RPC 2.0 reverse proxy designed for routing JSON-RPC requests to multiple upstream services based on method namespaces. It was originally built for the Steem blockchain ecosystem but can be adapted for any JSON-RPC-based service architecture.

## Core Features

### 1. Namespace-Based Routing
- Routes JSON-RPC requests to upstream services based on method namespaces
- Supports default namespace (methods without namespace prefix default to "steemd")
- Uses prefix trie (pygtrie) for efficient longest-prefix matching
- Example: `sbds.count_operations` routes to sbds namespace, `get_block` routes to steemd namespace

### 2. Multi-Protocol Upstream Support
- **HTTP/HTTPS**: Standard HTTP POST requests to upstream services
- **WebSocket**: Persistent WebSocket connections with connection pooling
- Connection pooling for both protocols with configurable pool sizes
- Automatic connection management and retry logic

### 3. Intelligent Caching System
- **Multi-tier caching**:
  - In-memory cache (fastest, first tier)
  - Redis cache (distributed, second tier)
  - Support for read replicas for Redis
- **Cache key generation**: Based on URN (namespace.api.method.params)
- **TTL strategies**:
  - `0`: Never expire
  - `-1`: No caching
  - `-2`: Cache only if irreversible (blockchain consensus-aware)
  - Positive integers: Cache duration in seconds
- **Batch request caching**: Efficiently handles caching for batch JSON-RPC requests
- **Cache validation**: Validates cached responses before returning

### 4. Request Processing
- **Single JSON-RPC requests**: Individual method calls
- **Batch JSON-RPC requests**: Multiple method calls in one request
- **Request validation**: Validates JSON-RPC 2.0 compliance
- **Request translation**: Translates legacy steemd format to appbase format when needed
- **Request ID management**: Maintains original request IDs while using internal IDs for upstream

### 5. Rate Limiting and Request Controls
- **Batch size limits**: Configurable maximum batch size (default: 50)
- **Account history limits**: Limits account history query results (default: 100)
- **Custom JSON operation limits**: 
  - Size limit: 8192 bytes
  - Account blacklist support
- **Broadcast transaction validation**: Validates and limits broadcast transactions

### 6. Timeout Management
- **Request timeouts**: Configurable per namespace/method
- **Upstream timeouts**: Separate timeout configuration for upstream calls
- **Cache read timeouts**: Timeout for cache operations (default: 1.0s)
- **Special timeout values**: `0` means no timeout

### 7. Monitoring and Observability
- **Health check endpoint**: `/health` - Returns service status
- **OpenTelemetry Integration**:
  - **Distributed Tracing**: Exports traces to Jaeger via OTLP
    - End-to-end request tracing
    - Span creation for all critical operations
    - Context propagation to upstream services
  - **Metrics Collection**: Exports metrics to Prometheus
    - Request rate, latency, error rates
    - Cache hit/miss ratios
    - Upstream call metrics
    - Connection pool metrics
- **Structured Logging**: JSON-formatted structured logging optimized for Scalyr
  - All logs output to stdout/stderr (Docker best practice)
  - JSON format for easy parsing by Scalyr
  - Rich context fields (request ID, trace ID, namespace, method, etc.)
  - Consistent log levels (DEBUG, INFO, WARN, ERROR)
  - Timestamp in ISO 8601 format

### 8. Blockchain-Specific Features
- **Irreversible block tracking**: Tracks last irreversible block number
- **Consensus-aware caching**: Adjusts cache TTL based on block irreversibility
- **Block validation**: Validates get_block responses match requested block numbers
- **Dynamic global properties**: Updates last irreversible block from upstream responses

## Architecture

### Request Flow

1. **Request Reception**
   - HTTP POST request received
   - Body parsed as JSON
   - JSON-RPC 2.0 validation

2. **Request Parsing**
   - Parse JSON-RPC method into URN (namespace.api.method.params)
   - Determine upstream configuration (URL, TTL, timeout)
   - Create JSONRPCRequest objects

3. **Cache Lookup**
   - For single requests: Check memory cache, then Redis
   - For batch requests: Batch check memory cache, then batch Redis (mget)
   - If all responses cached: Return immediately with cache hit header

4. **Upstream Request**
   - Determine protocol (HTTP or WebSocket)
   - Acquire connection from pool (if WebSocket)
   - Send request to upstream
   - Wait for response with timeout

5. **Response Processing**
   - Validate response format
   - Check if response is cacheable
   - For irreversible-aware caching: Check block irreversibility
   - Update last irreversible block number if applicable

6. **Caching**
   - Calculate TTL based on configuration and irreversibility
   - Store in memory cache
   - Store in Redis cache (async, non-blocking)

7. **Response Return**
   - Merge cached and fresh responses for batch requests
   - Add response headers (request ID, timing, cache status)
   - Return JSON response

### Component Structure

```
jussi/
├── serve.py              # Application entry point, Sanic app setup
├── handlers.py           # Request handlers (JSON-RPC, health, monitor)
├── request/
│   ├── http.py          # HTTP request wrapper
│   └── jsonrpc.py       # JSON-RPC request parsing and management
├── upstream.py          # Upstream routing and configuration
├── urn.py              # URN parsing (namespace.api.method.params)
├── cache/
│   ├── cache_group.py  # Multi-tier cache management
│   ├── backends/
│   │   ├── redis.py    # Redis cache backend
│   │   └── max_ttl.py  # In-memory cache backend
│   └── ttl.py          # TTL configuration and management
├── middlewares/
│   ├── caching.py      # Cache lookup and storage middleware
│   ├── jussi.py        # Request initialization and finalization
│   ├── limits.py       # Rate limiting and request validation
│   ├── statsd.py       # StatsD metrics collection
│   └── update_block_num.py  # Blockchain state updates
├── ws/
│   └── pool.py         # WebSocket connection pool
├── listeners.py        # Application lifecycle hooks
├── validators.py      # Request/response validation
└── errors.py          # Error handling and custom exceptions
```

## Configuration

### Upstream Configuration (JSON)

```json
{
  "limits": {
    "blacklist_accounts": ["account1", "account2"],
    "account_history_limit": 100
  },
  "upstreams": [
    {
      "name": "steemd",
      "translate_to_appbase": true,
      "urls": [
        ["steemd", "https://api.steemit.com"]
      ],
      "ttls": [
        ["steemd", 3],
        ["steemd.database_api.get_block", -2]
      ],
      "timeouts": [
        ["steemd", 5]
      ]
    }
  ]
}
```

### Environment Variables

- `JUSSI_UPSTREAM_CONFIG_FILE`: Path to upstream config file
- `JUSSI_REDIS_URL`: Redis connection URL (format: `redis://host:port`)
- `JUSSI_REDIS_READ_REPLICA_URLS`: Redis read replica URLs (array)
- `JUSSI_JSONRPC_BATCH_SIZE_LIMIT`: Maximum batch size (default: 50)
- `JUSSI_SERVER_PORT`: Server port (default: 9000)
- `JUSSI_SERVER_HOST`: Server host (default: 0.0.0.0)
- `JUSSI_SERVER_WORKERS`: Number of worker processes (default: CPU count)
- `JUSSI_WEBSOCKET_POOL_MAXSIZE`: WebSocket pool max size (default: 8)
- `JUSSI_WEBSOCKET_POOL_MINSIZE`: WebSocket pool min size (default: 8)
- `JUSSI_CACHE_READ_TIMEOUT`: Cache read timeout in seconds (default: 1.0)
- `JUSSI_TEST_UPSTREAM_URLS`: Test upstream URLs at startup (default: true)
- **Logging Configuration**:
  - `LOG_LEVEL`: Logging level (DEBUG, INFO, WARN, ERROR) (default: `INFO`)
  - `LOG_FORMAT`: Log format (`json` or `text`) (default: `json`)
  - `LOG_OUTPUT`: Log output destination (`stdout`, `stderr`, or both) (default: `stdout`)
  - `LOG_INCLUDE_CALLER`: Include caller information in logs (default: `false`)
  - `LOG_TIMESTAMP_FORMAT`: Timestamp format (`rfc3339`, `rfc3339nano`, `unix`) (default: `rfc3339`)
- **OpenTelemetry Configuration**:
  - `OTEL_EXPORTER_OTLP_ENDPOINT`: OTLP endpoint for traces (default: `http://localhost:4317`)
  - `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`: Jaeger OTLP endpoint (overrides OTEL_EXPORTER_OTLP_ENDPOINT for traces)
  - `OTEL_SERVICE_NAME`: Service name for traces (default: `jussi`)
  - `OTEL_RESOURCE_ATTRIBUTES`: Additional resource attributes (e.g., `deployment.environment=production`)
- **Prometheus Configuration**:
  - `PROMETHEUS_ENABLED`: Enable Prometheus metrics endpoint (default: `true`)
  - `PROMETHEUS_PATH`: Prometheus metrics endpoint path (default: `/metrics`)
  - `PROMETHEUS_PORT`: Port for Prometheus metrics endpoint (default: `9090`, separate from main server)

## Technical Stack

### Current Implementation (Python)
- **Framework**: Sanic (async Python web framework)
- **Event Loop**: uvloop (high-performance event loop)
- **HTTP Client**: aiohttp
- **WebSocket**: websockets library
- **Cache**: 
  - Redis: aioredis
  - In-memory: Custom implementation with max TTL
- **Data Structures**: pygtrie (prefix trie for routing)
- **JSON**: ujson (fast JSON parser)
- **Logging**: structlog
- **Validation**: jsonschema

### Target Implementation (Go + Gin)
- **Framework**: Gin (HTTP web framework)
- **HTTP Client**: net/http with connection pooling
- **WebSocket**: gorilla/websocket
- **Cache**: 
  - Redis: go-redis/redis/v8
  - In-memory: sync.Map or custom implementation
- **Data Structures**: Custom trie implementation or third-party library
- **JSON**: encoding/json (standard library)
- **Logging**: zerolog (recommended) or zap for JSON output, optimized for Scalyr
- **Validation**: JSON schema validation library
- **Observability**:
  - OpenTelemetry: go.opentelemetry.io/otel
  - Jaeger: OTLP exporter
  - Prometheus: Prometheus exporter and client

### Key Design Patterns
- **Middleware pattern**: Request/response processing pipeline
- **Connection pooling**: For WebSocket and HTTP connections
- **Multi-tier caching**: Memory + Redis with fallback
- **Trie-based routing**: Efficient longest-prefix matching
- **Async/await**: Fully asynchronous request handling

## Performance Characteristics

- **Concurrent request handling**: Uses async/await for non-blocking I/O
- **Connection pooling**: Reuses WebSocket and HTTP connections
- **Batch optimization**: Efficient batch cache lookups (mget)
- **Memory efficiency**: Compressed cache values (zlib)
- **Request timing**: Tracks performance at each stage

## Error Handling

- **JSON-RPC 2.0 compliant errors**: Standard error codes and formats
- **Custom error codes**: Extended error codes for Jussi-specific errors
- **Error logging**: Structured error logging with request context
- **Timeout handling**: Separate handling for request and response timeouts
- **Upstream error propagation**: Forwards upstream errors appropriately

## Security Features

- **Request validation**: Validates all incoming JSON-RPC requests
- **Account blacklisting**: Prevents certain accounts from using custom_json operations
- **Size limits**: Limits on custom JSON operation sizes
- **Input sanitization**: Validates request parameters and structure

## API Endpoints

- `POST /`: Main JSON-RPC endpoint
- `GET /health`: Health check endpoint
- `GET /metrics`: Prometheus metrics endpoint (if enabled)

**Note**: The `/monitor` endpoint from the original Python implementation is removed. All observability is handled through OpenTelemetry (Jaeger for traces) and Prometheus (for metrics).

## Response Headers

- `x-jussi-request-id`: Unique request identifier
- `x-amzn-trace-id`: AWS X-Ray trace ID (if provided)
- `x-jussi-response-time`: Total response time in seconds
- `x-jussi-cache-hit`: Cache key if response was cached
- `x-jussi-namespace`: Namespace of the request
- `x-jussi-api`: API of the request
- `x-jussi-method`: Method name
- `x-jussi-params`: Request parameters (truncated)
- `x-jussi-error-id`: Error ID if an error occurred

## Testing

The project includes comprehensive tests covering:
- JSON-RPC request/response handling
- Cache functionality
- Upstream routing
- Error handling
- Batch requests
- Validation logic
- TTL management

## Observability Architecture

### OpenTelemetry + Jaeger + Prometheus Stack

As the entry point for all traffic, Jussi implements comprehensive observability using OpenTelemetry, Jaeger, and Prometheus.

#### Distributed Tracing with Jaeger

- **Trace Export**: All traces are exported to Jaeger via OTLP (OpenTelemetry Protocol)
- **Trace Structure**:
  - Root span: Entire JSON-RPC request lifecycle
  - Child spans:
    - `request.parse`: JSON-RPC request parsing and validation
    - `cache.lookup`: Cache lookup operations (memory + Redis)
    - `cache.store`: Cache storage operations
    - `upstream.http`: HTTP upstream calls
    - `upstream.websocket`: WebSocket upstream calls
    - `response.format`: Response formatting and merging
- **Span Attributes**:
  - `jussi.namespace`: Request namespace
  - `jussi.api`: API name
  - `jussi.method`: Method name
  - `jussi.upstream.url`: Upstream service URL
  - `jussi.cache.hit`: Boolean indicating cache hit
  - `jussi.request.type`: "single" or "batch"
  - `jussi.batch.size`: Batch size (for batch requests)
- **Context Propagation**: Trace context is propagated to upstream services via HTTP headers
- **Configuration**: 
  - Jaeger collector endpoint via `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`
  - Service name via `OTEL_SERVICE_NAME`

#### Metrics with Prometheus

- **Metrics Endpoint**: Exposed at `/metrics` (configurable path and port)
- **Key Metrics**:
  - **Request Metrics**:
    - `jussi_requests_total`: Total number of requests (counter)
    - `jussi_request_duration_seconds`: Request latency (histogram)
    - `jussi_request_errors_total`: Total number of errors (counter)
    - `jussi_batch_size`: Batch request size distribution (histogram)
  - **Cache Metrics**:
    - `jussi_cache_operations_total`: Cache operations (counter, with labels: operation, result)
    - `jussi_cache_hit_ratio`: Cache hit ratio (gauge)
    - `jussi_cache_operation_duration_seconds`: Cache operation latency (histogram)
  - **Upstream Metrics**:
    - `jussi_upstream_requests_total`: Upstream requests (counter, with labels: upstream, protocol)
    - `jussi_upstream_request_duration_seconds`: Upstream call latency (histogram)
    - `jussi_upstream_errors_total`: Upstream errors (counter)
  - **Connection Pool Metrics**:
    - `jussi_websocket_pool_size`: WebSocket pool size (gauge)
    - `jussi_websocket_pool_active`: Active WebSocket connections (gauge)
    - `jussi_websocket_pool_idle`: Idle WebSocket connections (gauge)
  - **System Metrics**:
    - `jussi_goroutines`: Number of goroutines (gauge)
    - `jussi_memory_usage_bytes`: Memory usage (gauge)
- **Prometheus Scraping**: Prometheus server scrapes `/metrics` endpoint at configured intervals
- **Alerting**: Key metrics can be used for alerting rules in Prometheus

#### Integration Points

1. **Application Startup**:
   - Initialize OpenTelemetry SDK
   - Configure OTLP trace exporter (Jaeger)
   - Configure Prometheus metrics exporter
   - Register custom metrics with Prometheus registry

2. **Request Processing**:
   - Create root span for each request
   - Record metrics for each operation
   - Propagate trace context

3. **Shutdown**:
   - Flush pending traces to Jaeger
   - Ensure all metrics are exported

## Logging Format Specification (Scalyr-Optimized)

### JSON Log Format

All logs are output in JSON format to stdout/stderr for optimal Scalyr collection. Example log entries:

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "message": "Request processed successfully",
  "service": "jussi",
  "request_id": "req-12345",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "namespace": "steemd",
  "api": "database_api",
  "method": "get_block",
  "upstream": "https://api.steemit.com",
  "cache_hit": false,
  "duration_ms": 45.2
}
```

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "ERROR",
  "message": "Upstream request failed",
  "service": "jussi",
  "request_id": "req-12345",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "namespace": "steemd",
  "method": "get_block",
  "upstream": "https://api.steemit.com",
  "error": {
    "type": "UpstreamResponseError",
    "message": "Connection timeout",
    "code": 1100
  }
}
```

### Required Log Fields

- **Always present**:
  - `timestamp`: ISO 8601 format (RFC3339)
  - `level`: One of DEBUG, INFO, WARN, ERROR
  - `message`: Human-readable log message
  - `service`: Always "jussi"

- **Context fields** (when available):
  - `request_id`: Jussi internal request ID
  - `trace_id`: OpenTelemetry trace ID
  - `span_id`: OpenTelemetry span ID
  - `namespace`: JSON-RPC namespace
  - `api`: API name
  - `method`: JSON-RPC method name
  - `upstream`: Upstream service URL
  - `cache_hit`: Boolean indicating cache hit
  - `duration_ms`: Operation duration in milliseconds

- **Error fields** (for error logs):
  - `error.type`: Error type/class
  - `error.message`: Error message
  - `error.code`: Error code (if applicable)

### Log Level Guidelines

- **DEBUG**: Detailed diagnostic information, request/response bodies (sanitized), cache operations
- **INFO**: Request processing, upstream calls, cache hits/misses, normal operations
- **WARN**: Non-critical errors, timeouts, retries, degraded performance
- **ERROR**: Errors, exceptions, failures, upstream errors

## Deployment

### AWS Elastic Beanstalk Deployment

- **Docker Image**: Application is packaged as Docker image
- **Deployment Platform**: AWS Elastic Beanstalk on EC2
- **Container Logs**: All logs output to stdout/stderr (Docker best practice)
- **Scalyr Integration**: 
  - Scalyr agent installed on EC2 instances
  - Collects container logs from Docker daemon
  - Parses JSON-formatted logs automatically
  - Enables log search, filtering, and alerting in Scalyr UI
- **Health Checks**: Elastic Beanstalk health checks use `/health` endpoint
- **Multi-worker support**: Can run multiple worker processes
- **Graceful shutdown**: Proper cleanup of connections and resources

### Docker Configuration

- **Logging Driver**: Use default Docker logging driver (json-file or journald)
- **Log Rotation**: Configure Docker log rotation to prevent disk space issues
- **No File Logging**: Application does not write to log files, only stdout/stderr

### Scalyr Configuration

Scalyr agent on EC2 should be configured to:
- Monitor Docker container logs
- Parse JSON log format
- Extract structured fields for indexing
- Forward logs to Scalyr cloud service

Example Scalyr agent configuration (if needed):
```json
{
  "logs": [
    {
      "path": "/var/lib/docker/containers/*/*-json.log",
      "attributes": {
        "parser": "json",
        "service": "jussi"
      }
    }
  ]
}
```

### Observability Stack
  - **Jaeger**: Deploy Jaeger collector and UI for trace visualization
    - Configure OTLP receiver on Jaeger collector
    - Set up appropriate retention policies
    - Default endpoint: `http://jaeger-collector:4317`
  - **Prometheus**: Deploy Prometheus server for metrics collection
    - Configure scrape targets pointing to Jussi `/metrics` endpoint
    - Set up alerting rules for key metrics
    - Consider using Grafana for visualization
    - Example scrape config:
      ```yaml
      scrape_configs:
        - job_name: 'jussi'
          scrape_interval: 15s
          static_configs:
            - targets: ['jussi:9090']
      ```

## Migration Notes for Go + Gin Refactoring

### Key Components to Reimplement

1. **Routing System**
   - Replace pygtrie with Go trie implementation
   - Implement longest-prefix matching

2. **Caching**
   - In-memory cache: Use sync.Map or similar
   - Redis: Use go-redis or similar library
   - Implement cache group pattern

3. **Connection Pooling**
   - WebSocket: Implement connection pool (consider using gorilla/websocket)
   - HTTP: Use http.Client with connection pooling

4. **Async Processing**
   - Replace Python async/await with goroutines and channels
   - Use context.Context for timeout management

5. **Middleware**
   - Implement Gin middleware for:
     - Request parsing
     - Cache lookup/storage
     - Rate limiting
   - **OpenTelemetry Integration** (High Priority):
     - Distributed tracing for all requests
     - Span creation for request lifecycle, upstream calls, and cache operations
     - Context propagation to upstream services
     - Metrics collection via OTLP (optional)
     - This is critical as Jussi is the entry point for all traffic

6. **Configuration**
   - Use Viper or similar for configuration management
   - Support JSON config files and environment variables

7. **Logging** (Scalyr-Optimized)
   - Use structured logging library (recommended: `zerolog` or `zap` for JSON output)
   - **Scalyr Best Practices**:
     - Output all logs to stdout/stderr (Docker container best practice)
     - Use JSON format for structured logging
     - Include consistent fields in every log entry:
       - `timestamp`: ISO 8601 format timestamp
       - `level`: Log level (DEBUG, INFO, WARN, ERROR)
       - `message`: Human-readable message
       - `service`: Service name ("jussi")
       - `request_id`: Jussi request ID (when available)
       - `trace_id`: OpenTelemetry trace ID (when available)
       - `span_id`: OpenTelemetry span ID (when available)
       - `namespace`: Request namespace (when available)
       - `method`: JSON-RPC method (when available)
       - `upstream`: Upstream service URL (when available)
       - `error`: Error details (for error logs)
     - Use consistent field names (avoid changing field names between log entries)
     - Avoid logging sensitive information (passwords, tokens, etc.)
     - Use appropriate log levels:
       - DEBUG: Detailed diagnostic information
       - INFO: General informational messages, request processing
       - WARN: Warning messages, non-critical errors
       - ERROR: Error messages, exceptions, failures
   - **Docker Integration**:
     - Ensure logs are written to stdout/stderr (not files)
     - Use JSON format for easy parsing by Scalyr agent
     - Avoid buffering logs (use line-buffered or unbuffered output)
   - **File**: `internal/logging/logger.go`

8. **Validation**
   - Use JSON schema validation library
   - Implement JSON-RPC 2.0 validation

9. **OpenTelemetry Integration** (Critical - Highest Priority)
   - **Why Critical**: As the entry point for all traffic, OpenTelemetry is essential for:
     - End-to-end distributed tracing
     - Performance monitoring
     - Debugging request flows
     - Understanding upstream service dependencies
   - **Implementation Requirements**:
     - Initialize OpenTelemetry SDK on startup
     - Create root span for each incoming request
     - Create child spans for:
       - Request parsing
       - Cache operations (lookup and storage)
       - Upstream HTTP calls
       - Upstream WebSocket calls
       - Response formatting
     - Propagate trace context to upstream services
     - **Jaeger Integration**:
       - Export traces via OTLP to Jaeger collector
       - Configure Jaeger endpoint via `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`
       - Use Jaeger-compatible span attributes
       - Support for Jaeger sampling configuration
     - **Prometheus Integration**:
       - Expose Prometheus metrics endpoint (`/metrics`)
       - Export metrics via OpenTelemetry Prometheus exporter
       - Key metrics to expose:
         - Request rate (requests per second)
         - Request latency (p50, p95, p99)
         - Error rate
         - Cache hit/miss ratio
         - Upstream call latency
         - Connection pool utilization
         - Batch request size distribution
     - Add span attributes: namespace, method, upstream URL, cache hit/miss, response status
     - Record errors and exceptions in spans
     - Use otelgin middleware for automatic HTTP instrumentation
     - Custom middleware for JSON-RPC specific tracing
   - **Dependencies**:
     - `go.opentelemetry.io/otel` - Core OpenTelemetry
     - `go.opentelemetry.io/otel/trace` - Tracing
     - `go.opentelemetry.io/otel/metric` - Metrics
     - `go.opentelemetry.io/otel/exporters/otlp/otlptrace` - OTLP trace exporter (for Jaeger)
     - `go.opentelemetry.io/otel/exporters/prometheus` - Prometheus metrics exporter
     - `go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelingin` - Gin instrumentation
     - `github.com/prometheus/client_golang/prometheus` - Prometheus client (for custom metrics)
     - `github.com/prometheus/client_golang/prometheus/promhttp` - Prometheus HTTP handler

### Performance Considerations

- Go's concurrency model (goroutines) should provide excellent performance
- Consider using fasthttp for even better performance (though Gin is more feature-rich)
- Implement connection pooling carefully to avoid connection leaks
- Use sync.Pool for frequently allocated objects

### Architecture Recommendations

- Use dependency injection for better testability
- Implement interfaces for cache backends for flexibility
- Use context.Context throughout for cancellation and timeouts
- Consider using middleware chains similar to Gin's approach
- Implement graceful shutdown with proper resource cleanup
- **OpenTelemetry First**: Design all components with observability in mind
  - Pass trace context through all function calls
  - Create spans for all significant operations
  - Ensure trace context is propagated to upstream services
  - Flush traces on graceful shutdown
- **Logging Best Practices**:
  - Always output to stdout/stderr (never to files in containers)
  - Use JSON format for structured logging
  - Include trace_id and span_id in logs for correlation with Jaeger traces
  - Use consistent field names across all log entries
  - Avoid logging sensitive data (passwords, tokens, API keys)
  - Use appropriate log levels (avoid excessive DEBUG logs in production)
  - Ensure logs are not buffered (use line-buffered or unbuffered output)
- **Observability Stack**:
  - **Jaeger**: For distributed tracing and request flow visualization
    - Configure Jaeger collector endpoint
    - Use appropriate sampling rates for production
    - Ensure trace context propagation to upstream services
  - **Prometheus**: For metrics collection and alerting
    - Expose `/metrics` endpoint on separate port or path
    - Use Prometheus-compatible metric names and labels
    - Export key business and technical metrics
    - Consider using Prometheus Operator for Kubernetes deployments

