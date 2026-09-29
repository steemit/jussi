package telemetry

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// Build metadata of the running binary, taken from the environment the
// image was built with (CI passes SOURCE_COMMIT / DOCKER_TAG as build
// args, so the values travel with the image).
//
// /health and / redact that metadata unless JUSSI_EXPOSE_VERSION=true
// (public endpoints must not fingerprint the deployment), and the
// redacted form is the literal "unknown" — indistinguishable from a
// genuinely missing value. /metrics is the internal, access-restricted
// channel where operators verify which build is actually live, so the
// real values are always exported here.
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
