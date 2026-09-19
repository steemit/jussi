// Package upstream provides a per-upstream circuit breaker.
//
// The breaker exists to protect saturated backends from the
// cancel-and-retry amplification loop observed in the 2026-09-18
// incident: jussi cancels a request at its 3s deadline, but the SQL the
// upstream already started keeps running and holding its DB connection.
// New requests keep arriving and the backend can never drain. A circuit
// breaker converts that state into fast failures, which stops the
// arrival burst, lets the in-flight queries finish, and lets the
// backend recover.
package upstream

import (
	"fmt"
	"math/rand"
	"net/url"
	"sync"
	"time"
)

// BreakerConfig tunes one circuit breaker.
//
// Defaults below were chosen against the 2026-09-18 hivemind storm:
// with ~800 rps per jussi instance the 30s window fills with hundreds
// of samples (no cold-start problem), a 50% failure rate only trips
// once the backend is genuinely saturated, and the 10s open duration
// keeps probe traffic to ~1 req per open cycle instead of a steady
// stream.
type BreakerConfig struct {
	// Window is the length of the sliding failure-rate window.
	Window time.Duration
	// Bucket is the resolution of the sliding window (window is divided
	// into 10 buckets).
	Bucket time.Duration
	// FailureRate is the failure ratio (0..1) at which the breaker opens.
	FailureRate float64
	// MinSamples is the minimum number of requests in the window before
	// the rate is meaningful. Below this the breaker stays closed — a
	// handful of timeouts against a small sample must not trip it.
	MinSamples int
	// OpenDuration is how long the breaker stays open before moving to
	// half-open and admitting a single probe request.
	OpenDuration time.Duration
	// JitterFraction adds up to (JitterFraction * OpenDuration) of random
	// extra open time so several jussi instances do not probe the
	// recovering upstream in lockstep.
	JitterFraction float64
	// Now allows tests to inject a clock. Nil means time.Now.
	Now func() time.Time
}

func (c BreakerConfig) withDefaults() BreakerConfig {
	if c.Window <= 0 {
		c.Window = 30 * time.Second
	}
	if c.Bucket <= 0 {
		c.Bucket = c.Window / 10
	}
	if c.FailureRate <= 0 {
		c.FailureRate = 0.5
	}
	if c.MinSamples <= 0 {
		c.MinSamples = 20
	}
	if c.OpenDuration <= 0 {
		c.OpenDuration = 10 * time.Second
	}
	if c.JitterFraction <= 0 {
		c.JitterFraction = 0.25
	}
	if c.Now == nil {
		c.Now = time.Now
	}
	return c
}

// breakerState is the lifecycle state of a single upstream breaker.
type breakerState int32

const (
	stateClosed breakerState = iota
	stateOpen
	stateHalfOpen
)

// Breaker is a per-upstream circuit breaker with a sliding-window
// failure rate, an open period with jitter, and a single-probe
// half-open state. All methods are safe for concurrent use.
type Breaker struct {
	mu       sync.Mutex
	cfg      BreakerConfig
	state    breakerState
	openedAt time.Time
	// openFor is the (jittered) duration this open period lasts.
	openFor time.Duration
	// probeAdmittedAt is when the current half-open probe was admitted;
	// used by the liveness guard to re-admit if a probe never records.
	probeAdmittedAt time.Time
	// probeID is the generation of the current probe token; incremented
	// each time a probe is admitted so stale tokens are distinguishable.
	probeID uint64
	// buckets is a circular buffer of per-interval counts.
	buckets []bucket
	cur     int
	curEdge time.Time
}

type bucket struct {
	failures int
	total    int
}

// NewBreaker builds a breaker with the given config (zero values are
// replaced by defaults).
func NewBreaker(cfg BreakerConfig) *Breaker {
	cfg = cfg.withDefaults()
	n := int(cfg.Window / cfg.Bucket)
	if n < 1 {
		n = 1
	}
	return &Breaker{
		cfg:     cfg,
		buckets: make([]bucket, n),
	}
}

