package telemetry

import (
	"context"
	"fmt"
	"net/url"
	"strings"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/exporters/prometheus"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.4.0"

	"github.com/steemit/jussi/internal/config"
)

// Setup initializes OpenTelemetry SDK
func Setup(cfg config.TelemetryConfig) (func(), error) {
	ctx := context.Background()

	// Create resource
	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceNameKey.String(cfg.ServiceName),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create resource: %w", err)
	}

	// Parse endpoint URL to extract host:port and optional path
	// WithEndpoint expects host:port format, not full URL
	endpoint := cfg.OTLPEndpoint
	urlPath := cfg.OTLPPath // explicit override from config
	if strings.HasPrefix(cfg.OTLPEndpoint, "http://") || strings.HasPrefix(cfg.OTLPEndpoint, "https://") {
		parsedURL, err := url.Parse(cfg.OTLPEndpoint)
		if err != nil {
			return nil, fmt.Errorf("failed to parse endpoint URL: %w", err)
		}
		endpoint = parsedURL.Host
		if parsedURL.Port() == "" {
			// Default port based on scheme
			if parsedURL.Scheme == "https" {
				endpoint += ":4318"
			} else {
				endpoint += ":4318"
			}
		}
		// If URL has a path and no explicit override, use it
		if urlPath == "" && parsedURL.Path != "" && parsedURL.Path != "/" {
			urlPath = parsedURL.Path
		}
	}

	// Build OTLP HTTP client options. https:// endpoints use TLS so the
	// OTLP headers (which may carry Authorization credentials) and trace
	// payloads are encrypted in transit.
	useTLS := strings.HasPrefix(cfg.OTLPEndpoint, "https://")
	opts := []otlptracehttp.Option{
		otlptracehttp.WithEndpoint(endpoint),
	}
	if !useTLS {
		opts = append(opts, otlptracehttp.WithInsecure())
	}
	// Custom URL path (e.g. /api/default/v1/traces for OpenObserve)
	if urlPath != "" {
		opts = append(opts, otlptracehttp.WithURLPath(urlPath))
	}
	// Custom headers (e.g. Authorization for OpenObserve Basic Auth)
	if len(cfg.OTLPHeaders) > 0 {
		opts = append(opts, otlptracehttp.WithHeaders(cfg.OTLPHeaders))
	}

	// Setup trace exporter
	traceExporter, err := otlptrace.New(ctx,
		otlptracehttp.NewClient(opts...),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create trace exporter: %w", err)
	}

	// Setup trace provider
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(traceExporter),
		sdktrace.WithResource(res),
	)
	otel.SetTracerProvider(tp)

	// Setup propagation. Baggage is deliberately NOT propagated: this is a
	// public gateway, so client-supplied baggage headers are untrusted input
	// that would otherwise flow into traces and upstream requests.
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
	))

	// Setup Prometheus exporter
	promExporter, err := prometheus.New()
	if err != nil {
		return nil, fmt.Errorf("failed to create prometheus exporter: %w", err)
	}

	_ = promExporter // Will be used in metrics setup

	// Return shutdown function
	shutdown := func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := tp.Shutdown(ctx); err != nil {
			// Log error
		}
	}

	return shutdown, nil
}

