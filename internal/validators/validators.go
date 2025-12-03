package validators

import (
	"fmt"
	"reflect"
	"strconv"

	"github.com/steemit/jussi/internal/errors"
	"github.com/steemit/jussi/internal/request"
)

// JSONRPCRequestKeys are the valid keys in a JSON-RPC request
var JSONRPCRequestKeys = map[string]bool{
	"id":      true,
	"jsonrpc": true,
	"method":  true,
	"params":  true,
}

// JSONRPCResponseKeys are the valid keys in a JSON-RPC response
var JSONRPCResponseKeys = map[string]bool{
	"id":      true,
	"jsonrpc": true,
	"result":  true,
	"error":   true,
}

// IDTypes are valid types for JSON-RPC ID field
var IDTypes = []reflect.Kind{
	reflect.String,
	reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64,
	reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64,
	reflect.Float32, reflect.Float64,
}

// ParamsTypes are valid types for JSON-RPC params field
var ParamsTypes = []reflect.Kind{
	reflect.Slice,
	reflect.Map,
	reflect.Invalid, // nil
}

// ValidateJSONRPCRequest validates a JSON-RPC 2.0 request
func ValidateJSONRPCRequest(request interface{}) error {
	switch req := request.(type) {
	case map[string]interface{}:
		return validateSingleRequest(req)
	case []interface{}:
		if len(req) == 0 {
			return fmt.Errorf("batch request cannot be empty")
		}
		for i, r := range req {
			if err := validateSingleRequest(r.(map[string]interface{})); err != nil {
				return fmt.Errorf("batch request[%d]: %w", i, err)
			}
		}
		return nil
	default:
		return fmt.Errorf("request must be an object or array")
	}
}

func validateSingleRequest(req map[string]interface{}) error {
	// Check required fields
	jsonrpc, ok := req["jsonrpc"].(string)
	if !ok || jsonrpc != "2.0" {
		return fmt.Errorf("jsonrpc must be '2.0'")
	}

	method, ok := req["method"].(string)
	if !ok {
		return fmt.Errorf("method must be a string")
	}
	if method == "" {
		return fmt.Errorf("method cannot be empty")
	}

	// Check id (optional but must be valid type if present)
	if id, ok := req["id"]; ok && id != nil {
		if !isValidIDType(id) {
			return fmt.Errorf("id must be string, number, or null")
		}
	}

	// Check params (optional but must be valid type if present)
	if params, ok := req["params"]; ok && params != nil {
		if !isValidParamsType(params) {
			return fmt.Errorf("params must be array, object, or null")
		}
	}

	// Check for invalid keys
	for key := range req {
		if !JSONRPCRequestKeys[key] {
			return fmt.Errorf("invalid key: %s", key)
		}
	}

	return nil
}

// ValidateJSONRPCResponse validates a JSON-RPC 2.0 response
func ValidateJSONRPCResponse(response map[string]interface{}) error {
	// Must have either result or error, but not both
	hasResult := false
	hasError := false

	if _, ok := response["result"]; ok {
		hasResult = true
	}
	if _, ok := response["error"]; ok {
		hasError = true
	}

	if !hasResult && !hasError {
		return fmt.Errorf("response must have either 'result' or 'error'")
	}

	if hasResult && hasError {
		return fmt.Errorf("response cannot have both 'result' and 'error'")
	}

	// Check jsonrpc version
	if jsonrpc, ok := response["jsonrpc"].(string); ok {
		if jsonrpc != "2.0" {
			return fmt.Errorf("jsonrpc must be '2.0'")
		}
	}

	return nil
}

// IsValidNonErrorResponse checks if response is valid and non-error
func IsValidNonErrorResponse(response map[string]interface{}) bool {
	if err := ValidateJSONRPCResponse(response); err != nil {
		return false
	}

	// Must have result (not error)
	_, hasResult := response["result"]
	_, hasError := response["error"]

	return hasResult && !hasError
}

