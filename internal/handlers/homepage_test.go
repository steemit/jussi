package handlers

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
)

// `/` and `/health` are the same public, CORS-open shape and must not
// disagree about which build is live: both report the image's build
// metadata (accepted risk — see HealthHandler.versionInfo).
func TestHandleHomepageReportsBuildMetadata(t *testing.T) {
	h := NewHomepageHandler("404bc29", "next-404bc29", cache.NewBlockNumberTracker())
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest(http.MethodGet, "/", nil)
	h.HandleHomepage(c)

	if w.Code != http.StatusOK {
		t.Fatalf("GET / = %d, want 200", w.Code)
	}

	body := w.Body.String()
	for _, want := range []string{`"source_commit":"404bc29"`, `"docker_tag":"next-404bc29"`, `"status":"OK"`} {
		if !strings.Contains(body, want) {
			t.Fatalf("homepage payload is missing %s: %s", want, body)
		}
	}
	if strings.Contains(body, "unknown") {
		t.Fatalf("homepage payload must not redact build metadata: %s", body)
	}
}