// Allow reports whether a request to this upstream may proceed. When it
// returns false the caller should fail fast without touching the
// upstream.
//
// In the half-open state exactly one caller receives a non-nil token
// (the probe); everyone else gets (false, nil) until the probe lands.
// The token is what Record uses to attribute the probe's outcome, so a
// slow request admitted before the trip cannot "answer" the probe in
// its place — previously such a stale request could close the breaker
// prematurely (delaying recovery detection) or waste the probe and
// reopen (delaying recovery itself).
func (b *Breaker) Allow() (bool, ProbeToken) {
	b.mu.Lock()
	defer b.mu.Unlock()
	now := b.cfg.Now()
	b.roll(now)

	switch b.state {
	case stateClosed:
		return true, nil
	case stateOpen:
		if now.Sub(b.openedAt) >= b.openFor {
			b.state = stateHalfOpen
			b.probeAdmittedAt = now
			b.probeID++
			return true, probeToken{id: b.probeID}
		}
		return false, nil
	case stateHalfOpen:
		// Only the single admitted probe is in flight; everyone else
		// waits for its outcome.
		//
		// Liveness guard: if the probe never records (lost response,
		// panic in the caller), re-admit after a full open cycle
		// instead of deadlocking half-open forever.
		if now.Sub(b.probeAdmittedAt) >= b.cfg.OpenDuration {
			b.probeAdmittedAt = now
			b.probeID++
			return true, probeToken{id: b.probeID}
		}
		return false, nil
	}
	return true, nil
}

// ProbeToken marks the caller admitted as the half-open probe. It is
// opaque, single-purpose, and nil for non-probe requests.
type ProbeToken interface{ isProbe() }

// probeToken is the concrete ProbeToken implementation. The id ties a
// token to the exact half-open cycle that issued it, so a token from a
// previous cycle cannot answer the current probe.
type probeToken struct{ id uint64 }

func (probeToken) isProbe() {}

// Record reports the outcome of an upstream call. ok is false for
// timeouts, connection failures, and 5xx responses — the failure modes
// that indicate a saturated backend. Client-side cancellations after a
// context deadline count as failures too, which is exactly the signal
// the breaker exists to catch.
//
// token carries the half-open probe identity returned by Allow. Pass it
// only for the request that received it; a non-nil token from a stale
// Allow (one whose request has since completed) is ignored, and a nil
// token never answers a probe.
func (b *Breaker) Record(ok bool, token ProbeToken) {
	b.mu.Lock()
	defer b.mu.Unlock()
	now := b.cfg.Now()
	b.roll(now)

	switch b.state {
	case stateHalfOpen:
		if token == nil {
			// A stale request finished while the probe is in flight.
			// It must not decide the probe's outcome.
			return
		}
		pt, isProbe := token.(probeToken)
		if !isProbe || pt.id != b.probeID {
			// A token from a previous half-open cycle: the request was
			// admitted before the breaker re-opened. Ignore it.
			return
		}
		if ok {
			b.reset()
		} else {
			// Probe failed: reopen for another full cycle.
			b.trip(now)
		}
	default:
		b.buckets[b.cur].total++
		if !ok {
			b.buckets[b.cur].failures++
		}
		if b.failureRate(now) >= b.cfg.FailureRate && b.windowTotal(now) >= b.cfg.MinSamples {
			b.trip(now)
		}
	}
}

// State returns the current state, for metrics and health endpoints.
func (b *Breaker) State() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.roll(b.cfg.Now())
	switch b.state {
	case stateOpen:
		return "open"
	case stateHalfOpen:
		return "half-open"
	default:
		return "closed"
	}
}

// String implements fmt.Stringer for logging.
func (b *Breaker) String() string {
	return fmt.Sprintf("circuit breaker %s", b.State())
}

// failureRate computes the failure ratio over the live window. Caller
// must hold b.mu.
func (b *Breaker) failureRate(now time.Time) float64 {
	total := b.windowTotal(now)
	if total == 0 {
		return 0
	}
	failures := 0
	for _, bk := range b.liveBuckets(now) {
		failures += bk.failures
	}
	return float64(failures) / float64(total)
}

// windowTotal returns the number of recorded requests in the live
// window. Caller must hold b.mu.
func (b *Breaker) windowTotal(now time.Time) int {
	total := 0
	for _, bk := range b.liveBuckets(now) {
		total += bk.total
	}
	return total
}

