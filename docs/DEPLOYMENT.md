# Jussi Deployment Guide

## Overview

Jussi is a JSON-RPC 2.0 reverse proxy designed for high-performance blockchain API access. This guide covers deployment options and best practices.

## Docker Deployment

### Quick Start

1. **Build the Docker image:**
   ```bash
   docker build -t jussi:latest .
   ```

2. **Run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

### Docker Compose Services

The provided `docker-compose.yml` includes:

- **jussi**: Main application service
- **redis**: Cache backend
- **jaeger**: Distributed tracing
- **prometheus**: Metrics collection

### Environment Variables

The Go service uses the `JUSSI_` prefix (see [CONFIGURATION.md](CONFIGURATION.md)). Common deployment variables:

| Variable | Description | Default / notes |
|----------|-------------|-----------------|
| `JUSSI_SERVER_HOST` | Server bind address | `0.0.0.0` |
| `JUSSI_SERVER_PORT` | HTTP listen port (JSON-RPC, `/health`, `/metrics`) | `9000` (many configs); `8080` in sample `DEV_config.json` |
| `JUSSI_UPSTREAM_CONFIG_FILE` | Path to upstream JSON inside the container | e.g. `/app/configfiles.json` |
| `JUSSI_CACHE_REDIS_URL` | Redis URL (`cache.redis_url`) | `redis://host:6379` |
| `LOG_LEVEL` | Log level | `INFO` / `info` (validated case-insensitively) |
| `LOG_FORMAT` | Log format | `json`, `text` |
| `JUSSI_TELEMETRY_ENABLED` | OpenTelemetry traces | `true` |
| `JUSSI_TELEMETRY_OTLP_ENDPOINT` | OTLP **HTTP** collector URL (host must reach Jaeger) | e.g. `http://watchtower-private-ip:4318` |
| `JUSSI_TELEMETRY_SERVICE_NAME` | Trace service name | `jussi` |
| `JUSSI_TELEMETRY_RESOURCE_ATTRIBUTES` | Extra resource attributes | e.g. `deployment.environment=dev` |
| `JUSSI_PROMETHEUS_ENABLED` | Expose Prometheus on the **same** port as the app | `true` |
| `JUSSI_PROMETHEUS_PATH` | Metrics path | `/metrics` |
| `JUSSI_PROMETHEUS_LOCALHOST_ONLY` | If `true`, only localhost can scrape | Set `false` when Prometheus runs on another host (e.g. Watchtower) |

**Watchtower**: the shared observability stack exposes OTLP HTTP on **4318** and OTLP gRPC on **4317**; the Go exporter uses **HTTP** (`otlptracehttp`), so point `JUSSI_TELEMETRY_OTLP_ENDPOINT` at `http://<watchtower-private-ip>:4318`. Allow the Watchtower security group (or instance IP) to reach Jussi on `JUSSI_SERVER_PORT` for Prometheus scrape targets (`/metrics`). See the Watchtower repository README for ports and SG guidance.

## AWS Elastic Beanstalk Deployment

### Prerequisites

- AWS CLI configured
- Elastic Beanstalk CLI (eb) installed
- Docker image pushed to ECR or Docker Hub

### Deployment Steps

1. **Create Elastic Beanstalk application:**
   ```bash
   eb init jussi --platform docker
   ```

2. **Create environment:**
   ```bash
   eb create production --instance-type t3.medium
   ```

3. **Configure environment variables** (adjust OTLP host to your Watchtower instance private IP in VPC):
   ```bash
   eb setenv JUSSI_SERVER_HOST=0.0.0.0 \
            JUSSI_SERVER_PORT=9000 \
            JUSSI_CACHE_REDIS_URL=redis://your-redis-cluster:6379 \
            LOG_LEVEL=info \
            LOG_FORMAT=json \
            JUSSI_TELEMETRY_OTLP_ENDPOINT=http://watchtower-private-ip:4318 \
            JUSSI_PROMETHEUS_LOCALHOST_ONLY=false
   ```

4. **Deploy:**
   ```bash
   eb deploy
   ```

### Scalyr Integration

For log collection with Scalyr on EC2:

1. **Install Scalyr agent on EC2 instances**
2. **Configure log collection for Docker containers:**
   ```json
   {
     "logs": [
       {
         "path": "/var/lib/docker/containers/*/*-json.log",
         "attributes": {
           "parser": "dockerJson"
         }
       }
     ]
   }
   ```

3. **Jussi logs are structured JSON** with required Scalyr fields:
   - `timestamp`: ISO 8601 format
   - `level`: Log level
   - `message`: Log message
   - `service`: "jussi"
   - `version`: Application version

## Configuration

### Upstream Configuration

