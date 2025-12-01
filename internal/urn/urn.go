package urn

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
)

// URN represents a parsed JSON-RPC method identifier
type URN struct {
	Namespace string
	API       string
	Method    string
	Params   interface{}
}

// String returns the string representation of the URN
func (u *URN) String() string {
	parts := []string{u.Namespace}
	if u.API != "" {
		parts = append(parts, u.API)
	}
	parts = append(parts, u.Method)
	return strings.Join(parts, ".")
}

// ToDict returns the URN as a map
func (u *URN) ToDict() map[string]interface{} {
	return map[string]interface{}{
		"namespace": u.Namespace,
		"api":       u.API,
		"method":    u.Method,
		"params":    u.Params,
	}
}

var (
	// JRPC_METHOD_REGEX matches JSON-RPC method patterns
	JRPC_METHOD_REGEX = regexp.MustCompile(
		`^(?P<appbase_api>[^\.]+_api)\.(?P<appbase_method>[^\.]+)$|` +
			`^(?P<bare_method>^[^\.]+)$|` +
			`^(?P<namespace>[^\.]+){1}\.(?:(?P<api>[^\.]+)\.){0,1}(?P<method>[^\.]+){1}$`,
	)

	// STEEMD_NUMERIC_API_MAPPING maps numeric API indices to names
	STEEMD_NUMERIC_API_MAPPING = []string{"database_api", "login_api"}
)

// FromRequest parses a JSON-RPC request into a URN
func FromRequest(request map[string]interface{}) (*URN, error) {
	method, ok := request["method"].(string)
	if !ok {
		return nil, fmt.Errorf("method must be a string")
	}

	params := request["params"]
	if params == nil {
		params = []interface{}{}
	}

	matched := JRPC_METHOD_REGEX.FindStringSubmatch(method)
	if matched == nil {
		return nil, fmt.Errorf("invalid method format: %s", method)
	}

	groups := make(map[string]string)
	for i, name := range JRPC_METHOD_REGEX.SubexpNames() {
		if i > 0 && i <= len(matched) {
			groups[name] = matched[i]
		}
	}

	// Handle appbase_api format (e.g., "condenser_api.get_account")
	if groups["appbase_api"] != "" {
		return &URN{
			Namespace: "appbase",
			API:       groups["appbase_api"],
			Method:    groups["appbase_method"],
			Params:    normalizeParams(params),
		}, nil
	}

	// Handle namespace format (e.g., "steemd.database_api.get_block")
	if groups["namespace"] != "" {
		namespace := groups["namespace"]
		if namespace == "jsonrpc" {
			return &URN{
				Namespace: "appbase",
				API:       "jsonrpc",
				Method:    groups["method"],
				Params:    normalizeParams(params),
			}, nil
		}

		return &URN{
			Namespace: namespace,
			API:       groups["api"],
			Method:    groups["method"],
			Params:    normalizeParams(params),
		}, nil
	}

	// Handle bare method format (e.g., "get_block" or "call")
	if groups["bare_method"] != "" {
		bareMethod := groups["bare_method"]
		if bareMethod != "call" {
			// Default to steemd.database_api
			return &URN{
				Namespace: "steemd",
				API:       "database_api",
				Method:    bareMethod,
				Params:    normalizeParams(params),
			}, nil
		}

		// Handle "call" method
		paramsList, ok := params.([]interface{})
		if !ok {
			return nil, fmt.Errorf("call method requires array params")
		}

		if len(paramsList) != 3 {
			// Appbase format: ["condenser_api", "get_account", ...]
			if len(paramsList) >= 2 {
				api, _ := paramsList[0].(string)
				method, _ := paramsList[1].(string)
				var methodParams interface{}
				if len(paramsList) > 2 {
					methodParams = paramsList[2]
				}

				namespace := "appbase"
				if api == "condenser_api" || isDict(methodParams) || api == "jsonrpc" {
					namespace = "appbase"
				} else {
					namespace = "steemd"
				}

				return &URN{
					Namespace: namespace,
					API:       api,
					Method:    method,
					Params:    normalizeParams(methodParams),
				}, nil
			}
		} else {
			// When params length is 3, extract api, method, and params
			// First check if api is a string (appbase format) or number (steemd format)
			apiRaw := paramsList[0]
			method, _ := paramsList[1].(string)
			methodParams := paramsList[2]

			// Check if first param is a number (steemd format)
			if apiIndex, ok := apiRaw.(float64); ok {
				// Steemd format: [api_index, method, params]
				apiIdx := int(apiIndex)
				if apiIdx < 0 || apiIdx >= len(STEEMD_NUMERIC_API_MAPPING) {
					return nil, fmt.Errorf("invalid API index: %d", apiIdx)
				}

				api := STEEMD_NUMERIC_API_MAPPING[apiIdx]
				return &URN{
					Namespace: "steemd",
					API:       api,
					Method:    method,
					Params:    normalizeParams(methodParams),
				}, nil
			}

			// Appbase format: ["condenser_api", "method", params] or ["network_broadcast_api", "method", params]
			api, ok := apiRaw.(string)
			if !ok {
				return nil, fmt.Errorf("call method first param must be string (API name) or number (API index)")
			}

			// Determine namespace based on API name and params type
			namespace := "appbase"
			if api == "condenser_api" || isDict(methodParams) || api == "jsonrpc" {
				namespace = "appbase"
			} else {
				namespace = "steemd"
			}

			return &URN{
				Namespace: namespace,
				API:       api,
				Method:    method,
				Params:    normalizeParams(methodParams),
			}, nil
		}
	}

	return nil, fmt.Errorf("unable to parse method: %s", method)
}

// normalizeParams normalizes params for consistent hashing
func normalizeParams(params interface{}) interface{} {
	if params == nil {
		return nil
	}

	// If params is a map, sort keys for consistent hashing
	if paramsMap, ok := params.(map[string]interface{}); ok {
		normalized := make(map[string]interface{})
		keys := make([]string, 0, len(paramsMap))
		for k := range paramsMap {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			normalized[k] = paramsMap[k]
		}
		return normalized
	}

	return params
}

// isDict checks if the value is a dictionary/map
func isDict(v interface{}) bool {
	_, ok := v.(map[string]interface{})
	return ok
}

