package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"regexp"
	"sync"
	"time"

	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/urn"
)

// ============================================================================
// TEMPORARY WORKAROUND: get_state path emulation (with Redis cache)
// ============================================================================
//
// Background:
//   steemd's condenser_api.get_state supports a limited set of sub-paths:
//     - /@user/recent-replies, /@user/posts, /@user/comments
//     - /@user/blog, /@user/feed
//     - /trending, /hot, /promoted, /created, etc.
//
//   The following paths are NOT handled by steemd's get_state:
//
//   Category 1 — User sub-paths (returns -32602 "Invalid parameters"):
//     - /@user/transfers
//     - /@user/author-rewards
//     - /@user/curation-rewards
//     - /@user/delegations
//
//   Category 2 — Special pages (returns -32000 "Server error"):
//     - /~witnesses
//     - /proposals
//
//   Some third-party clients (old wallet), direct API calls, and SSR requests
//   still use these paths, causing 504 timeouts when the client retries/waits
//   for ~350 seconds.
//
//   The new wallet (Next.js) and condenser rewrite will completely migrate
//   away from get_state and use direct API calls.
//
// Solution:
//   Category 1: Intercept get_state with unsupported user sub-paths at the
//   jussi layer and emulate the expected response by:
//     1. Calling get_state("/@username") for base account data
//     2. Calling get_account_history for transfers/author/curation rewards
//     3. Calling get_vesting_delegations for delegation data
//     4. Assembling a response in the same format get_state returns
//
//   Category 2: For /~witnesses and /proposals, fetch the base state via
//   get_state("/") to obtain feed_price, props, etc., and return a minimal
//   response. The actual witness/proposal data is loaded client-side via
//   separate API calls (get_witnesses_by_vote, list_proposals).
//
//   All sub-requests are cached in Redis with fine-grained keys to maximize
//   reuse across different sub-paths for the same user.
//
// Cache key design (for maximum reuse):
//
//   {prefix}gs:base:{username}         — get_state("/@user") base account data
//   {prefix}gs:base:__root__           — get_state("/") root state (feed_price, props)
//   {prefix}gs:hist:{username}         — get_account_history full result
//   {prefix}gs:deleg_out:{username}    — get_vesting_delegations (outgoing)
//   {prefix}gs:deleg_in:{username}     — list_vesting_delegations (incoming)
//
//   Where {prefix} is read from JUSSI_CACHE_KEY_PREFIX env var (default: "jussi.")
//
//   author-rewards and curation-rewards both reuse gs:hist:{username},
//   only differing in the client-side filter applied to the cached data.
//
// Removal:
//   DELETE THIS FILE once all clients have migrated to the condenser rewrite
//   and wallet rewrite (both of which do not use get_state at all).
//   Track usage via the "workaround_success" metric in Prometheus and remove
//   when request count drops to zero.
//   Also remove the corresponding intercept block in processor.go
//   (search for "TEMPORARY WORKAROUND" comment).
//
// Added: 2026-05-25 (Category 1), 2026-05-28 (Category 2)
// Related: wallet 504 investigation, steemd get_state limitations
// ============================================================================

// Configuration constants
const (
	subRequestTimeout = 15 * time.Second
	maxHistoryEntries = 200
	workaroundCacheTTL = 10 * time.Second
)

// cacheKeyPrefix is the global prefix for workaround cache keys.
// Configurable via JUSSI_CACHE_KEY_PREFIX environment variable.
var cacheKeyPrefix string

func init() {
	cacheKeyPrefix = os.Getenv("JUSSI_CACHE_KEY_PREFIX")
	if cacheKeyPrefix == "" {
		cacheKeyPrefix = "jussi."
	}
}

// Fine-grained cache key generators.
// Each targets a specific sub-request to maximize cross-subpath reuse:
//   - gs:base is reused by all three sub-paths
//   - gs:hist is reused by both author-rewards and curation-rewards
//   - gs:deleg_out and gs:deleg_in are only used by delegations
func cacheKeyBase(username string) string {
	return cacheKeyPrefix + "gs:base:" + username
}

func cacheKeyHistory(username string) string {
	return cacheKeyPrefix + "gs:hist:" + username
}

func cacheKeyDelegOut(username string) string {
	return cacheKeyPrefix + "gs:deleg_out:" + username
}

