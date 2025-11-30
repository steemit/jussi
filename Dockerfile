# Build stage
FROM golang:1.23-alpine AS builder

# Build arguments for proxy support
ARG HTTPS_PROXY
ARG HTTP_PROXY
ARG NO_PROXY

# Set proxy environment variables if provided
ENV HTTPS_PROXY=${HTTPS_PROXY}
ENV HTTP_PROXY=${HTTP_PROXY}
ENV NO_PROXY=${NO_PROXY}

# Install build dependencies
RUN apk add --no-cache git ca-certificates tzdata

# Set working directory
WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Get current commit hash and write to /tmp/commit_hash
RUN git rev-parse HEAD > /tmp/commit_hash 2>/dev/null || echo "unknown" > /tmp/commit_hash

# Tidy dependencies and build the application
RUN go mod tidy && CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o jussi ./cmd/jussi

# Final stage
FROM golang:1.23-alpine

# Install runtime dependencies
RUN apk --no-cache add ca-certificates tzdata

# Set working directory
WORKDIR /app

# Copy binary from builder stage
COPY --from=builder /app/jussi .

# Copy configuration files
COPY --from=builder /app/config ./config
COPY --from=builder /app/DEV_config.json .

# Copy the commit hash to /etc/version
COPY --from=builder /tmp/commit_hash /etc/version

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# Set environment variable for configuration file
ENV JUSSI_UPSTREAM_CONFIG_FILE=DEV_config.json
ENV DOCKER_TAG=latest

# Run the application
CMD ["./jussi"]

