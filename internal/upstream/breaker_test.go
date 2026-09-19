package upstream

import (
	"testing"
	"time"
)

// fakeClock returns a controllable clock for breaker tests.
type fakeClock struct {
	now time.Time
}

func (c *fakeClock) Now() time.Time { return c.now }

func (c *fakeClock) advance(d time.Duration) { c.now = c.now.Add(d) }

func testConfig(clock *fakeClock) BreakerConfig {
	return BreakerConfig{
		Window:       30 * time.Second,
		Bucket:       3 * time.Second,
		FailureRate:  0.5,
		MinSamples:   20,
		OpenDuration: 10 * time.Second,
		Now:          clock.Now,
	}
}

func TestBreakerStaysClosedUnderLowFailureRate(t *testing.T) {
	clock := &fakeClock{now: time.Unix(0, 0)}
	b := NewBreaker(testConfig(clock))

	// 80 successes + 20% failures: under the 50% threshold.
	for i := 0; i < 80; i++ {
		if allowed, _ := b.Allow(); !allowed {
			t.Fatalf("request %d rejected while breaker should be closed", i)
		}
		b.Record(true, nil)
	}
	for i := 0; i < 19; i++ {
		b.Allow()
		b.Record(false, nil)
	}
	if got := b.State(); got != "closed" {
		t.Fatalf("expected closed, got %s", got)
	}
}

func TestBreakerOpensAtFailureRate(t *testing.T) {
	clock := &fakeClock{now: time.Unix(0, 0)}
	b := NewBreaker(testConfig(clock))

	// Fill the window with a mixed history, then fail hard. The breaker
	// trips as soon as the ratio reaches 50% (>= threshold), which may
	// happen mid-loop — walk until a request is rejected and assert the
	// open state.
	for i := 0; i < 20; i++ {
		b.Allow()
		b.Record(true, nil)
	}
	tripped := false
	for i := 0; i < 25; i++ {
		if allowed, _ := b.Allow(); !allowed {
			tripped = true
			break
		}
		b.Record(false, nil)
	}
	if !tripped {
		t.Fatal("breaker never rejected a request despite >=50% failure rate")
	}
	if got := b.State(); got != "open" {
		t.Fatalf("expected open, got %s", got)
	}
}

func TestBreakerNeedsMinSamples(t *testing.T) {
	clock := &fakeClock{now: time.Unix(0, 0)}
	b := NewBreaker(testConfig(clock))

	// A handful of failures with no history must not trip the breaker.
	for i := 0; i < 10; i++ {
		if allowed, _ := b.Allow(); !allowed {
			t.Fatalf("request rejected with insufficient samples")
		}
		b.Record(false, nil)
	}
	if got := b.State(); got != "closed" {
		t.Fatalf("expected closed below MinSamples, got %s", got)
	}
}

func TestBreakerRejectsWhileOpenThenHalfOpens(t *testing.T) {
	clock := &fakeClock{now: time.Unix(0, 0)}
	b := NewBreaker(testConfig(clock))

	for i := 0; i < 40; i++ {
		b.Allow()
		b.Record(false, nil)
	}
	if got := b.State(); got != "open" {
		t.Fatalf("expected open, got %s", got)
	}

	// Every request during the open window is rejected.
	clock.advance(5 * time.Second)
	if allowed, _ := b.Allow(); allowed {
		t.Fatal("Allow returned true while breaker open")
	}

	// After the open duration the breaker admits exactly one probe.
	clock.advance(15 * time.Second) // 10s open + up to 25% jitter
	admitted := 0
	var probeToken ProbeToken
	for i := 0; i < 10; i++ {
		allowed, tok := b.Allow()
		if allowed {
			admitted++
			probeToken = tok
		}
	}
	_ = probeToken
	if admitted != 1 {
		t.Fatalf("half-open should admit exactly one probe, admitted %d", admitted)
	}
	if got := b.State(); got != "half-open" {
		t.Fatalf("expected half-open, got %s", got)
	}

	// Concurrent callers are rejected while the probe is in flight.
	if allowed, _ := b.Allow(); allowed {
		t.Fatal("Allow returned true while probe in flight")
	}
}

func TestBreakerClosesOnSuccessfulProbe(t *testing.T) {
	clock := &fakeClock{now: time.Unix(0, 0)}
	b := NewBreaker(testConfig(clock))

	for i := 0; i < 40; i++ {
		b.Allow()
		b.Record(false, nil)
	}
	clock.advance(15 * time.Second)
	_, tok := b.Allow() // probe admitted

	// A successful probe closes the breaker and clears the window.
	b.Record(true, tok)
	if got := b.State(); got != "closed" {
		t.Fatalf("expected closed after successful probe, got %s", got)
	}

	// The window was cleared: a few failures right after must not re-trip.
	for i := 0; i < 5; i++ {
		if allowed, _ := b.Allow(); !allowed {
			t.Fatalf("request rejected right after recovery")
		}
		b.Record(false, nil)
	}
	if got := b.State(); got != "closed" {
		t.Fatalf("expected closed after isolated failures, got %s", got)
	}
}

