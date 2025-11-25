# Changelog

All notable changes to the Jussi project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Observability and Metrics Integration (Phase 3)

#### Prometheus Metrics
- Comprehensive Prometheus metrics collection
- Request metrics (total, duration, errors)
- Cache metrics (operations, hit ratio, duration)
- Upstream metrics (requests, duration, errors)
- Connection pool metrics (size, active, idle)
- Batch request size distribution
- All metrics exposed via /metrics endpoint

#### OpenTelemetry Integration
- Span creation for all request processing operations
- Child spans for cache operations and upstream calls
- Span attributes for namespace, method, upstream URL, cache hit/miss
- Context propagation through request processing
- Error recording in spans
- Trace export to Jaeger via OTLP

#### Request Processing Enhancements
- Integrated metrics collection in request processor
- OpenTelemetry tracing in all operations
- Improved error handling with metrics
- Performance tracking for all operations

### Added - Request Processing Flow Integration (Phase 2)

#### Request Processing
- Complete request processing flow with cache lookup and upstream calls
- Request processor for single and batch requests
- Integration of cache, router, and upstream clients
- Response caching with TTL support
- Concurrent batch request processing

#### Middleware Enhancements
- Response capture middleware for caching response bodies
- OpenTelemetry tracing middleware with span creation
- Error handling middleware for JSON-RPC compliant error responses
- Cache storage middleware integration

#### Application Architecture
- Application struct for dependency management
- Centralized application initialization and lifecycle
- Dependency injection for handlers and processors
- Resource cleanup on graceful shutdown

#### Cache System Enhancements
- Cache key generation from URN
- TTL calculation and management
- Cache validation utilities

#### Code Organization
- Separated request processing logic into dedicated processor
- Improved handler structure with dependency injection
- Better separation of concerns

### Added - Initial Go + Gin Refactoring (Phase 1)

#### Core Infrastructure
- Go module initialization with all required dependencies
- Project structure following Go best practices (cmd/, internal/, pkg/)
- Configuration system using Viper with environment variable support
- JSON config file loading for upstream configuration
- Structured logging system using zerolog, optimized for Scalyr
- Error handling framework with JSON-RPC 2.0 compliant errors

#### Request Processing
- JSON-RPC 2.0 request parsing and validation
- URN (Uniform Resource Name) parsing for namespace.api.method.params
- Support for single and batch JSON-RPC requests
- Request/response data structures

#### Routing System
- Custom Trie implementation for efficient longest-prefix matching
- Upstream router with URL, TTL, and timeout configuration per namespace/method
- Namespace-based routing to multiple upstream services

#### Caching System
- Cache interface definition for flexible backend implementation
- In-memory cache with TTL support and thread-safety
- Redis cache backend with connection pooling
- Multi-tier cache group (memory + Redis) with fallback strategy
- Batch cache operations (MGet, SetMany)

#### Upstream Communication
- HTTP upstream client with connection pooling
- WebSocket client implementation
- WebSocket connection pool with health checking
- Support for both HTTP/HTTPS and WS/WSS protocols

#### Observability
- OpenTelemetry SDK initialization
- Structured logging with trace context support (trace_id, span_id)
- Prometheus metrics endpoint (/metrics)
- Request ID middleware for request tracking

#### Middleware
- Request ID middleware for unique request identification
- Cache lookup middleware (checks cache before processing)
- Rate limiting middleware (batch size limits)
- Error handling middleware

#### Handlers
- JSON-RPC handler for POST / endpoint
- Health check handler for GET /health endpoint
- Prometheus metrics handler for GET /metrics endpoint

#### Application
- Main application entry point with Gin router
- Graceful shutdown with resource cleanup
- Environment-based configuration loading

### Technical Details

#### Dependencies
- **Framework**: Gin v1.11.0
- **Cache**: go-redis/v9 v9.3.0
- **WebSocket**: gobwas/ws v1.4.0
- **Configuration**: spf13/viper v1.21.0
- **Logging**: rs/zerolog v1.34.0
- **Validation**: santhosh-tekuri/jsonschema/v5 v5.3.1
- **OpenTelemetry**: go.opentelemetry.io/otel v1.38.0
- **Prometheus**: prometheus/client_golang v1.23.2
- **Testing**: stretchr/testify v1.11.1

#### Project Statistics
- **Go Files**: 23
- **Packages**: 15
- **Build Status**: ✅ Success
- **Binary Size**: 38MB

### Known Limitations

The following features are partially implemented and require completion:

1. **Request Processing Flow Integration**
   - Cache lookup integration in handlers needs completion
   - Upstream call integration (HTTP/WebSocket) needs to be wired up
   - Response caching storage needs response body capture implementation
   - Batch request handling needs full integration

2. **OpenTelemetry Integration**
   - Span creation for all operations needs to be added
   - Context propagation to upstream services needs implementation
   - Trace export to Jaeger needs configuration

3. **Cache Storage Middleware**
   - Response body capture mechanism needs implementation
   - TTL calculation based on upstream configuration needs integration
   - Cache key generation from URN needs proper implementation

4. **Testing**
   - Unit tests for all components
   - Integration tests
   - Performance tests

5. **Deployment**
   - Dockerfile creation
   - docker-compose.yml for local development
   - Build scripts

### Migration Notes

This is a complete rewrite from Python (Sanic) to Go (Gin). The original Python implementation has been preserved in the `legacy/` directory for reference.

Key architectural changes:
- Replaced Python async/await with Go goroutines and channels
- Replaced pygtrie with custom Trie implementation
- Replaced structlog with zerolog
- Replaced StatsD with Prometheus metrics
- Removed `/monitor` endpoint (replaced with OpenTelemetry + Prometheus)
- Added comprehensive OpenTelemetry integration for distributed tracing

---

## [Legacy] - Python Implementation

The original Python implementation using Sanic framework is preserved in the `legacy/` directory. This implementation served as the reference for the Go rewrite.

