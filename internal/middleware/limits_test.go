package middleware

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
)

func mustMarshal(t *testing.T, v interface{}) []byte {
	t.Helper()
	b, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func makeBatch(n int) []interface{} {
	batch := make([]interface{}, 0, n)
	for i := 0; i < n; i++ {
		batch = append(batch, map[string]interface{}{
			"jsonrpc": "2.0", "method": "get_block",
			"params": []interface{}{1}, "id": i,
		})
	}
	return batch
}

// TestLimitsEnforcedWithBodyParseMiddleware is the regression test for the
// middleware-ordering bug where CacheLookupMiddleware consumed the request
// body and LimitsMiddleware's re-parse hit EOF, silently skipping every
// limit check. The chain here mirrors the registration order in app.go.
func TestLimitsEnforcedWithBodyParseMiddleware(t *testing.T) {
	gin.SetMode(gin.TestMode)

	reached := false
	r := gin.New()
	r.Use(BodyParseMiddleware(0))
	r.Use(CacheLookupMiddleware(cache.NewCacheGroup(cache.NewMemoryCache(16), nil)))
	r.Use(LimitsMiddleware(&LimitsConfig{BatchSizeLimit: 50, AccountHistoryLimit: 100}))
	r.POST("/", func(c *gin.Context) { reached = true; c.JSON(200, gin.H{"ok": true}) })

	req := httptest.NewRequest(http.MethodPost, "/", bytes.NewReader(mustMarshal(t, makeBatch(150))))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if reached {
		t.Fatalf("batch of 150 (limit 50) reached handler — limits bypassed again")
	}
	var resp map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("non-JSON response: %s", w.Body.String())
	}
	if resp["error"] == nil {
		t.Fatalf("expected JSON-RPC error, got: %s", w.Body.String())
	}
}

// TestAccountHistoryLimitEnforced checks the ahnode protection fires for a
// single request through the same chain.
func TestAccountHistoryLimitEnforced(t *testing.T) {
	gin.SetMode(gin.TestMode)

	reached := false
	r := gin.New()
	r.Use(BodyParseMiddleware(0))
	r.Use(CacheLookupMiddleware(cache.NewCacheGroup(cache.NewMemoryCache(16), nil)))
	r.Use(LimitsMiddleware(&LimitsConfig{BatchSizeLimit: 50, AccountHistoryLimit: 100}))
	r.POST("/", func(c *gin.Context) { reached = true; c.JSON(200, gin.H{"ok": true}) })

	body := mustMarshal(t, map[string]interface{}{
		"jsonrpc": "2.0", "method": "condenser_api.get_account_history",
		"params": []interface{}{"someuser", -1, 10000}, "id": 1,
	})
	req := httptest.NewRequest(http.MethodPost, "/", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if reached {
		t.Fatalf("get_account_history limit=10000 (max 100) reached handler")
	}
	if !strings.Contains(w.Body.String(), "1701") {
		t.Fatalf("expected account history limit error code 1701, got: %s", w.Body.String())
	}
}

// TestBodyParseMiddlewareSizeCap verifies oversized bodies are rejected
// before parsing.
func TestBodyParseMiddlewareSizeCap(t *testing.T) {
	gin.SetMode(gin.TestMode)

	reached := false
	r := gin.New()
	r.Use(BodyParseMiddleware(1024))
	r.POST("/", func(c *gin.Context) { reached = true; c.JSON(200, gin.H{"ok": true}) })

	big := bytes.Repeat([]byte("a"), 4096)
	req := httptest.NewRequest(http.MethodPost, "/", bytes.NewReader(big))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if reached {
		t.Fatalf("4KB body reached handler despite 1KB cap")
	}
}

// TestCustomJSONLimitEnforced verifies the custom_json size limit from the
// upstream limits config is wired into the middleware chain.
func TestCustomJSONLimitEnforced(t *testing.T) {
	gin.SetMode(gin.TestMode)

	reached := false
	r := gin.New()
	r.Use(BodyParseMiddleware(0))
	r.Use(LimitsMiddleware(&LimitsConfig{
		BatchSizeLimit:      50,
		AccountHistoryLimit: 100,
		UpstreamLimits: map[string]interface{}{
			"custom_json_size_limit": float64(8),
		},
	}))
	r.POST("/", func(c *gin.Context) { reached = true; c.JSON(200, gin.H{"ok": true}) })

	body := mustMarshal(t, map[string]interface{}{
		"jsonrpc": "2.0", "method": "condenser_api.broadcast_transaction",
		"params": []interface{}{map[string]interface{}{
			"ref_block_num": 1,
			"operations": []interface{}{
				[]interface{}{"custom_json", map[string]interface{}{
					"json": "aaaaaaaaaaaaaaaaaaaaaaaa",
				}},
			},
		}},
		"id": 1,
	})
	req := httptest.NewRequest(http.MethodPost, "/", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if reached {
		t.Fatalf("oversized custom_json op reached handler")
	}
	if !strings.Contains(w.Body.String(), "1800") {
		t.Fatalf("expected custom JSON length error code 1800, got: %s", w.Body.String())
	}
}