func cacheKeyDelegIn(username string) string {
	return cacheKeyPrefix + "gs:deleg_in:" + username
}

// getStateSubPathRegex matches get_state sub-paths that steemd does NOT handle.
// All four sub-paths cause "Invalid parameters" and need emulation.
var getStateSubPathRegex = regexp.MustCompile(
	`^/?@([^/\s]+)/(transfers|author-rewards|curation-rewards|delegations)$`,
)

// getStateSpecialPathRegex matches get_state paths that steemd's get_state
// does NOT handle at all (returns -32000 Server error).
// These are special pages like witnesses list and proposals.
// Matches: "/~witnesses", "~witnesses", "/proposals", "proposals"
var getStateSpecialPathRegex = regexp.MustCompile(
	`^/?(?:~witnesses|proposals)$`,
)

// isGetStateUnsupportedSubPath checks if a request is condenser_api.get_state
// with a sub-path that steemd does NOT handle natively.
// Returns (username, subPath, true) when interception is needed.
func isGetStateUnsupportedSubPath(jsonrpcReq *request.JSONRPCRequest) (string, string, bool) {
	if jsonrpcReq.URN.API != "condenser_api" || jsonrpcReq.URN.Method != "get_state" {
		return "", "", false
	}

	params, ok := jsonrpcReq.Params.([]interface{})
	if !ok {
		return "", "", false
	}

	// Extract the path string from params.
	// Two formats after translateLegacyAPI:
	//   - direct method: params = ["/@user/transfers"]           (len=1)
	//   - call-style:    params = ["condenser_api","get_state",["/@user/transfers"]]  (len=3)
	var path string
	switch len(params) {
	case 1:
		path, ok = params[0].(string)
	case 3:
		// call-style: params[2] is the actual argument
		var args []interface{}
		if args, ok = params[2].([]interface{}); ok && len(args) >= 1 {
			path, ok = args[0].(string)
		}
	}
	if !ok || path == "" {
		return "", "", false
	}

	matches := getStateSubPathRegex.FindStringSubmatch(path)
	if matches == nil {
		return "", "", false
	}

	return matches[1], matches[2], true
}

// isGetStateSpecialPath checks if a request is condenser_api.get_state
// with a path that steemd's get_state returns -32000 for (not implemented).
// Returns (pathType, true) when interception is needed.
// pathType is "witnesses" or "proposals".
func isGetStateSpecialPath(jsonrpcReq *request.JSONRPCRequest) (string, bool) {
	if jsonrpcReq.URN.API != "condenser_api" || jsonrpcReq.URN.Method != "get_state" {
		return "", false
	}

	params, ok := jsonrpcReq.Params.([]interface{})
	if !ok {
		return "", false
	}

	var path string
	switch len(params) {
	case 1:
		path, ok = params[0].(string)
	case 3:
		var args []interface{}
		if args, ok = params[2].([]interface{}); ok && len(args) >= 1 {
			path, ok = args[0].(string)
		}
	}
	if !ok || path == "" {
		return "", false
	}

	if getStateSpecialPathRegex.MatchString(path) {
		if path == "/~witnesses" || path == "~witnesses" {
			return "witnesses", true
		}
		return "proposals", true
	}
	return "", false
}