Create a configuration file (e.g., `config/production.json`):

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8080,
    "batch_size_limit": 50
  },
  "upstream": {
    "raw_config": {
      "upstreams": {
        "steemd": [
          ["https://api.steemit.com", 1, 30]
        ],
        "appbase": {
          "condenser_api": [
            ["https://api.steemit.com", 1, 30]
          ]
        }
      }
    }
  }
}
```

### Health Checks

- **Health endpoint**: `GET /health`
- **Metrics endpoint**: `GET /metrics` (Prometheus format)

### Load Balancer Configuration

For AWS Application Load Balancer:

1. **Target Group Settings:**
   - Protocol: HTTP
   - Port: 8080
   - Health check path: `/health`
   - Health check interval: 30 seconds

2. **Listener Rules:**
   - Forward all traffic to Jussi target group
   - Enable sticky sessions if needed

## Monitoring and Observability

### Jaeger / OpenTelemetry (Watchtower)

Traces are exported via **OTLP HTTP** to Jaeger (e.g. the Watchtower EC2 stack). Use `JUSSI_TELEMETRY_OTLP_ENDPOINT=http://<watchtower-private-ip>:4318`. Access Jaeger UI on the Watchtower host at port **16686** (VPC / VPN only unless exposed).

### Prometheus Metrics

Metrics are on the **same port** as the API (`JUSSI_SERVER_PORT`), path `JUSSI_PROMETHEUS_PATH` (default `/metrics`). When a central Prometheus (e.g. on Watchtower) scrapes Jussi, set `JUSSI_PROMETHEUS_LOCALHOST_ONLY=false` or configure `allowed_ips` in JSON / env.

Key metrics include:

- `jussi_requests_total`: Total requests processed
- `jussi_request_duration_seconds`: Request processing time
- `jussi_upstream_requests_total`: Upstream requests
- `jussi_cache_operations_total`: Cache operations
- `jussi_errors_total`: Error counts

### Grafana Dashboard

Import the provided Grafana dashboard for visualization:

1. Add Prometheus as data source
2. Import dashboard from `monitoring/grafana-dashboard.json`

## Performance Tuning

### Resource Requirements

**Minimum (Development):**
- CPU: 1 vCPU
- Memory: 512 MB
- Storage: 1 GB

**Production (Medium Load):**
- CPU: 2-4 vCPUs
- Memory: 2-4 GB
- Storage: 10 GB

**Production (High Load):**
- CPU: 8+ vCPUs
- Memory: 8+ GB
- Storage: 50+ GB

### Scaling Recommendations

1. **Horizontal Scaling:**
   - Deploy multiple Jussi instances behind load balancer
   - Use shared Redis cluster for caching
   - Configure session affinity if needed

2. **Vertical Scaling:**
   - Increase CPU for higher throughput
   - Increase memory for larger cache
   - Use SSD storage for better I/O

3. **Cache Optimization:**
   - Use Redis cluster for high availability
   - Configure appropriate TTL values
   - Monitor cache hit rates

## Security

### Network Security

1. **Firewall Rules:**
   - Allow inbound: 8080 (HTTP), 443 (HTTPS)
   - Allow outbound: 80, 443 (upstream APIs)
   - Restrict Redis access to application subnet

2. **TLS/SSL:**
   - Use HTTPS for external access
   - Configure TLS termination at load balancer
   - Use TLS for upstream connections when available

### Application Security

1. **Rate Limiting:**
   - Configure batch size limits
   - Implement request rate limiting at load balancer
   - Monitor for abuse patterns

2. **Input Validation:**
   - JSON-RPC request validation enabled by default
   - Parameter validation for known methods
   - Request size limits

## Troubleshooting

### Common Issues

1. **High Memory Usage:**
   - Check cache size configuration
   - Monitor for memory leaks
   - Adjust garbage collection settings

2. **Slow Response Times:**
   - Check upstream API latency
   - Verify cache hit rates
   - Monitor database connections

3. **Connection Errors:**
   - Verify upstream URL configuration
   - Check network connectivity
   - Review firewall rules

### Log Analysis

Search for common error patterns:

```bash
# Connection errors
grep "connection refused" /var/log/jussi.log

# Timeout errors
grep "timeout" /var/log/jussi.log

# Cache errors
grep "cache error" /var/log/jussi.log
```

### Health Check Failures

If health checks fail:

1. Check application logs
2. Verify Redis connectivity
3. Test upstream API availability
4. Check resource utilization

## Backup and Recovery

### Configuration Backup

- Store configuration files in version control
- Backup environment variables
- Document custom settings

### Data Backup

- Redis cache data is ephemeral (no backup needed)
- Application logs should be centralized
- Monitor configuration changes

## Support

For issues and questions:

1. Check application logs
2. Review monitoring dashboards
3. Consult troubleshooting guide
4. Contact development team

## Version History

- **v2.0.0**: Go + Gin refactoring with OpenTelemetry
- **v1.x**: Original Python implementation (legacy)

