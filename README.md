# Jussi

A high-performance JSON-RPC 2.0 reverse proxy written in Go.

## Features

- Namespace-based routing to multiple upstream services
- Multi-tier caching (in-memory + Redis)
- HTTP and WebSocket upstream support
- OpenTelemetry integration (Jaeger + Prometheus)
- Scalyr-optimized structured logging
- Full JSON-RPC 2.0 compliance

## Building

```bash
go build -o bin/jussi ./cmd/jussi
```

## Running

```bash
./bin/jussi
```

## Configuration

Configuration is loaded from environment variables and config files. See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for detailed documentation.

### Key Features

- **Namespace-based routing**: Route requests to different upstream services based on JSON-RPC method namespaces
- **Automatic fallback**: Unconfigured namespaces automatically fall back to `appbase` or `steemd` configuration
- **Longest prefix matching**: Supports fine-grained routing with prefix-based configuration
- **Multi-tier caching**: In-memory and Redis caching with configurable TTLs

## License

See LICENSE file.

