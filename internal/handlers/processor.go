package handlers

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/steemit/jussi/internal/cache"
	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/upstream"
	"github.com/steemit/jussi/internal/ws"
)

// RequestProcessor processes JSON-RPC requests
type RequestProcessor struct {
	cacheGroup *cache.CacheGroup
	router     *upstream.Router
	httpClient *upstream.HTTPClient
	wsPools    map[string]*ws.Pool
}

// NewRequestProcessor creates a new request processor
func NewRequestProcessor(
	cacheGroup *cache.CacheGroup,
	router *upstream.Router,
	httpClient *upstream.HTTPClient,
	wsPools map[string]*ws.Pool,
) *RequestProcessor {
	return &RequestProcessor{
		cacheGroup: cacheGroup,
		router:     router,
		httpClient: httpClient,
		wsPools:    wsPools,
	}
}

// ProcessSingleRequest processes a single JSON-RPC request
func (p *RequestProcessor) ProcessSingleRequest(ctx context.Context, jsonrpcReq *request.JSONRPCRequest) (map[string]interface{}, error) {
	// Get upstream configuration
	upstreamConfig, err := p.router.GetUpstream(jsonrpcReq.URN)
	if err != nil {
		return nil, fmt.Errorf("failed to get upstream: %w", err)
	}

	// Convert upstream.Upstream to request.UpstreamConfig
	jsonrpcReq.Upstream = &request.UpstreamConfig{
		URL:     upstreamConfig.URL,
		TTL:     upstreamConfig.TTL,
		Timeout: upstreamConfig.Timeout,
	}

	ttl := upstreamConfig.TTL

	// Check cache if TTL is not -1 (no cache)
	if cache.IsCacheable(ttl) {
		cacheKey := cache.GenerateCacheKey(jsonrpcReq.URN)
		cachedValue, err := p.cacheGroup.Get(ctx, cacheKey)
		if err == nil && cachedValue != nil {
			// Cache hit - merge with request ID
			if cachedResp, ok := cachedValue.(map[string]interface{}); ok {
				cachedResp["id"] = jsonrpcReq.ID
				return cachedResp, nil
			}
		}
	}

	// Cache miss - call upstream
	var response map[string]interface{}
	upstreamURL := upstreamConfig.URL

	if strings.HasPrefix(upstreamURL, "ws://") || strings.HasPrefix(upstreamURL, "wss://") {
		// WebSocket upstream
		response, err = p.callWebSocketUpstream(ctx, jsonrpcReq, upstreamURL)
	} else {
		// HTTP upstream
		response, err = p.callHTTPUpstream(ctx, jsonrpcReq, upstreamURL)
	}

	if err != nil {
		return nil, fmt.Errorf("upstream call failed: %w", err)
	}

	// Cache response if cacheable
	if cache.IsCacheable(ttl) {
		cacheKey := cache.GenerateCacheKey(jsonrpcReq.URN)
		cacheTTL := cache.CalculateTTL(ttl, false, 0) // TODO: Check irreversibility
		_ = p.cacheGroup.Set(ctx, cacheKey, response, cacheTTL)
	}

	// Ensure response has correct ID
	response["id"] = jsonrpcReq.ID
	return response, nil
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

// callWebSocketUpstream calls WebSocket upstream
func (p *RequestProcessor) callWebSocketUpstream(ctx context.Context, jsonrpcReq *request.JSONRPCRequest, url string) (map[string]interface{}, error) {
	pool, exists := p.wsPools[url]
	if !exists {
		// Create pool on demand
		var err error
		pool, err = ws.NewPool(url, 8, 8) // Default pool size
		if err != nil {
			return nil, fmt.Errorf("failed to create WebSocket pool: %w", err)
		}
		p.wsPools[url] = pool
	}

	// Acquire connection
	client, err := pool.Acquire(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to acquire connection: %w", err)
	}
	defer pool.Release(client)

	// Send request
	payload := jsonrpcReq.ToUpstreamRequest()
	if err := client.Send(ctx, payload); err != nil {
		return nil, fmt.Errorf("failed to send: %w", err)
	}

	// Receive response
	response, err := client.Receive(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to receive: %w", err)
	}

	return response, nil
}

// ProcessBatchRequest processes a batch of JSON-RPC requests
func (p *RequestProcessor) ProcessBatchRequest(ctx context.Context, requests []*request.JSONRPCRequest) ([]map[string]interface{}, error) {
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
	for i := 0; i < len(requests); i++ {
		res := <-resultChan
		if res.err != nil {
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

	return results, nil
}

