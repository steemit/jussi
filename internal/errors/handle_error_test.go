package errors

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

// captureHandleError runs HandleError against a test Gin context and
// decodes the JSON-RPC error envelope it writes.
func captureHandleError(t *testing.T, err error) map[string]interface{} {
	t.Helper()
	gin.SetMode(gin.TestMode)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest(http.MethodPost, "/", nil)
	HandleError(c, err, nil)

	var body map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("response is not valid JSON: %v (%s)", err, w.Body.String())
	}
	return body
}

func errorBody(t *testing.T, body map[string]interface{}) map[string]interface{} {
	t.Helper()
	e, ok := body["error"].(map[string]interface{})
	if !ok {
		t.Fatalf("no error object in response: %v", body)
	}
	return e
}

func TestHandleErrorDirectJSONRPCError(t *testing.T) {
	body := captureHandleError(t, NewRequestTimeoutError("slow upstream"))
	e := errorBody(t, body)
	if e["message"] != "Request Timeout" {
		t.Fatalf("expected Request Timeout message, got %v", e["message"])
	}
}

func TestHandleErrorWrappedJSONRPCError(t *testing.T) {
	// The circuit-breaker rejection path: a typed *JSONRPCError wrapped
	// by fmt.Errorf with %w at the call site.
	typed := NewUpstreamCircuitOpenError("circuit breaker open for https://hivemind.example")
	wrapped := fmt.Errorf("upstream call failed: %w", typed)

	body := captureHandleError(t, wrapped)
	e := errorBody(t, body)
	if e["message"] != "Upstream temporarily unavailable" {
		t.Fatalf("wrapped JSONRPCError message lost, got %v", e["message"])
	}
	// The generic internal-error path must NOT have swallowed it.
	if e["message"] == "Internal error" {
		t.Fatal("wrapped error flattened to Internal error")
	}
}

func TestHandleErrorDoubleWrappedJSONRPCError(t *testing.T) {
	typed := NewRequestTimeoutError("upstream deadline")
	double := fmt.Errorf("outer: %w", fmt.Errorf("inner: %w", typed))
	body := captureHandleError(t, double)
	e := errorBody(t, body)
	if e["message"] != "Request Timeout" {
		t.Fatalf("deeply wrapped JSONRPCError message lost, got %v", e["message"])
	}
}

func TestHandleErrorUnknownErrorStaysGeneric(t *testing.T) {
	// Regression guard for the default-branch dependants: plain errors
	// must keep the generic internal-error response and must not leak
	// their text to the client.
	sentinel := errors.New("connection to 10.0.0.1:5432 refused")
	body := captureHandleError(t, fmt.Errorf("upstream request failed: %w", sentinel))
	e := errorBody(t, body)
	if e["message"] != "Internal error" {
		t.Fatalf("expected generic Internal error, got %v", e["message"])
	}
	if detail, _ := e["data"].(map[string]interface{}); detail != nil {
		if s, _ := detail["details"].(string); s != "" {
			t.Fatalf("internal error text leaked to client: %v", s)
		}
	}
}
