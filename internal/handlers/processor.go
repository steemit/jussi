package handlers

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/steemit/jussi/internal/cache"
	"github.com/steemit/jussi/internal/middleware"
	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/telemetry"
	"github.com/steemit/jussi/internal/upstream"
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

// RequestProcessor processes JSON-RPC requests
type RequestProcessor struct {
	cacheGroup *cache.CacheGroup
	router     *upstream.Router
	httpClient *upstream.HTTPClient
	// TODO: WebSocket support - temporarily disabled
	// wsPools    map[string]*ws.Pool
}

// NewRequestProcessor creates a new request processor
func NewRequestProcessor(
	cacheGroup *cache.CacheGroup,
	router *upstream.Router,
	httpClient *upstream.HTTPClient,
	wsPools map[string]*ws.Pool, // TODO: WebSocket support - temporarily disabled, can be nil
) *RequestProcessor {
	return &RequestProcessor{
		cacheGroup: cacheGroup,
		router:     router,
		httpClient: httpClient,
		// TODO: WebSocket support - temporarily disabled
		// wsPools:    wsPools,
	}
}

// ProcessSingleRequest processes a single JSON-RPC request
func (p *RequestProcessor) ProcessSingleRequest(ctx context.Context, jsonrpcReq *request.JSONRPCRequest) (map[string]interface{}, error) {
	// Create span for request processing
	ctx, span := telemetry.StartSpan(ctx, "jussi.process_request",
		trace.WithSpanKind(trace.SpanKindInternal),
	)
	defer span.End()

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
		err := fmt.Errorf("failed to get upstream configuration")
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
				cachedResp["id"] = jsonrpcReq.ID
				telemetry.SetSpanSuccess(span)
				return cachedResp, nil
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
			_ = p.cacheGroup.Set(ctx, cacheKey, response, cacheTTL)
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

// callHTTPUpstream calls HTTP upstream
func (p *RequestProcessor) callHTTPUpstream(ctx context.Context, jsonrpcReq *request.JSONRPCRequest, url string) (map[string]interface{}, error) {
	payload := jsonrpcReq.ToUpstreamRequest()
	headers := jsonrpcReq.UpstreamHeaders()

	// Create timeout context
	timeout := time.Duration(jsonrpcReq.Upstream.Timeout) * time.Second
	if timeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, timeout)
		defer cancel()
	}

	return p.httpClient.Request(ctx, url, payload, headers)
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
			// Create error response
			results[res.index] = map[string]interface{}{
				"jsonrpc": "2.0",
				"id":      requests[res.index].ID,
				"error": map[string]interface{}{
					"code":    -32603,
					"message": res.err.Error(),
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