// emulateGetStateSpecialPath constructs a synthetic get_state response for
// paths that steemd's get_state does not implement (~witnesses, proposals).
//
// It fetches the base state via get_state("/") to obtain feed_price, props,
// etc., then adds a minimal structure for the requested page.
//
// The wallet SSR mainly needs feed_price and props to render the page shell.
// The actual witness/proposal data is fetched client-side via direct API calls
// (get_witnesses_by_vote, list_proposals), so we don't need to include it here.
func (p *RequestProcessor) emulateGetStateSpecialPath(
	ctx context.Context,
	jsonrpcReq *request.JSONRPCRequest,
	pathType string,
) (map[string]interface{}, error) {
	upstreamURL, err := p.getSteemdUpstreamURL()
	if err != nil {
		return nil, fmt.Errorf("get_state special path workaround: %w", err)
	}

	// Fetch base state using get_state("/") for feed_price, props, etc.
	baseResp, err := p.fetchCachedOrCall(ctx, upstreamURL,
		cacheKeyPrefix+"gs:base:__root__",
		"condenser_api.get_state",
		[]interface{}{"/"},
		jsonrpcReq,
	)
	if err != nil {
		return nil, fmt.Errorf("get_state special path workaround: base state failed: %w", err)
	}

	if _, hasErr := baseResp["error"]; hasErr {
		baseResp["id"] = jsonrpcReq.ID
		return baseResp, nil
	}

	result, ok := baseResp["result"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("get_state special path workaround: unexpected base response format")
	}

	// Build minimal response structure for the special page.
	// Wallet SSR only needs the basic get_state envelope to render the page shell.
	// The actual data (witnesses list, proposals list) is loaded via separate
	// client-side API calls after the page loads.
	result["current_route"] = "/" + pathType
	if result["accounts"] == nil {
		result["accounts"] = map[string]interface{}{}
	}
	if result["content"] == nil {
		result["content"] = map[string]interface{}{}
	}
	if result["discussion_idx"] == nil {
		result["discussion_idx"] = map[string]interface{}{}
	}
	if result["tag_idx"] == nil {
		result["tag_idx"] = map[string]interface{}{}
	}
	if result["tags"] == nil {
		result["tags"] = map[string]interface{}{}
	}

	baseResp["id"] = jsonrpcReq.ID
	return baseResp, nil
}

// emulateGetStateSubPath constructs a synthetic get_state response for
// unsupported sub-paths by calling the steemd upstream directly,
// with Redis caching at the sub-request level.
func (p *RequestProcessor) emulateGetStateSubPath(
	ctx context.Context,
	jsonrpcReq *request.JSONRPCRequest,
	username string,
	subPath string,
) (map[string]interface{}, error) {
	// Resolve the steemd upstream URL via the router
	upstreamURL, err := p.getSteemdUpstreamURL()
	if err != nil {
		return nil, fmt.Errorf("get_state workaround: %w", err)
	}

	// Step 1: Fetch base account state — cached by username
	baseResp, err := p.fetchCachedOrCall(ctx, upstreamURL, cacheKeyBase(username),
		"condenser_api.get_state",
		[]interface{}{fmt.Sprintf("/@%s", username)},
		jsonrpcReq,
	)
	if err != nil {
		return nil, fmt.Errorf("get_state workaround: base get_state failed: %w", err)
	}

	// If base request returned an error, pass it through
	if _, hasErr := baseResp["error"]; hasErr {
		baseResp["id"] = jsonrpcReq.ID
		return baseResp, nil
	}

	result, ok := baseResp["result"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("get_state workaround: unexpected base response format")
	}

	// Step 2: Fetch sub-path-specific data (with caching)
	switch subPath {
	case "transfers":
		p.fillRewardHistory(ctx, upstreamURL, jsonrpcReq, result, username, isTransferOp)

	case "author-rewards":
		p.fillRewardHistory(ctx, upstreamURL, jsonrpcReq, result, username, isAuthorRewardOp)

	case "curation-rewards":
		p.fillRewardHistory(ctx, upstreamURL, jsonrpcReq, result, username, isCurationRewardOp)

	case "delegations":
		p.fillDelegations(ctx, upstreamURL, jsonrpcReq, result, username)
	}

	result["current_route"] = fmt.Sprintf("/@%s/%s", username, subPath)
	baseResp["id"] = jsonrpcReq.ID
	return baseResp, nil
}

// fetchCachedOrCall checks Redis cache first, falls back to upstream call,
// then caches the result. This is the core caching primitive for the workaround.
// Returns the full JSON-RPC response (including "result" key) from either
// cache or fresh upstream call.
func (p *RequestProcessor) fetchCachedOrCall(
	ctx context.Context,
	upstreamURL string,
	cacheKey string,
	method string,
	params []interface{},
	jsonrpcReq *request.JSONRPCRequest,
) (map[string]interface{}, error) {
	// Try cache first
	if p.cacheGroup != nil {
		cached, err := p.cacheGroup.Get(ctx, cacheKey)
		if err == nil && cached != nil {
			if cachedMap, ok := cached.(map[string]interface{}); ok {
				slog.Debug("get_state workaround: cache hit",
					"key", cacheKey, "method", method)
				return cachedMap, nil
			}
		}
	}

	// Cache miss — call upstream
	resp, err := p.callSteemd(ctx, upstreamURL, method, params, jsonrpcReq)
	if err != nil {
		return nil, err
	}

	// Store in cache (only cache successful responses)
	if p.cacheGroup != nil && resp["error"] == nil {
		// Deep copy before caching to avoid shared reference issues
		cached := deepCopyMap(resp)
		go func() {
			bgCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			if err := p.cacheGroup.Set(bgCtx, cacheKey, cached, workaroundCacheTTL); err != nil {
				slog.Warn("get_state workaround: cache set failed",
					"key", cacheKey, "error", err)
			}
		}()
	}

	return resp, nil
}

