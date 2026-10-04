package telemetry

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// Build metadata of the running binary, taken from the environment the
// image was built with (CI passes SOURCE_COMMIT / DOCKER_TAG as build
// args, so the values travel with the image).
//
// /health and / report the same values in their JSON payload — nothing is
// redacted (accepted risk; the decision record is the comment on
// handlers.HealthHandler.versionInfo). The metric exists for the time
// series: dashboards and alert rules need "which build has been live since
// when", which a JSON endpoint cannot answer, and the series stays
// queryable when a node is unreachable. /metrics therefore carries the same
// fingerprint, so restrict that endpoint with prometheus.localhost_only or
// a non-empty prometheus.allowed_ips.
var BuildInfo = promauto.NewGaugeVec(
	prometheus.GaugeOpts{
		Name: "jussi_build_info",
		Help: "Build metadata of the running binary (value is always 1)",
	},
	[]string{"commit", "tag"},
)

// SetBuildInfo publishes the build metadata of the running binary.
// Values are expected to be non-empty; callers pass "unknown" when the
// image carries no build args, which still exports a series so a build
// without metadata is visible rather than silently absent.
func SetBuildInfo(commit, tag string) {
	// One series only: a restart with a new image must not leave the
	// previous build's labels behind (same process, new values).
	BuildInfo.Reset()
	BuildInfo.WithLabelValues(commit, tag).Set(1)
}
