package telemetry

import (
	"context"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
)

// StartSpan starts a new span with the given name
func StartSpan(ctx context.Context, name string, opts ...trace.SpanStartOption) (context.Context, trace.Span) {
	tracer := otel.Tracer("jussi")
	return tracer.Start(ctx, name, opts...)
}

// AddSpanAttributes adds attributes to a span
func AddSpanAttributes(span trace.Span, attrs map[string]string) {
	attributes := make([]attribute.KeyValue, 0, len(attrs))
	for k, v := range attrs {
		attributes = append(attributes, attribute.String(k, v))
	}
	span.SetAttributes(attributes...)
}

// RecordSpanError records an error in a span
func RecordSpanError(span trace.Span, err error) {
	span.RecordError(err)
	span.SetStatus(codes.Error, err.Error())
}

// SetSpanSuccess marks a span as successful
func SetSpanSuccess(span trace.Span) {
	span.SetStatus(codes.Ok, "Success")
}