// fillRewardHistory fetches get_account_history and filters by op type,
// injecting matching operations into the account's transfer_history field.
// The full history is cached (shared between author-rewards and curation-rewards).
func (p *RequestProcessor) fillRewardHistory(
	ctx context.Context,
	upstreamURL string,
	jsonrpcReq *request.JSONRPCRequest,
	result map[string]interface{},
	username string,
	opFilter func(string) bool,
) {
	// Fetch full history — cached by username (reused across reward types)
	historyResp, err := p.fetchCachedOrCall(ctx, upstreamURL, cacheKeyHistory(username),
		"condenser_api.get_account_history",
		[]interface{}{username, -1, 1000},
		jsonrpcReq,
	)
	if err != nil {
		slog.Warn("get_state workaround: get_account_history failed",
			"username", username, "error", err)
		return // non-fatal: return base state without history
	}

	historyResult, ok := historyResp["result"].([]interface{})
	if !ok {
		return
	}

	// Get account entry from get_state result
	accounts, ok := result["accounts"].(map[string]interface{})
	if !ok {
		return
	}
	account, ok := accounts[username].(map[string]interface{})
	if !ok {
		return
	}

	// Build filtered transfer_history in the same format steemd uses:
	// map of "index_string" -> {"op": ["op_type", {op_data}]}
	transferHistory := make(map[string]interface{})
	count := 0
	for _, item := range historyResult {
		if count >= maxHistoryEntries {
			break
		}
		entry, ok := item.([]interface{})
		if !ok || len(entry) < 2 {
			continue
		}
		index, ok := entry[0].(float64)
		if !ok {
			continue
		}
		opObj, ok := entry[1].(map[string]interface{})
		if !ok {
			continue
		}
		op, ok := opObj["op"].([]interface{})
		if !ok || len(op) < 1 {
			continue
		}
		opType, ok := op[0].(string)
		if !ok {
			continue
		}

		if opFilter(opType) {
			transferHistory[fmt.Sprintf("%d", int(index))] = opObj
			count++
		}
	}

	account["transfer_history"] = transferHistory
}

// fillDelegations fetches outgoing and incoming vesting delegations
// and injects them into the account's transfer_history field.
// Both sub-requests are cached independently.
func (p *RequestProcessor) fillDelegations(
	ctx context.Context,
	upstreamURL string,
	jsonrpcReq *request.JSONRPCRequest,
	result map[string]interface{},
	username string,
) {
	accounts, ok := result["accounts"].(map[string]interface{})
	if !ok {
		return
	}
	account, ok := accounts[username].(map[string]interface{})
	if !ok {
		return
	}

	var (
		wg             sync.WaitGroup
		outDelegsResp  map[string]interface{}
		outErr         error
		inDelegsResp   map[string]interface{}
		inErr          error
	)

	wg.Add(2)
	go func() {
		defer wg.Done()
		// Outgoing delegations — cached independently
		outDelegsResp, outErr = p.fetchCachedOrCall(ctx, upstreamURL,
			cacheKeyDelegOut(username),
			"condenser_api.get_vesting_delegations",
			[]interface{}{username, "", 100}, jsonrpcReq)
	}()
	go func() {
		defer wg.Done()
		// Incoming delegations — cached independently
		// Use start object to position at the target delegatee for efficient
		// filtering. The API returns delegations ordered by delegatee, so we
		// seek to {delegatee: username, delegator: ""} and collect up to 100.
		inDelegsResp, inErr = p.fetchCachedOrCall(ctx, upstreamURL,
			cacheKeyDelegIn(username),
			"database_api.list_vesting_delegations",
			[]interface{}{map[string]interface{}{
				"start": map[string]interface{}{
					"delegatee": username,
					"delegator": "",
				},
				"limit": 100,
				"order": "by_delegatee",
			}}, jsonrpcReq)
	}()
	wg.Wait()

	if outErr != nil {
		slog.Warn("get_state workaround: outgoing delegations failed",
			"username", username, "error", outErr)
	}
	if inErr != nil {
		slog.Warn("get_state workaround: incoming delegations failed",
			"username", username, "error", inErr)
	}

	// Build synthetic transfer_history with delegation entries
	transferHistory := make(map[string]interface{})
	idx := 0

	// Outgoing delegations: response is array of delegation objects
	if outDelegsResp != nil {
		if outResult, ok := outDelegsResp["result"].([]interface{}); ok {
			for _, del := range outResult {
				if idx >= maxHistoryEntries {
					break
				}
				if delMap, ok := del.(map[string]interface{}); ok {
					transferHistory[fmt.Sprintf("%d", idx)] = map[string]interface{}{
						"op": []interface{}{"delegate_vesting_shares", delMap},
					}
					idx++
				}
			}
		}
	}

	// Incoming delegations: response has {delegations: [...]}
	if inDelegsResp != nil {
		if inResult, ok := inDelegsResp["result"].(map[string]interface{}); ok {
			if delegations, ok := inResult["delegations"].([]interface{}); ok {
				for _, del := range delegations {
					if idx >= maxHistoryEntries {
						break
					}
					if delMap, ok := del.(map[string]interface{}); ok {
						transferHistory[fmt.Sprintf("%d", idx)] = map[string]interface{}{
							"op": []interface{}{"delegate_vesting_shares", delMap},
						}
						idx++
					}
				}
			}
		}
	}

	account["transfer_history"] = transferHistory
}

