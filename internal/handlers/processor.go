package handlers

import (
	"context"
	"fmt"
	"log/slog"
	"strings"
	"sync"
	"time"

	"github.com/steemit/jussi/internal/cache"
	"github.com/steemit/jussi/internal/config"
	jussiErrors "github.com/steemit/jussi/internal/errors"
	"github.com/steemit/jussi/internal/helpers"
	"github.com/steemit/jussi/internal/middleware"
	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/telemetry"
	"github.com/steemit/jussi/internal/upstream"
	"github.com/steemit/jussi/internal/validators"
	"github.com/steemit/jussi/internal/ws"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

// Import metrics for direct access
var (
	CacheOperations         = telemetry.CacheOperations
	UpstreamRequests        = telemetry.UpstreamRequests
	UpstreamRequestDuration = telemetry.UpstreamRequestDuration
	UpstreamErrors          = telemetry.UpstreamErrors
	RequestsTotal           = telemetry.RequestsTotal
	BatchSize               = telemetry.BatchSize
)

// Upstream timeout policy.
//
// defaultUpstreamTimeout is the fallback when the upstream config sets
// timeout=0 (no per-URN entry matched). 15s covers ~5 Steem blocks and
// keeps idempotent reads from hanging forever if a per-URN timeout was
// forgotten.
//
// broadcastMinimumTimeout is the lower bound for broadcast_transaction*
// methods regardless of config. Synchronous broadcast must wait for a
// block (~3s on Steem); when an upstream node is slow or hung, ALB will
// keep the connection open and jussi must wait until it succeeds or until
// the timeout fires. Legacy jussi had timeout=0 (no limit) here and used
// retry to mask hung backends — we keep a finite limit but raise it to
// 30s so the request can survive ~10 blocks of upstream slowness without
// being clipped, which is what surfaces as "broadcast timeout" to wallets.
const (
	defaultUpstreamTimeout  = 15 * time.Second
	broadcastMinimumTimeout = 30 * time.Second
)

// selectUpstreamTimeout resolves the effective upstream timeout for a request.
// It honours the configured per-URN timeout, falls back to defaultUpstreamTimeout
// when unset, and raises broadcast_transaction* requests to at least
// broadcastMinimumTimeout regardless of config (since clipping a synchronous
// broadcast can leave the transaction in flight on the upstream while the
// caller retries with a fresh expiration).
//
// When the broadcast floor actually overrides a smaller configured value
// it logs once per method per broadcastFloorLogInterval — operators want
// to know a config typo (or a too-aggressive timeout) is being silently
// rescued by the safety net, but only once, not on every request.
func selectUpstreamTimeout(req *request.JSONRPCRequest) time.Duration {
	var configured time.Duration
	if req != nil && req.Upstream != nil {
		configured = time.Duration(req.Upstream.Timeout) * time.Second
	}
	timeout := configured
	if timeout <= 0 {
		timeout = defaultUpstreamTimeout
	}
	if validators.IsBroadcastTransactionRequest(req) && timeout < broadcastMinimumTimeout {
		method := "unknown"
		if req != nil && req.URN != nil {
			method = req.URN.Method
		}
		if shouldLogBroadcastFloor(method) {
			slog.Info("broadcast upstream timeout floored",
				"method", method,
				"configured_s", configured.Seconds(),
				"applied_s", broadcastMinimumTimeout.Seconds(),
			)
		}
		timeout = broadcastMinimumTimeout
	}
	return timeout
}

// broadcastFloorLogInterval throttles "timeout floored" logs to one
// emission per method per interval. The point is observability, not a
// per-request audit trail.
const broadcastFloorLogInterval = time.Minute

var broadcastFloorLastLog sync.Map // map[string]time.Time keyed by method

func shouldLogBroadcastFloor(method string) bool {
	now := time.Now()
	for {
		actual, loaded := broadcastFloorLastLog.Load(method)
		if loaded {
			if lastT, ok := actual.(time.Time); ok && now.Sub(lastT) < broadcastFloorLogInterval {
				return false
			}
			if broadcastFloorLastLog.CompareAndSwap(method, actual, now) {
				return true
			}
		} else {
			if _, loaded := broadcastFloorLastLog.LoadOrStore(method, now); !loaded {
				return true
			}
		}
	}
}

// RequestProcessor processes JSON-RPC requests
type RequestProcessor struct {
	cacheGroup *cache.CacheGroup
	router     *upstream.Router
	httpClient *upstream.HTTPClient
	// breakers holds one circuit breaker per upstream host. When an
	// upstream is saturated (deadlines, connection errors, 5xx), the
	// breaker stops new requests from piling onto it: jussi cancels at
	// its deadline, but the upstream keeps executing the SQL it already
	// started, so unthrottled arrivals turn one slow backend into an
	// outage (2026-09-18 hivemind storm). Fail fast instead and let the
	// backend drain.
	breakers *upstream.Registry
	// circuitEnabled mirrors the config flag; checked on every call so
	// the breaker can be disabled via env var without a restart path in
	// code (new instances pick it up; disabling mid-flight requires the
	// next deploy, matching every other jussi config knob).
	circuitEnabled bool
}

// NewRequestProcessor creates a new request processor
func NewRequestProcessor(
	cacheGroup *cache.CacheGroup,
	router *upstream.Router,
	httpClient *upstream.HTTPClient,
	wsPools map[string]*ws.Pool, // TODO: WebSocket support - temporarily disabled, can be nil
	circuitCfg config.CircuitConfig,
) *RequestProcessor {
	return &RequestProcessor{
		cacheGroup:     cacheGroup,
		router:         router,
		httpClient:     httpClient,
		breakers:       upstream.NewRegistry(breakerConfig(circuitCfg)),
		circuitEnabled: circuitCfg.Enabled,
		// TODO: WebSocket support - temporarily disabled
		// wsPools:    wsPools,
	}
}

// translateToAppbase converts legacy condenser-era request formats to the
// appbase namespaced format when an appbase-style upstream is configured with
// translate_to_appbase: true.
//
// Only requests that use a legacy wire format are rewritten — i.e. the params
// are positional (or absent): bare methods ("get_block"), call-style triples
// (["database_api","get_block",args] or [0,"get_block",args]) and api-prefixed
// methods with positional args ("database_api.get_state" with ["/trending"]).
// appbase nodes only accept that wire format on condenser_api, so these are
// rewritten to their condenser_api equivalent:
//
//	"get_block"                          → "condenser_api.get_block"
//	["database_api","get_block",args]    → ["condenser_api","get_block",args]
//
// Requests already in appbase format — named (JSON object) params, e.g.
// database_api.find_accounts with {"accounts":[...]} — are forwarded with
// their target API unchanged. Rewriting those would break every method that
// exists on an appbase API but not on condenser_api (find_accounts,
// list_votes, ...), which surfaced as
// "Could not find method find_accounts" errors.
//
// URN.Namespace is switched to "appbase" on translation so routing matches
// config entries like "appbase.condenser_api.get_state" (→ hivemind) instead
// of falling through to the generic steemd upstream.
func translateToAppbase(jsonrpcReq *request.JSONRPCRequest, router *upstream.Router) {
	api := jsonrpcReq.URN.API
	if api == "condenser_api" || api == "jsonrpc" {
		return
	}

	// Translation only applies to requests destined for the steemd/appbase
	// upstreams. Other namespaces (hivemind bridge.*, overseer, ...) are
	// different services and must be forwarded exactly as received.
	switch jsonrpcReq.URN.Namespace {
	case "steemd":
		if !router.ShouldTranslateToAppbase("steemd") {
			return
		}
	case "appbase":
		// Direct *_api.method requests can use the legacy positional format
		// too; honor either the steemd or appbase upstream flag.
		if !router.ShouldTranslateToAppbase("steemd") && !router.ShouldTranslateToAppbase("appbase") {
			return
		}
	default:
		return
	}

	// Named params mean the request is already in appbase format; the target
	// API must not be changed.
	if isNamedParams(jsonrpcReq.URN.Params) {
		return
	}

	jsonrpcReq.URN.API = "condenser_api"
	jsonrpcReq.URN.Namespace = "appbase"

	if jsonrpcReq.Method == "call" {
		if paramsSlice, ok := jsonrpcReq.Params.([]interface{}); ok && len(paramsSlice) > 0 {
			switch paramsSlice[0].(type) {
			case string, float64, int:
				// string API name ("database_api") or pre-appbase numeric
				// API index (0=database_api, 1=login_api)
				paramsSlice[0] = "condenser_api"
			}
		}
		return
	}

	// Rebuild the method from the parsed URN so bare ("get_block") and
	// api-prefixed ("database_api.get_block", "steemd.database_api.get_block")
	// methods all become a valid namespaced appbase method.
	jsonrpcReq.Method = "condenser_api." + jsonrpcReq.URN.Method
}

// isNamedParams reports whether the method params are a JSON object, which is
// the appbase wire format (legacy condenser clients send positional arrays).
func isNamedParams(params interface{}) bool {
	_, ok := params.(map[string]interface{})
	return ok
}

// ProcessSingleRequest processes a single JSON-RPC request
func (p *RequestProcessor) ProcessSingleRequest(ctx context.Context, jsonrpcReq *request.JSONRPCRequest) (map[string]interface{}, error) {
	// Create span for request processing
	ctx, span := telemetry.StartSpan(ctx, "jussi.process_request",
		trace.WithSpanKind(trace.SpanKindInternal),
	)
	defer span.End()

	// Translate API calls to condenser_api when the upstream requires appbase format.
	translateToAppbase(jsonrpcReq, p.router)

	// TEMPORARY WORKAROUND: Intercept get_state with unsupported paths.
	// There are two categories:
	//   1. Sub-paths like /@user/transfers that steemd returns "Invalid parameters" for
	//   2. Special paths like /~witnesses and /proposals that steemd returns -32000 for
	//
	// ALL of these workarounds will be removed once the condenser rewrite and
	// wallet rewrite are deployed. The new versions do not use get_state at all.
	// See get_state_workaround.go for full documentation.
	// TODO: Remove this entire block after condenser rewrite + wallet rewrite launch.
	if username, subPath, ok := isGetStateUnsupportedSubPath(jsonrpcReq); ok {
		slog.Debug("get_state workaround: sub-path intercepted",
			"username", username, "subPath", subPath)
		span.SetAttributes(attribute.String("jussi.workaround", "get_state_subpath"))
		span.SetAttributes(attribute.String("jussi.workaround.subpath", subPath))
		span.SetAttributes(attribute.String("jussi.workaround.username", username))

		resp, err := p.emulateGetStateSubPath(ctx, jsonrpcReq, username, subPath)
		if err != nil {
			telemetry.RecordSpanError(span, err)
			RequestsTotal.WithLabelValues(jsonrpcReq.URN.Namespace, jsonrpcReq.URN.Method, "workaround_error").Inc()
			return nil, fmt.Errorf("get_state workaround failed: %w", err)
		}
		RequestsTotal.WithLabelValues(jsonrpcReq.URN.Namespace, jsonrpcReq.URN.Method, "workaround_success").Inc()
		return resp, nil
	}

	if pathType, ok := isGetStateSpecialPath(jsonrpcReq); ok {
		slog.Debug("get_state workaround: special path intercepted",
			"pathType", pathType)
		span.SetAttributes(attribute.String("jussi.workaround", "get_state_special_path"))
		span.SetAttributes(attribute.String("jussi.workaround.path_type", pathType))

		resp, err := p.emulateGetStateSpecialPath(ctx, jsonrpcReq, pathType)
		if err != nil {
			telemetry.RecordSpanError(span, err)
			RequestsTotal.WithLabelValues(jsonrpcReq.URN.Namespace, jsonrpcReq.URN.Method, "workaround_error").Inc()
			return nil, fmt.Errorf("get_state special path workaround failed: %w", err)
		}
		RequestsTotal.WithLabelValues(jsonrpcReq.URN.Namespace, jsonrpcReq.URN.Method, "workaround_success").Inc()
		return resp, nil
	}

	// Add span attributes
	telemetry.AddSpanAttributes(span, map[string]string{
		"jussi.namespace":  jsonrpcReq.URN.Namespace,
		"jussi.api":        jsonrpcReq.URN.API,
		"jussi.method":     jsonrpcReq.URN.Method,
		"jussi.request_id": jsonrpcReq.JussiRequestID,
	})

	// Record request parameters as span event (shows in Logs section)
	telemetry.RecordSpanParams(span, jsonrpcReq.Params)

	// Get upstream configuration
	upstreamConfig, found := p.router.GetUpstream(jsonrpcReq.URN.String())
	if !found {
		err := fmt.Errorf("no upstream configuration found for namespace: %s (URN: %s)", jsonrpcReq.URN.Namespace, jsonrpcReq.URN.String())
		telemetry.RecordSpanError(span, err)
		return nil, err
	}

	// Convert upstream.Upstream to request.UpstreamConfig
	jsonrpcReq.Upstream = &request.UpstreamConfig{
		URL:     upstreamConfig.URL,
		TTL:     upstreamConfig.TTL,
		Timeout: upstreamConfig.Timeout,
	}

	ttl := upstreamConfig.TTL
	span.SetAttributes(attribute.String("jussi.upstream.url", upstreamConfig.URL))
	span.SetAttributes(attribute.Int("jussi.upstream.ttl", ttl))

	// Check cache if TTL is not -1 (no cache)
	if cache.IsCacheable(ttl) {
		ctx, cacheSpan := telemetry.StartSpan(ctx, "jussi.cache.lookup")
		cacheKey := cache.GenerateCacheKey(jsonrpcReq.URN)
		cachedValue, err := p.cacheGroup.Get(ctx, cacheKey)
		cacheSpan.End()

		if err == nil && cachedValue != nil {
			// Cache hit
			span.SetAttributes(attribute.Bool("jussi.cache.hit", true))
			CacheOperations.WithLabelValues("get", "hit").Inc()

			if cachedResp, ok := cachedValue.(map[string]interface{}); ok {
				// Deep copy the cached response to avoid data races when
				// concurrent batch requests modify the "id" field on the
				// same cached map reference (Go maps are not concurrency-safe).
				resp := helpers.DeepCopyMap(cachedResp)
				resp["id"] = jsonrpcReq.ID
				telemetry.SetSpanSuccess(span)
				return resp, nil
			}
		}
		span.SetAttributes(attribute.Bool("jussi.cache.hit", false))
		CacheOperations.WithLabelValues("get", "miss").Inc()
	}

	// Cache miss - call upstream
	var response map[string]interface{}
	var err error
	upstreamURL := upstreamConfig.URL

	startTime := time.Now()
	// TODO: WebSocket support - temporarily disabled
	// if strings.HasPrefix(upstreamURL, "ws://") || strings.HasPrefix(upstreamURL, "wss://") {
	// 	// WebSocket upstream
	// 	ctx, wsSpan := telemetry.StartSpan(ctx, "jussi.upstream.websocket")
	// 	response, err = p.callWebSocketUpstream(ctx, jsonrpcReq, upstreamURL)
	// 	wsSpan.End()
	// 	UpstreamRequests.WithLabelValues(upstreamURL, "websocket").Inc()
	// } else {
	// HTTP upstream
	ctx, httpSpan := telemetry.StartSpan(ctx, "jussi.upstream.http")
	response, err = p.callHTTPUpstream(ctx, jsonrpcReq, upstreamURL)
	httpSpan.End()
	UpstreamRequests.WithLabelValues(upstreamURL, "http").Inc()
	// }
	duration := time.Since(startTime).Seconds()
	UpstreamRequestDuration.WithLabelValues(upstreamURL, getProtocol(upstreamURL)).Observe(duration)

	if err != nil {
		telemetry.RecordSpanError(span, err)
		UpstreamErrors.WithLabelValues(upstreamURL, getProtocol(upstreamURL), "error").Inc()
		return nil, fmt.Errorf("upstream call failed: %w", err)
	}

	// Cache response if cacheable
	if cache.IsCacheable(ttl) {
		ctx, cacheSpan := telemetry.StartSpan(ctx, "jussi.cache.store")
		cacheKey := cache.GenerateCacheKey(jsonrpcReq.URN)

		// Calculate TTL based on irreversibility if needed
		var cacheTTL time.Duration
		if ttl == cache.TTLExpireIfIrreversible {
			// Get last irreversible block number from tracker
			tracker := middleware.GetBlockNumberTracker()
			lastIrreversibleBlockNum := tracker.GetLastIrreversibleBlockNum()
			irreversibleTTL := cache.IrreversibleTTL(response, lastIrreversibleBlockNum)
			cacheTTL = cache.CalculateTTL(irreversibleTTL, false, lastIrreversibleBlockNum)
		} else {
			cacheTTL = cache.CalculateTTL(ttl, false, 0)
		}

		if cacheTTL > 0 || ttl == cache.TTLNoExpire {
			// Store a copy without the request-specific "id" so that
			// future cache hits don't carry a stale id.  The "id" is
			// per-request and must be injected at read time (above).
			cacheEntry := helpers.DeepCopyMap(response)
			delete(cacheEntry, "id")
			_ = p.cacheGroup.Set(ctx, cacheKey, cacheEntry, cacheTTL)
			cacheSpan.End()
			CacheOperations.WithLabelValues("set", "success").Inc()
		} else {
			cacheSpan.End()
			CacheOperations.WithLabelValues("set", "skipped").Inc()
		}
	}

	// Ensure response has correct ID
	response["id"] = jsonrpcReq.ID

	// If response contains an error, add trace ID to error data
	if errField, ok := response["error"].(map[string]interface{}); ok {
		// Get trace ID from context
		if spanCtx := span.SpanContext(); spanCtx.IsValid() {
			traceID := spanCtx.TraceID().String()

			// Get or create error data
			var errorData map[string]interface{}
			if data, exists := errField["data"]; exists {
				if dataMap, ok := data.(map[string]interface{}); ok {
					errorData = dataMap
				} else {
					errorData = make(map[string]interface{})
				}
			} else {
				errorData = make(map[string]interface{})
			}

			// Add trace ID to error data
			errorData["trace_id"] = traceID

			// Add jussi_request_id if available
			if jsonrpcReq.JussiRequestID != "" {
				errorData["jussi_request_id"] = jsonrpcReq.JussiRequestID
			}

			// Update error data in response
			errField["data"] = errorData
		}

		// Mark span as error
		telemetry.RecordSpanError(span, fmt.Errorf("upstream returned error: %v", errField["message"]))
		RequestsTotal.WithLabelValues(jsonrpcReq.URN.Namespace, jsonrpcReq.URN.Method, "error").Inc()

		// For broadcast methods, emit a structured warn log alongside the
		// span. Broadcast traffic is low-volume and these errors are the
		// signal operators actually need to correlate "wallets are seeing
		// failed transactions" with an upstream incident — without paging
		// through jaeger trace by trace.
		if validators.IsBroadcastTransactionRequest(jsonrpcReq) {
			slog.Warn("broadcast upstream returned error",
				"method", jsonrpcReq.URN.Method,
				"namespace", jsonrpcReq.URN.Namespace,
				"upstream_url", upstreamURL,
				"jussi_request_id", jsonrpcReq.JussiRequestID,
				"upstream_message", fmt.Sprintf("%v", errField["message"]),
			)
		}
	} else {
		telemetry.SetSpanSuccess(span)
		RequestsTotal.WithLabelValues(jsonrpcReq.URN.Namespace, jsonrpcReq.URN.Method, "success").Inc()
	}

	return response, nil
}

// getProtocol extracts protocol from URL
func getProtocol(url string) string {
	if strings.HasPrefix(url, "ws://") || strings.HasPrefix(url, "wss://") {
		return "websocket"
	}
	return "http"
}

// callHTTPUpstream calls HTTP upstream with policy tuned to the request type:
//   - broadcast_transaction* methods are non-idempotent and MUST NOT be
//     retried (a transient transport error could otherwise cause the same
//     transaction to be submitted twice). They get a single attempt with
//     the broadcast-minimum timeout enforced by selectUpstreamTimeout.
//   - All other methods are treated as idempotent and use RequestWithRetry
//     with DefaultRetryConfig (≤2 attempts, ~100-500ms backoff). This
//     mirrors what legacy jussi did to mask transient ALB/steemd blips,
//     but with a tight enough budget to avoid the expiration-on-retry
//     pattern that motivated commit 9cf36ea.
func (p *RequestProcessor) callHTTPUpstream(ctx context.Context, jsonrpcReq *request.JSONRPCRequest, url string) (map[string]interface{}, error) {
	// Circuit breaker: when an upstream is saturated, fail fast instead
	// of queueing another request behind the pile-up. See
	// RequestProcessor.breakers for why this matters. When the circuit
	// is disabled via config (upstream.circuit.enabled=false) every
	// Allow returns true and Record is a no-op window write.
	breaker, breakerKey := p.breakers.For(url)
	allowed, probeToken := breaker.Allow()
	if !allowed && p.circuitEnabled {
		telemetry.UpstreamCircuitRejects.WithLabelValues(breakerKey).Inc()
		telemetry.UpstreamCircuitState.WithLabelValues(breakerKey).Set(breakerStateValue(breaker))
		// The upstream identity (breakerKey) goes to the metric label
		// and this server-side log only — the client-facing error must
		// not carry the hostname.
		slog.Warn("circuit open: request rejected without dialing upstream",
			"upstream", breakerKey,
			"method", jsonrpcReq.URN.String(),
		)
		return nil, jussiErrors.NewUpstreamCircuitOpenError(
			"circuit breaker open; request rejected without dialing upstream")
	}
	probeToken = nil //nolint:ineffassign,wastedassign // documented below
	if p.circuitEnabled {
		// Keep the token only when the circuit is enabled; when
		// disabled, Record below would otherwise treat a half-open
		// probe admission as live.
		if !allowed {
			allowed = true
		}
	}

	payload := jsonrpcReq.ToUpstreamRequest()
	headers := jsonrpcReq.UpstreamHeaders()

	timeout := selectUpstreamTimeout(jsonrpcReq)
	var cancel context.CancelFunc
	ctx, cancel = context.WithTimeout(ctx, timeout)
	defer cancel()

	var response map[string]interface{}
	var err error
	if validators.IsBroadcastTransactionRequest(jsonrpcReq) {
		response, err = p.httpClient.Request(ctx, url, payload, headers)
	} else {
		response, err = p.httpClient.RequestWithRetry(ctx, url, payload, headers, upstream.DefaultRetryConfig())
	}

	// Feed the breaker. Timeouts (including context deadlines jussi set
	// itself), transport errors, and 5xx responses all count as
	// failures; any successful response counts as success. The probe
	// token attributes half-open outcomes to the actual probe request.
	if err != nil {
		breaker.Record(false, probeToken)
		telemetry.UpstreamCircuitState.WithLabelValues(breakerKey).Set(breakerStateValue(breaker))
		return nil, err
	}
	breaker.Record(true, probeToken)
	telemetry.UpstreamCircuitState.WithLabelValues(breakerKey).Set(breakerStateValue(breaker))
	return response, nil
}

// breakerStateValue maps the breaker state to the gauge value exported
// by jussi_upstream_circuit_state.
func breakerStateValue(b *upstream.Breaker) float64 {
	switch b.State() {
	case "open":
		return 1
	case "half-open":
		return 2
	default:
		return 0
	}
}

// TODO: WebSocket support - temporarily disabled
// callWebSocketUpstream calls WebSocket upstream with retry logic
// func (p *RequestProcessor) callWebSocketUpstream(ctx context.Context, jsonrpcReq *request.JSONRPCRequest, url string) (map[string]interface{}, error) {
// 	retryConfig := upstream.DefaultRetryConfig()
//
// 	return upstream.RetryWithResult(ctx, retryConfig, func() (map[string]interface{}, error) {
// 		pool, exists := p.wsPools[url]
// 		if !exists {
// 			// Create pool on demand
// 			var err error
// 			pool, err = ws.NewPool(url, 8, 8) // Default pool size
// 			if err != nil {
// 				return nil, &upstream.RetryableError{Err: fmt.Errorf("failed to create WebSocket pool: %w", err)}
// 			}
// 			p.wsPools[url] = pool
// 		}
//
// 		// Acquire connection
// 		client, err := pool.Acquire(ctx)
// 		if err != nil {
// 			return nil, &upstream.RetryableError{Err: fmt.Errorf("failed to acquire connection: %w", err)}
// 		}
// 		defer pool.Release(client)
//
// 		// Send request
// 		payload := jsonrpcReq.ToUpstreamRequest()
// 		if err := client.Send(ctx, payload); err != nil {
// 			return nil, &upstream.RetryableError{Err: fmt.Errorf("failed to send: %w", err)}
// 		}
//
// 		// Receive response
// 		response, err := client.Receive(ctx)
// 		if err != nil {
// 			return nil, &upstream.RetryableError{Err: fmt.Errorf("failed to receive: %w", err)}
// 		}
//
// 		return response, nil
// 	})
// }

// ProcessBatchRequest processes a batch of JSON-RPC requests
func (p *RequestProcessor) ProcessBatchRequest(ctx context.Context, requests []*request.JSONRPCRequest) ([]map[string]interface{}, error) {
	ctx, span := telemetry.StartSpan(ctx, "jussi.process_batch",
		trace.WithSpanKind(trace.SpanKindInternal),
	)
	defer span.End()

	span.SetAttributes(attribute.Int("jussi.batch.size", len(requests)))
	BatchSize.Observe(float64(len(requests)))

	results := make([]map[string]interface{}, len(requests))

	// Process all requests concurrently
	type result struct {
		index int
		resp  map[string]interface{}
		err   error
	}

	resultChan := make(chan result, len(requests))

	for i, req := range requests {
		go func(idx int, r *request.JSONRPCRequest) {
			resp, err := p.ProcessSingleRequest(ctx, r)
			resultChan <- result{index: idx, resp: resp, err: err}
		}(i, req)
	}

	// Collect results
	errorCount := 0
	for i := 0; i < len(requests); i++ {
		res := <-resultChan
		if res.err != nil {
			errorCount++
			// Log the real error server-side; the client gets a generic
			// message because the error chain may contain upstream URLs
			// and internal details.
			slog.Warn("batch request failed",
				"error", res.err.Error(),
				"method", requests[res.index].Method,
			)
			results[res.index] = map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      requests[res.index].ID,
				"error": map[string]interface{}{
					"code":    -32603,
					"message": "Internal error",
				},
			}
		} else {
			results[res.index] = res.resp
		}
	}

	if errorCount > 0 {
		span.SetAttributes(attribute.Int("jussi.batch.errors", errorCount))
	} else {
		telemetry.SetSpanSuccess(span)
	}

	return results, nil
}