// liveBuckets returns the buckets that overlap the last cfg.Window. As
// long as roll() is called before every read, all non-empty buckets are
// within the window. Caller must hold b.mu.
func (b *Breaker) liveBuckets(now time.Time) []bucket {
	return b.buckets
}

// roll advances the circular buffer to the bucket covering now,
// clearing any bucket that has fallen out of the window. Caller must
// hold b.mu.
func (b *Breaker) roll(now time.Time) {
	if b.curEdge.IsZero() {
		b.curEdge = now
		return
	}
	elapsed := now.Sub(b.curEdge)
	if elapsed < b.cfg.Bucket {
		return
	}
	steps := int(elapsed / b.cfg.Bucket)
	if steps >= len(b.buckets) {
		// The whole window has gone idle: clear everything.
		for i := range b.buckets {
			b.buckets[i] = bucket{}
		}
		b.cur = 0
		b.curEdge = now
		return
	}
	for i := 0; i < steps; i++ {
		b.cur = (b.cur + 1) % len(b.buckets)
		b.buckets[b.cur] = bucket{}
	}
	b.curEdge = b.curEdge.Add(time.Duration(steps) * b.cfg.Bucket)
}

// trip opens the breaker. Caller must hold b.mu.
func (b *Breaker) trip(now time.Time) {
	b.state = stateOpen
	b.openedAt = now
	jitter := time.Duration(rand.Float64() * b.cfg.JitterFraction * float64(b.cfg.OpenDuration))
	b.openFor = b.cfg.OpenDuration + jitter
}

// reset returns the breaker to closed and clears the window so the
// failure rate that tripped it does not immediately re-trip it.
func (b *Breaker) reset() {
	b.state = stateClosed
	for i := range b.buckets {
		b.buckets[i] = bucket{}
	}
	b.curEdge = b.cfg.Now()
}

// Registry holds one Breaker per upstream URL. It is safe for
// concurrent use; breakers are created lazily on first use.
type Registry struct {
	mu       sync.Mutex
	breakers map[string]*Breaker
	cfg      BreakerConfig
}

// NewRegistry creates an empty breaker registry with the given config.
func NewRegistry(cfg BreakerConfig) *Registry {
	return &Registry{
		breakers: make(map[string]*Breaker),
		cfg:      cfg,
	}
}

// For returns the breaker for an upstream URL along with its registry
// key, creating it if needed. Callers should use the key as the metric
// label so all URL variants of one host share a single series. The URL
// is reduced to scheme://host so pooled upstream URLs (https + ws
// variants of the same host) share one breaker.
func (r *Registry) For(upstreamURL string) (*Breaker, string) {
	key := BreakerKey(upstreamURL)
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.breakers == nil {
		r.breakers = make(map[string]*Breaker)
	}
	b, ok := r.breakers[key]
	if !ok {
		b = NewBreaker(r.cfg)
		r.breakers[key] = b
	}
	return b, key
}

// Snapshot returns state strings for every known breaker, keyed by
// upstream host. Intended for health/metrics endpoints.
func (r *Registry) Snapshot() map[string]string {
	r.mu.Lock()
	defer r.mu.Unlock()
	out := make(map[string]string, len(r.breakers))
	for k, b := range r.breakers {
		out[k] = b.State()
	}
	return out
}

// BreakerKey reduces an upstream URL to its registry/metric key
// (scheme://host) so pooled upstream URLs of one host share a single
// breaker. Exported for callers that must precompute keys without
// touching a breaker — e.g. mapping snapshot keys to hostname-free
// aliases for the public /health payload.
func BreakerKey(rawURL string) string {
	u, err := url.Parse(rawURL)
	if err != nil || u.Host == "" {
		return rawURL
	}
	return u.Scheme + "://" + u.Host
}

// DefaultBreakerConfig returns the production breaker tuning. See
// BreakerConfig for the rationale behind each value.
func DefaultBreakerConfig() BreakerConfig {
	return BreakerConfig{
		Window:         30 * time.Second,
		Bucket:         3 * time.Second,
		FailureRate:    0.5,
		MinSamples:     20,
		OpenDuration:   10 * time.Second,
		JitterFraction: 0.25,
	}
}
