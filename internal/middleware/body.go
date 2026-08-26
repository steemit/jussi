package middleware

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/errors"
)

// DefaultMaxBodySize is the default cap on JSON-RPC request bodies (4 MiB).
// Legitimate Steem transactions are a few KiB; batches of 100 requests with
// typical params stay well under this limit.
const DefaultMaxBodySize = 4 << 20

// BodyParseMiddleware reads the request body once (enforcing a size cap),
// parses it as JSON, and stores the result in the "parsed_body" context key.
// The raw body is restored so downstream code can still read c.Request.Body.
//
// This must be registered BEFORE CacheLookupMiddleware and LimitsMiddleware:
// both previously called ShouldBindJSON themselves, and whichever ran second
// got an EOF (the body was already consumed) — which silently disabled all
// limit checks. Parsing once here and sharing the result fixes that.
func BodyParseMiddleware(maxBodySize int64) gin.HandlerFunc {
	if maxBodySize <= 0 {
		maxBodySize = DefaultMaxBodySize
	}
	return func(c *gin.Context) {
		if c.Request.Method != http.MethodPost {
			c.Next()
			return
		}

		c.Request.Body = http.MaxBytesReader(c.Writer, c.Request.Body, maxBodySize)
		raw, err := io.ReadAll(c.Request.Body)
		if err != nil {
			errors.HandleError(c, errors.NewInvalidRequest(
				fmt.Sprintf("request body unreadable or exceeds %d bytes", maxBodySize)), nil)
			c.Abort()
			return
		}

		var body interface{}
		if len(raw) > 0 {
			if err := json.Unmarshal(raw, &body); err != nil {
				errors.HandleError(c, errors.NewParseError(err.Error()), nil)
				c.Abort()
				return
			}
		}

		c.Set("parsed_body", body)
		// Restore the body so anything downstream that still reads
		// c.Request.Body (e.g. Gin's ShouldBindJSON) sees the same bytes.
		c.Request.Body = io.NopCloser(bytes.NewReader(raw))

		c.Next()
	}
}

// ParsedBody returns the request body parsed by BodyParseMiddleware.
// The second return value is false when the middleware did not run or the
// body was empty.
func ParsedBody(c *gin.Context) (interface{}, bool) {
	if v, exists := c.Get("parsed_body"); exists {
		return v, true
	}
	return nil, false
}