// --- Helper functions ---

func isAuthorRewardOp(opType string) bool {
	return opType == "author_reward" || opType == "comment_benefactor_reward"
}

func isCurationRewardOp(opType string) bool {
	return opType == "curation_reward"
}

// isTransferOp matches all operation types that appear in the "transfers" tab.
// This mirrors steemd's native behavior for get_state("/@user/transfers").
func isTransferOp(opType string) bool {
	switch opType {
	case "transfer", "transfer_to_vesting", "transfer_from_savings",
		"transfer_to_savings", "cancel_transfer_from_savings":
		return true
	}
	return false
}

// getSteemdUpstreamURL resolves the upstream URL for condenser_api requests.
// Constructs a synthetic URN without Params so URN.String() produces
// "appbase.condenser_api.get_state" which matches the router config.
func (p *RequestProcessor) getSteemdUpstreamURL() (string, error) {
	synthURN := &urn.URN{
		Namespace: "appbase",
		API:       "condenser_api",
		Method:    "get_state",
		// Params intentionally nil: URN.String() must produce
		// "appbase.condenser_api.get_state" (without params suffix)
		// to match the router's longest-prefix lookup.
	}
	upstreamConfig, found := p.router.GetUpstream(synthURN.String())
	if !found {
		return "", fmt.Errorf("no upstream configured for %s", synthURN.String())
	}
	return upstreamConfig.URL, nil
}

// callSteemd sends a single JSON-RPC request to the steemd upstream
// with an independent timeout to avoid cascading context cancellation.
func (p *RequestProcessor) callSteemd(
	ctx context.Context,
	upstreamURL string,
	method string,
	params []interface{},
	originalReq *request.JSONRPCRequest,
) (map[string]interface{}, error) {
	// Create a per-request timeout context
	subCtx, cancel := context.WithTimeout(ctx, subRequestTimeout)
	defer cancel()

	payload := map[string]interface{}{
		"jsonrpc": "2.0",
		"method":  method,
		"params":  params,
		"id":      originalReq.UpstreamID(),
	}
	headers := originalReq.UpstreamHeaders()

	return p.httpClient.Request(subCtx, upstreamURL, payload, headers)
}

// deepCopyMap creates a deep copy of a map[string]interface{} by
// round-tripping through JSON. Used before caching to prevent shared
// reference issues between concurrent requests.
func deepCopyMap(m map[string]interface{}) map[string]interface{} {
	data, err := json.Marshal(m)
	if err != nil {
		return m // fallback: return original (should not happen with JSON-RPC responses)
	}
	var result map[string]interface{}
	if err := json.Unmarshal(data, &result); err != nil {
		return m
	}
	return result
}
