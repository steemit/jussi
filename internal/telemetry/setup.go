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
)

// Setup initializes OpenTelemetry SDK
func Setup(serviceName, tracesEndpoint string) (func(), error) {
	ctx := context.Background()

	// Create resource
	res, err := resource.New(ctx,
		resource.WithAttributes(
			semconv.ServiceNameKey.String(serviceName),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create resource: %w", err)
	}

	// Parse endpoint URL to extract host:port
	// WithEndpoint expects host:port format, not full URL
	endpoint := tracesEndpoint
	if strings.HasPrefix(tracesEndpoint, "http://") || strings.HasPrefix(tracesEndpoint, "https://") {
		parsedURL, err := url.Parse(tracesEndpoint)
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
	}

	// Setup trace exporter
	traceExporter, err := otlptrace.New(ctx,
		otlptracehttp.NewClient(
			otlptracehttp.WithEndpoint(endpoint),
			otlptracehttp.WithInsecure(), // Use TLS in production
		),
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

	// Setup propagation
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
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

