package middleware

import (
	"bytes"

	"github.com/gin-gonic/gin"
)

// responseWriter wraps gin.ResponseWriter to capture response body
type responseWriter struct {
	gin.ResponseWriter
	body *bytes.Buffer
}

func newResponseWriter(w gin.ResponseWriter) *responseWriter {
	return &responseWriter{
		ResponseWriter: w,
		body:           &bytes.Buffer{},
	}
}

func (w *responseWriter) Write(b []byte) (int, error) {
	w.body.Write(b)
	return w.ResponseWriter.Write(b)
}

func (w *responseWriter) WriteString(s string) (int, error) {
	w.body.WriteString(s)
	return w.ResponseWriter.WriteString(s)
}

// Body returns the captured response body
func (w *responseWriter) Body() []byte {
	return w.body.Bytes()
}

// ResponseCaptureMiddleware captures response body for caching
func ResponseCaptureMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		writer := newResponseWriter(c.Writer)
		c.Writer = writer
		c.Next()
		// Response body is now available in writer.Body()
		c.Set("response_body", writer.Body())
	}
}

