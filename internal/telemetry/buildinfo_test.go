package telemetry

import (
	"strings"
	"testing"

	"github.com/prometheus/client_golang/prometheus/testutil"
)

// expectBuildInfo asserts the metric exposes exactly this one series.
// CollectAndCompare on the whole GaugeVec (rather than reading a single
// WithLabelValues child) is what catches stale labels: a child created
// for a previous build still exports, with value 0, until it is reset.
func expectBuildInfo(t *testing.T, commit, tag string) {
	t.Helper()
	want := `# HELP jussi_build_info Build metadata of the running binary (value is always 1)
# TYPE jussi_build_info gauge
jussi_build_info{commit="` + commit + `",tag="` + tag + `"} 1
`
	if err := testutil.CollectAndCompare(BuildInfo, strings.NewReader(want)); err != nil {
		t.Fatalf("unexpected jussi_build_info exposition: %v", err)
	}
}

func TestSetBuildInfoExportsSingleSeries(t *testing.T) {
	SetBuildInfo("404bc29", "next-404bc29")

	expectBuildInfo(t, "404bc29", "next-404bc29")
}

// A redeploy inside the same process must not leave the previous
// build's labels exportable.
func TestSetBuildInfoReplacesPreviousBuild(t *testing.T) {
	SetBuildInfo("758133f", "next-758133f")
	SetBuildInfo("404bc29", "next-404bc29")

	expectBuildInfo(t, "404bc29", "next-404bc29")
}

// An image built without CI build args reports "unknown" rather than
// exporting nothing — operators must be able to tell the two apart on
// /metrics, since /health shows "unknown" for both redacted and absent.
func TestSetBuildInfoExportsUnknownMetadata(t *testing.T) {
	SetBuildInfo("unknown", "unknown")

	expectBuildInfo(t, "unknown", "unknown")
}
