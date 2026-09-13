# Build stage
FROM golang:1.25-alpine AS builder

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

# Build metadata, injected by CI via build args (.git is dockerignored, so
# git rev-parse here would always yield "unknown")
ARG SOURCE_COMMIT=unknown
ARG DOCKER_TAG=latest
RUN echo "${SOURCE_COMMIT}" > /tmp/commit_hash

# Tidy dependencies and build the application (without go mod tidy)
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o jussi ./cmd/jussi

# Final stage — minimal runtime base, non-root user
FROM alpine:3.20

# Install runtime dependencies
RUN apk --no-cache add ca-certificates tzdata

# Run as an unprivileged user
RUN addgroup -S jussi && adduser -S -G jussi jussi

# Set working directory
WORKDIR /app

# Copy binary from builder stage
COPY --from=builder --chown=jussi:jussi /app/jussi .

# Copy default upstream JSON (no top-level config/ dir in this repo)
COPY --from=builder --chown=jussi:jussi /app/DEV_config.json .

# Copy the commit hash to /etc/version
COPY --from=builder /tmp/commit_hash /etc/version

# Expose port
EXPOSE 9000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:9000/health || exit 1

# Set environment variable for configuration file
ENV JUSSI_UPSTREAM_CONFIG_FILE=DEV_config.json

# Build metadata for /health and / version info (re-declare: ARG scope is
# per-stage). Real values come from CI build args; consumed by the app only
# when JUSSI_EXPOSE_VERSION=true.
ARG SOURCE_COMMIT=unknown
ARG DOCKER_TAG=latest
ENV SOURCE_COMMIT=${SOURCE_COMMIT}
ENV DOCKER_TAG=${DOCKER_TAG}

USER jussi

# Run the application
CMD ["./jussi"]

