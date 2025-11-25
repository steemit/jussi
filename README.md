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

Configuration is loaded from environment variables and config files. See `.cursor/PROJECT_ANALYSIS.md` for detailed documentation.

## License

See LICENSE file.