func isValidIDType(v interface{}) bool {
	kind := reflect.TypeOf(v).Kind()
	for _, validKind := range IDTypes {
		if kind == validKind {
			return true
		}
	}
	return false
}

func isValidParamsType(v interface{}) bool {
	if v == nil {
		return true
	}
	kind := reflect.TypeOf(v).Kind()
	for _, validKind := range ParamsTypes {
		if kind == validKind {
			return true
		}
	}
	return false
}

// Broadcast transaction method names
var BroadcastTransactionMethods = map[string]bool{
	"broadcast_transaction":             true,
	"broadcast_transaction_synchronous": true,
}

// IsGetBlockRequest checks if the request is a get_block request
func IsGetBlockRequest(req *request.JSONRPCRequest) bool {
	if req == nil || req.URN == nil {
		return false
	}
	return (req.URN.Namespace == "steemd" || req.URN.Namespace == "appbase") &&
		req.URN.Method == "get_block"
}

// IsGetBlockHeaderRequest checks if the request is a get_block_header request
func IsGetBlockHeaderRequest(req *request.JSONRPCRequest) bool {
	if req == nil || req.URN == nil {
		return false
	}
	return (req.URN.Namespace == "steemd" || req.URN.Namespace == "appbase") &&
		req.URN.Method == "get_block_header"
}

// IsBroadcastTransactionRequest checks if the request is a broadcast transaction request
func IsBroadcastTransactionRequest(req *request.JSONRPCRequest) bool {
	if req == nil || req.URN == nil {
		return false
	}
	return BroadcastTransactionMethods[req.URN.Method]
}

// BlockNumFromID extracts block number from block ID (first 8 hex digits)
func BlockNumFromID(blockID string) (int, error) {
	if len(blockID) < 8 {
		return 0, fmt.Errorf("block ID too short: %s", blockID)
	}
	blockNumStr := blockID[:8]
	blockNum, err := strconv.ParseInt(blockNumStr, 16, 32)
	if err != nil {
		return 0, fmt.Errorf("failed to parse block number from ID: %w", err)
	}
	return int(blockNum), nil
}

// IsValidGetBlockResponse validates that the response matches the get_block request
func IsValidGetBlockResponse(req *request.JSONRPCRequest, response map[string]interface{}) bool {
	if !IsGetBlockRequest(req) {
		return false
	}

	if !IsValidNonErrorResponse(response) {
		return false
	}

	// Check if result is nil (block doesn't exist yet)
	result, ok := response["result"].(map[string]interface{})
	if !ok || result == nil {
		return false
	}

	// Extract block_id from response
	var blockID string
	if id, ok := result["block_id"].(string); ok {
		blockID = id
	} else if block, ok := result["block"].(map[string]interface{}); ok {
		if id, ok := block["block_id"].(string); ok {
			blockID = id
		}
	}

	if blockID == "" {
		return false
	}

	// Extract block number from request params
	var requestBlockNum interface{}
	switch params := req.URN.Params.(type) {
	case []interface{}:
		if len(params) > 0 {
			requestBlockNum = params[0]
		}
	case map[string]interface{}:
		requestBlockNum = params["block_num"]
	}

	if requestBlockNum == nil {
		return false
	}

	// Convert request block num to int
	var reqBlockNum int
	switch v := requestBlockNum.(type) {
	case int:
		reqBlockNum = v
	case float64:
		reqBlockNum = int(v)
	case string:
		num, err := strconv.Atoi(v)
		if err != nil {
			return false
		}
		reqBlockNum = num
	default:
		return false
	}

	// Extract block number from response block ID
	respBlockNum, err := BlockNumFromID(blockID)
	if err != nil {
		return false
	}

	return reqBlockNum == respBlockNum
}

