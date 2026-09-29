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
// genuinely missing value. Exporting it here instead keeps the public
// payload unchanged, at the cost that /metrics now carries the
// fingerprint for every caller it admits: restrict that endpoint with
// prometheus.localhost_only / prometheus.allowed_ips, because the values
// are exported regardless of JUSSI_EXPOSE_VERSION.
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
