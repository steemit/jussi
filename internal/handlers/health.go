package handlers

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
	"github.com/steemit/jussi/internal/config"
	"github.com/steemit/jussi/internal/upstream"
)

// worstBreakerState returns the most degraded state across all known
// breakers: open > half-open > closed.
func worstBreakerState(r *upstream.Registry) string {
	worst := "closed"
	rank := map[string]int{"closed": 0, "half-open": 1, "open": 2}
	for _, state := range r.Snapshot() {
		if rank[state] > rank[worst] {
			worst = state
		}
	}
	return worst
}

// HealthHandler handles health check requests
type HealthHandler struct {
	SourceCommit string
	DockerTag    string
	Tracker      *cache.BlockNumberTracker
	// Breakers, when set, exposes per-upstream circuit breaker states
	// in the health payload. May be nil (breaker not wired).
	Breakers *upstream.Registry
	// BreakerNames maps breaker registry keys (scheme://host) to the
	// opaque aliases /health reports them under. /health is public and
	// CORS-open, so backend hostnames — including internal-only ones —
	// are deployment topology that must not leak. Built from the
	// upstream config via BreakerAliases; may be nil (keys then all get
	// the digest fallback below).
	BreakerNames map[string]string
}

// NewHealthHandler creates a new health handler
func NewHealthHandler(sourceCommit, dockerTag string, tracker *cache.BlockNumberTracker) *HealthHandler {
	return &HealthHandler{
		SourceCommit: sourceCommit,
		DockerTag:    dockerTag,
		Tracker:      tracker,
	}
}

// versionInfo returns (sourceCommit, dockerTag), redacted to "unknown"
// unless JUSSI_EXPOSE_VERSION=true — build metadata on a public endpoint
// helps attackers fingerprint the deployment.
func (h *HealthHandler) versionInfo() (string, string) {
	if os.Getenv("JUSSI_EXPOSE_VERSION") == "true" {
		return h.SourceCommit, h.DockerTag
	}
	return "unknown", "unknown"
}

// HandleHealth handles GET /health requests
// Returns health information similar to the legacy project
func (h *HealthHandler) HandleHealth(c *gin.Context) {
	sourceCommit, dockerTag := h.versionInfo()
	response := gin.H{
		"status":        "OK",
		"datetime":      time.Now().UTC().Format(time.RFC3339),
		"source_commit": sourceCommit,
		"docker_tag":    dockerTag,
		"jussi_num":     h.Tracker.GetLastIrreversibleBlockNum(),
	}

	// Per-upstream circuit breaker states (closed/open/half-open),
	// keyed by configured upstream name rather than hostname. Exported
	// here in addition to the Prometheus gauge so a scrape failure never
	// blinds operators to a tripped breaker.
	if h.Breakers != nil {
		response["circuit_states"] = aliasedCircuitStates(h.Breakers.Snapshot(), h.BreakerNames)
		if state := worstBreakerState(h.Breakers); state != "closed" {
			response["circuit_degraded"] = true
			response["circuit_worst_state"] = state
		}
	}

	// Add CORS headers
	c.Header("Access-Control-Allow-Origin", "*")
	c.Header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
	c.Header("Access-Control-Allow-Headers", "DNT,Keep-Alive,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Content-Range,Range")

	c.JSON(http.StatusOK, response)
}

// BreakerAliases maps breaker registry keys (scheme://host) to the
// configured upstream names ("hivemind", "steemd"), so /health reports
// per-backend breaker states without exposing backend hostnames — the
// endpoint is public and CORS-open, and even internal-only hostnames
// reveal deployment topology.
//
// Naming rules (documented for operators in
// docs/circuit-breaker-observability.md):
//   - the alias base is the upstream's configured `name`; one alias per
//     UNIQUE host — pool-style entries that repeat a host across many
//     routing lines (e.g. 32 urls rows on 3 hosts) count it once
//   - multiple unique hosts under one name get -2, -3, ... suffixes in
//     sorted host order
//   - a host serving several named upstreams keeps the
//     alphabetically-last name (specific single-host entries like
//     "hive" win over pool entries like "appbase-2")
//   - names and hosts are walked in sorted order, so aliases are stable
//     across restarts (but renumber if the config's host set changes)
func BreakerAliases(raw *config.UpstreamRawConfig) map[string]string {
	if raw == nil {
		return nil
	}
	byName := make(map[string]map[string]struct{})
	for _, u := range raw.Upstreams {
		for _, pair := range u.URLs {
			if len(pair) != 2 {
				continue
			}
			rawURL, ok := pair[1].(string)
			if !ok || !strings.Contains(rawURL, "://") {
				// Non-URL pairs (prefix markers, ttls-style entries) in
				// the urls array.
				continue
			}
			if byName[u.Name] == nil {
				byName[u.Name] = make(map[string]struct{})
			}
			byName[u.Name][upstream.BreakerKey(rawURL)] = struct{}{}
		}
	}

	names := make([]string, 0, len(byName))
	for name := range byName {
		names = append(names, name)
	}
	sort.Strings(names)

	out := make(map[string]string)
	for _, name := range names {
		keys := make([]string, 0, len(byName[name]))
		for key := range byName[name] {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		for i, key := range keys {
			alias := name
			if i > 0 {
				alias = fmt.Sprintf("%s-%d", name, i+1)
			}
			out[key] = alias
		}
	}
	return out
}

// aliasedCircuitStates rewrites snapshot keys to their aliases. Keys
// without an alias — a breaker whose URL never appeared in the config,
// which should not happen since all runtime upstream URLs come from the
// router — fall back to a non-reversible digest so a hostname can never
// reach the response by accident.
func aliasedCircuitStates(states, aliases map[string]string) map[string]string {
	out := make(map[string]string, len(states))
	for key, state := range states {
		if alias, ok := aliases[key]; ok {
			out[alias] = state
			continue
		}
		digest := sha256.Sum256([]byte(key))
		out["upstream-"+hex.EncodeToString(digest[:4])] = state
	}
	return out
}
