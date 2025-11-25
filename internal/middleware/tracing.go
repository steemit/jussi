package middleware

import (
	"github.com/gin-gonic/gin"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/trace"
)

// TracingMiddleware adds OpenTelemetry tracing to requests
func TracingMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx := c.Request.Context()
		tracer := otel.Tracer("jussi")

		// Create span for request
		ctx, span := tracer.Start(ctx, "jussi.request",
			trace.WithSpanKind(trace.SpanKindServer),
		)
		defer span.End()

		// Add request attributes
		span.SetAttributes(
			attribute.String("http.method", c.Request.Method),
			attribute.String("http.path", c.Request.URL.Path),
			attribute.String("http.route", c.FullPath()),
		)

		// Store span in context
		c.Request = c.Request.WithContext(ctx)

		// Process request
		c.Next()

		// Add response attributes
		span.SetAttributes(
			attribute.Int("http.status_code", c.Writer.Status()),
		)

		// Mark span as error if status >= 400
		if c.Writer.Status() >= 400 {
			span.SetStatus(codes.Error, "HTTP error")
		}
	}
}

