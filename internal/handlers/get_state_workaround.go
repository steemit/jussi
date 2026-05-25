package handlers

import (
	"context"
	"fmt"
	"log/slog"
	"regexp"
	"sync"
	"time"

	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/upstream"
	"github.com/steemit/jussi/internal/urn"
)

// ============================================================================
// TEMPORARY WORKAROUND: get_state sub-path emulation
// ============================================================================
//
// Background:
//   steemd's condenser_api.get_state only supports a limited set of sub-paths:
//     - /@user/transfers
//     - /@user/recent-replies
//     - /@user/posts, /@user/comments
//     - /@user/blog, /@user/feed
//
//   The following sub-paths were NEVER implemented in steemd's get_state:
//     - /@user/author-rewards
//     - /@user/curation-rewards
//     - /@user/delegations
//
//   Calling get_state with these paths causes steemd to return
//   -32602 "Invalid parameters". The old wallet (condenser-based) and
//   some third-party clients still request these paths, causing the
//   frontend SSR to hang until timeout (~344 seconds) and return 504.
//
//   The new wallet (Next.js) has completely migrated away from get_state
//   and uses direct API calls:
//     - /api/query/history             -> get_account_history
//     - /api/query/vesting-delegations -> get_vesting_delegations
//
// Solution:
//   Intercept get_state requests with unsupported sub-paths at the jussi
//   layer and emulate the expected get_state response by:
//     1. Calling get_state("/@username") for base account data
//     2. Calling get_account_history for author/curation rewards
//     3. Calling get_vesting_delegations for delegation data
//     4. Assembling a response in the same format get_state returns
//
// Removal:
//   DELETE THIS FILE once all clients have migrated to the new wallet or
//   to direct API calls. Track usage via the "workaround_success" metric
//   in Prometheus and remove when request count drops to zero.
//   Also remove the corresponding intercept block in processor.go
//   (search for "TEMPORARY WORKAROUND" comment).
//
// Added: 2026-05-25
// Related: beta-wallet 504 investigation, steemd get_state limitations
// ============================================================================

// subRequestTimeout is the per-request timeout for workaround internal calls.
const subRequestTimeout = 15 * time.Second

// maxHistoryEntries caps the number of filtered entries we inject into
// transfer_history to keep response size reasonable.
const maxHistoryEntries = 200

// getStateSubPathRegex matches unsupported get_state sub-paths.
// NOTE: "transfers" is intentionally excluded — steemd supports it natively.
var getStateSubPathRegex = regexp.MustCompile(
	`^/?@([^/\s]+)/(author-rewards|curation-rewards|delegations)$`,
)

// isGetStateUnsupportedSubPath checks if a request is condenser_api.get_state
// with a sub-path that steemd does NOT handle natively.
// Returns (username, subPath, true) when interception is needed.
func isGetStateUnsupportedSubPath(jsonrpcReq *request.JSONRPCRequest) (string, string, bool) {
	if jsonrpcReq.URN.API != "condenser_api" || jsonrpcReq.URN.Method != "get_state" {
		return "", "", false
	}

	params, ok := jsonrpcReq.Params.([]interface{})
	if !ok || len(params) != 1 {
		return "", "", false
	}
	path, ok := params[0].(string)
	if !ok {
		return "", "", false
	}

	matches := getStateSubPathRegex.FindStringSubmatch(path)
	if matches == nil {
		return "", "", false
	}

	return matches[1], matches[2], true // username, subPath
}

// emulateGetStateSubPath constructs a synthetic get_state response for
// unsupported sub-paths by calling the steemd upstream directly.
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

	// Step 1: Fetch base account state via get_state("/@username")
	baseResp, err := p.callSteemd(ctx, upstreamURL, "condenser_api.get_state",
		[]interface{}{fmt.Sprintf("/@%s", username)}, jsonrpcReq)
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

	// Step 2: Fetch sub-path-specific data
	switch subPath {
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

// fillRewardHistory fetches get_account_history and filters by op type,
// injecting matching operations into the account's transfer_history field.
func (p *RequestProcessor) fillRewardHistory(
	ctx context.Context,
	upstreamURL string,
	jsonrpcReq *request.JSONRPCRequest,
	result map[string]interface{},
	username string,
	opFilter func(string) bool,
) {
	// Fetch last 1000 history entries (steemd max limit)
	historyResp, err := p.callSteemd(ctx, upstreamURL, "condenser_api.get_account_history",
		[]interface{}{username, -1, 1000}, jsonrpcReq)
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
		// Outgoing delegations via condenser_api
		outDelegsResp, outErr = p.callSteemd(ctx, upstreamURL,
			"condenser_api.get_vesting_delegations",
			[]interface{}{username, "", 100}, jsonrpcReq)
	}()
	go func() {
		defer wg.Done()
		// Incoming delegations via database_api.list_vesting_delegations
		// Use start object to position at the target delegatee for efficient
		// filtering. The API returns delegations ordered by delegatee, so we
		// seek to {delegatee: username, delegator: ""} and collect up to 100.
		inDelegsResp, inErr = p.callSteemd(ctx, upstreamURL,
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
	// Create a per-request timeout context to prevent one slow call
	// from consuming the entire parent context budget.
	subCtx, cancel := context.WithTimeout(ctx, subRequestTimeout)
	defer cancel()

	payload := map[string]interface{}{
		"jsonrpc": "2.0",
		"method":  method,
		"params":  params,
		"id":      originalReq.UpstreamID(),
	}
	headers := originalReq.UpstreamHeaders()

	retryCfg := &upstream.RetryConfig{
		MaxRetries:        1,
		InitialBackoff:    100 * time.Millisecond,
		MaxBackoff:        1 * time.Second,
		BackoffMultiplier: 2.0,
	}

	return p.httpClient.RequestWithRetry(subCtx, upstreamURL, payload, headers, retryCfg)
}
