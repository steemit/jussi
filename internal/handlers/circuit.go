package handlers

import (
	"log/slog"
	"time"

	"github.com/steemit/jussi/internal/config"
	jussiErrors "github.com/steemit/jussi/internal/errors"
	"github.com/steemit/jussi/internal/telemetry"
	"github.com/steemit/jussi/internal/upstream"
)

// breakerConfig converts the viper-facing config.CircuitConfig into the
// breaker's runtime config, falling back to the tuned defaults for any
// unset value. Lives here (not in config) to keep the config package
// free of upstream internals.
func breakerConfig(cfg config.CircuitConfig) upstream.BreakerConfig {
	out := upstream.DefaultBreakerConfig()
	if cfg.Window > 0 {
		out.Window = time.Duration(cfg.Window) * time.Second
	}
	if cfg.FailureRate > 0 {
		out.FailureRate = cfg.FailureRate
	}
	if cfg.MinSamples > 0 {
		out.MinSamples = cfg.MinSamples
	}
	if cfg.OpenDuration > 0 {
		out.OpenDuration = time.Duration(cfg.OpenDuration) * time.Second
	}
	if cfg.JitterFraction > 0 {
		out.JitterFraction = cfg.JitterFraction
	}
	return out
}

// upstreamAdmission is the circuit breaker state carried by exactly one
// upstream call: the breaker to report the outcome to, its metric label,
// and — when this call was admitted as the half-open probe — the token
// that ties its outcome to that probe.
type upstreamAdmission struct {
	breaker    *upstream.Breaker
	breakerKey string
	probeToken upstream.ProbeToken
}

// admitUpstream runs the admission half of the circuit breaker protocol
// for one upstream call: it consults the breaker, fails fast when the
// upstream's circuit is open, and hands back the admission the caller must
// report its outcome to.
//
// kind is "request" or "sub-request"; it only shapes the server-side log
// line and the internal error detail, both of which stay hostname-free.
//
// The error is non-nil only when the caller must not dial the upstream. The
// returned admission is valid — and must receive a record() call — only
// when the error is nil.
//
// Both breaker call sites (callHTTPUpstream and callSteemd) share this
// helper deliberately: a copy of this logic is what caused the 2026-09-25
// incident, where one site nilled probeToken unconditionally and stranded a
// half-open breaker for four days (every request rejected, the admitted
// probe's success never attributed).
func (p *RequestProcessor) admitUpstream(url, kind, method string) (upstreamAdmission, error) {
	breaker, breakerKey := p.breakers.For(url)
	allowed, probeToken := breaker.Allow()

	if !allowed && p.circuitEnabled {
		telemetry.UpstreamCircuitRejects.WithLabelValues(breakerKey).Inc()
		telemetry.UpstreamCircuitState.WithLabelValues(breakerKey).Set(breakerStateValue(breaker))
		// The upstream identity (breakerKey) goes to the metric label
		// and this server-side log only — the client-facing error must
		// not carry the hostname.
		slog.Warn("circuit open: "+kind+" rejected without dialing upstream",
			"upstream", breakerKey,
			"method", method,
		)
		return upstreamAdmission{}, jussiErrors.NewUpstreamCircuitOpenError(
			"circuit breaker open; " + kind + " rejected without dialing upstream")
	}

	if !p.circuitEnabled {
		// Kill switch: the breaker may still sit open/half-open from an
		// earlier enabled period, but the operator has opted out of
		// honouring it, so this call proceeds regardless. The token is
		// dropped with it — this path never gated the call, so its
		// outcome must not be attributed to a half-open probe
		// admission.
		probeToken = nil
	}

	return upstreamAdmission{breaker: breaker, breakerKey: breakerKey, probeToken: probeToken}, nil
}

// record feeds one upstream call's outcome back to the breaker and
// refreshes the exported state gauge. The probe token is what lets a
// successful half-open probe close the breaker: recording a probe admission
// with a nil token is ignored by the breaker and leaves it half-open
// forever.
func (a upstreamAdmission) record(ok bool) {
	a.breaker.Record(ok, a.probeToken)
	telemetry.UpstreamCircuitState.WithLabelValues(a.breakerKey).Set(breakerStateValue(a.breaker))
}