// LimitCustomJSONOpLength validates custom JSON operation length
func LimitCustomJSONOpLength(ops []interface{}, sizeLimit int) error {
	for _, op := range ops {
		opList, ok := op.([]interface{})
		if !ok || len(opList) < 2 {
			continue
		}

		opType, ok := opList[0].(string)
		if !ok || opType != "custom_json" {
			continue
		}

		opData, ok := opList[1].(map[string]interface{})
		if !ok {
			continue
		}

		jsonStr, ok := opData["json"].(string)
		if !ok {
			continue
		}

		// Check UTF-8 encoded length
		jsonBytes := []byte(jsonStr)
		if len(jsonBytes) > sizeLimit {
			return errors.NewCustomJSONOpLengthError(len(jsonBytes), sizeLimit)
		}
	}

	return nil
}

// LimitCustomJSONAccount validates custom JSON account blacklist
func LimitCustomJSONAccount(ops []interface{}, blacklistAccounts map[string]bool) error {
	if blacklistAccounts == nil || len(blacklistAccounts) == 0 {
		return nil
	}

	for _, op := range ops {
		opList, ok := op.([]interface{})
		if !ok || len(opList) < 2 {
			continue
		}

		opType, ok := opList[0].(string)
		if !ok || opType != "custom_json" {
			continue
		}

		opData, ok := opList[1].(map[string]interface{})
		if !ok {
			continue
		}

		// Check required_posting_auths
		if postingAuths, ok := opData["required_posting_auths"].([]interface{}); ok {
			for _, auth := range postingAuths {
				if authStr, ok := auth.(string); ok {
					if blacklistAccounts[authStr] {
						return errors.NewLimitsError(fmt.Sprintf("account %s is blacklisted", authStr))
					}
				}
			}
		}
	}

	return nil
}

// LimitBroadcastTransactionRequest validates broadcast transaction request limits
func LimitBroadcastTransactionRequest(req *request.JSONRPCRequest, limits map[string]interface{}) error {
	if !IsBroadcastTransactionRequest(req) {
		return nil
	}

	// Extract operations from request params
	var operations []interface{}
	switch params := req.URN.Params.(type) {
	case []interface{}:
		if len(params) > 0 {
			if trx, ok := params[0].(map[string]interface{}); ok {
				if ops, ok := trx["operations"].([]interface{}); ok {
					operations = ops
				}
			}
		}
	case map[string]interface{}:
		if trx, ok := params["trx"].(map[string]interface{}); ok {
			if ops, ok := trx["operations"].([]interface{}); ok {
				operations = ops
			}
		}
	}

	if len(operations) == 0 {
		return nil
	}

	// Filter custom_json operations
	var customJSONOps []interface{}
	for _, op := range operations {
		opList, ok := op.([]interface{})
		if !ok || len(opList) < 2 {
			continue
		}
		if opType, ok := opList[0].(string); ok && opType == "custom_json" {
			customJSONOps = append(customJSONOps, op)
		}
	}

	if len(customJSONOps) == 0 {
		return nil
	}

	// Validate custom JSON op length (default limit: 8192 bytes)
	sizeLimit := 8192
	if limit, ok := limits["custom_json_size_limit"].(float64); ok {
		sizeLimit = int(limit)
	} else if limit, ok := limits["custom_json_size_limit"].(int); ok {
		sizeLimit = limit
	}

	if err := LimitCustomJSONOpLength(customJSONOps, sizeLimit); err != nil {
		return err
	}

	// Validate account blacklist
	blacklistAccounts := make(map[string]bool)
	if accounts, ok := limits["accounts_blacklist"].([]interface{}); ok {
		for _, acc := range accounts {
			if accStr, ok := acc.(string); ok {
				blacklistAccounts[accStr] = true
			}
		}
	} else if accounts, ok := limits["accounts_blacklist"].([]string); ok {
		for _, acc := range accounts {
			blacklistAccounts[acc] = true
		}
	}

	return LimitCustomJSONAccount(customJSONOps, blacklistAccounts)
}