func TestBreakerReopensOnFailedProbe(t *testing.T) {
	clock := &fakeClock{now: time.Unix(0, 0)}
	b := NewBreaker(testConfig(clock))

	for i := 0; i < 40; i++ {
		b.Allow()
		b.Record(false, nil)
	}
	clock.advance(15 * time.Second)
	_, tok := b.Allow() // probe admitted
	b.Record(false, tok)

	if got := b.State(); got != "open" {
		t.Fatalf("expected open after failed probe, got %s", got)
	}
	if allowed, _ := b.Allow(); allowed {
		t.Fatal("Allow returned true immediately after failed probe")
	}
}

func TestBreakerWindowSlides(t *testing.T) {
	clock := &fakeClock{now: time.Unix(0, 0)}
	b := NewBreaker(testConfig(clock))

	// All failures, but then the window slides past them.
	for i := 0; i < 40; i++ {
		b.Allow()
		b.Record(false, nil)
	}
	clock.advance(45 * time.Second) // longer than the 30s window

	// Failures aged out; fresh successes keep the breaker closed. The
	// breaker may still be open (or half-open) from the earlier
	// failures — Allow is state-dependent — so complete the probe
	// properly and keep looping until the breaker closes.
	probeDone := false
	for i := 0; i < 25; i++ {
		allowed, tok := b.Allow()
		if !allowed {
			t.Fatalf("request %d rejected after window slide", i)
		}
		b.Record(true, tok)
		clock.advance(time.Second)
		if tok != nil {
			probeDone = true
		}
		if probeDone {
			break // probe success closed the breaker
		}
	}
	if got := b.State(); got != "closed" {
		t.Fatalf("expected closed after window slide, got %s", got)
	}
}

func TestBreakerRegistryPerHost(t *testing.T) {
	r := NewRegistry(BreakerConfig{})
	a := r.For("https://beta-hivemind.steemit.com")
	b := r.For("https://beta-hivemind.steemit.com/")
	c := r.For("https://steemd.steemit.com")
	if a != b {
		t.Fatal("same upstream host must share one breaker")
	}
	if a == c {
		t.Fatal("different upstream hosts must not share a breaker")
	}
	snap := r.Snapshot()
	if len(snap) != 2 {
		t.Fatalf("expected 2 breakers in snapshot, got %d", len(snap))
	}
}

func TestBreakerStaleRequestCannotAnswerProbe(t *testing.T) {
	clock := &fakeClock{now: time.Unix(0, 0)}
	b := NewBreaker(testConfig(clock))

	// Trip the breaker with one request still conceptually in flight
	// (it holds no token because it was admitted while closed).
	for i := 0; i < 40; i++ {
		b.Allow()
		b.Record(false, nil)
	}
	clock.advance(15 * time.Second)

	// The real probe is admitted.
	_, tok := b.Allow()

	// A stale request (nil token) lands in the half-open window. It
	// must neither close nor reopen the breaker.
	b.Record(true, nil)
	if got := b.State(); got != "half-open" {
		t.Fatalf("stale success must not close the breaker, got %s", got)
	}
	b.Record(false, nil)
	if got := b.State(); got != "half-open" {
		t.Fatalf("stale failure must not reopen the breaker, got %s", got)
	}

	// Only the genuine probe decides.
	b.Record(false, tok)
	if got := b.State(); got != "open" {
		t.Fatalf("expected open after failed probe, got %s", got)
	}
}

func TestBreakerTokenOnlyValidForOneProbe(t *testing.T) {
	clock := &fakeClock{now: time.Unix(0, 0)}
	b := NewBreaker(testConfig(clock))

	for i := 0; i < 40; i++ {
		b.Allow()
		b.Record(false, nil)
	}
	clock.advance(15 * time.Second)
	_, tok1 := b.Allow()

	// Probe 1 fails: breaker reopens.
	b.Record(false, tok1)

	// Next half-open cycle admits a NEW probe; the old token must not
	// be able to answer it.
	clock.advance(15 * time.Second)
	_, tok2 := b.Allow()
	if tok1 == tok2 {
		t.Fatal("each probe must receive a distinct token")
	}
	b.Record(true, tok1)
	if got := b.State(); got != "half-open" {
		t.Fatalf("stale token must not answer the new probe, got %s", got)
	}
	b.Record(true, tok2)
	if got := b.State(); got != "closed" {
		t.Fatalf("expected closed after genuine probe success, got %s", got)
	}
}

func TestBreakerHalfOpenLivenessGuard(t *testing.T) {
	clock := &fakeClock{now: time.Unix(0, 0)}
	b := NewBreaker(testConfig(clock))

	for i := 0; i < 40; i++ {
		b.Allow()
		b.Record(false, nil)
	}
	clock.advance(15 * time.Second)
	_, tok1 := b.Allow()

	// The probe never records. After one open cycle the breaker must
	// admit a new probe instead of deadlocking in half-open.
	clock.advance(15 * time.Second)
	allowed, tok2 := b.Allow()
	if !allowed {
		t.Fatal("liveness guard must re-admit a probe when the previous one never records")
	}
	if tok2 == nil {
		t.Fatal("re-admitted probe must carry a token")
	}
	_ = tok1
}
