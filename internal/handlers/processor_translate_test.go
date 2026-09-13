package handlers

import (
	"testing"

	"github.com/steemit/jussi/internal/config"
	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/upstream"
	"github.com/steemit/jussi/internal/urn"
)

func newTestRouter(translateNamespaces ...string) *upstream.Router {
	cfg := &config.UpstreamRawConfig{}
	for _, ns := range translateNamespaces {
		cfg.Upstreams = append(cfg.Upstreams, config.UpstreamDefinition{
			Name:               ns,
			TranslateToAppbase: true,
		})
	}
	r, _ := upstream.NewRouter(cfg)
	return r
}

// newTranslateRequest builds a request the same way the JSON-RPC handler does:
// URN comes from the real parser so tests reflect production behavior.
func newTranslateRequest(t *testing.T, raw map[string]interface{}) *request.JSONRPCRequest {
	t.Helper()
	u, err := urn.FromRequest(raw)
	if err != nil {
		t.Fatalf("urn.FromRequest(%v) failed: %v", raw, err)
	}
	method, _ := raw["method"].(string)
	return &request.JSONRPCRequest{
		Method: method,
		Params: raw["params"],
		URN:    u,
	}
}

// Appbase-format requests (named params) must keep their target API: methods
// like database_api.find_accounts do not exist on condenser_api.
func TestTranslateToAppbase_namedParamsPassthrough(t *testing.T) {
	router := newTestRouter("steemd")

	tests := []struct {
		name    string
		raw     map[string]interface{}
		wantAPI string
	}{
		{
			name: "database_api.find_accounts",
			raw: map[string]interface{}{
				"method": "database_api.find_accounts",
				"params": map[string]interface{}{"accounts": []interface{}{"moecki"}},
			},
			wantAPI: "database_api",
		},
		{
			name: "database_api.list_votes",
			raw: map[string]interface{}{
				"method": "database_api.list_votes",
				"params": map[string]interface{}{"start": []interface{}{}, "limit": 50, "order": "by_account"},
			},
			wantAPI: "database_api",
		},
		{
			name: "call-style database_api.find_accounts with object args",
			raw: map[string]interface{}{
				"method": "call",
				"params": []interface{}{"database_api", "find_accounts", map[string]interface{}{"accounts": []interface{}{"moecki"}}},
			},
			wantAPI: "database_api",
		},
		{
			name: "network_broadcast_api.broadcast_transaction with object args",
			raw: map[string]interface{}{
				"method": "network_broadcast_api.broadcast_transaction",
				"params": map[string]interface{}{"trx": map[string]interface{}{"ref_block_num": float64(1)}},
			},
			wantAPI: "network_broadcast_api",
		},
		{
			name: "follow_api.get_blog with object args",
			raw: map[string]interface{}{
				"method": "follow_api.get_blog",
				"params": map[string]interface{}{"account": "user", "start_entry_id": float64(10), "limit": float64(20)},
			},
			wantAPI: "follow_api",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := newTranslateRequest(t, tt.raw)
			translateToAppbase(req, router)

			if req.URN.API != tt.wantAPI {
				t.Errorf("URN.API = %q, want unchanged %q", req.URN.API, tt.wantAPI)
			}
			if req.Method != tt.raw["method"] {
				t.Errorf("Method = %q, want unchanged %q", req.Method, tt.raw["method"])
			}
			if got, ok := req.Params.([]interface{}); ok && len(got) > 0 {
				if got[0] == "condenser_api" {
					t.Errorf("Params[0] rewritten to condenser_api, want unchanged")
				}
			}
		})
	}
}

// Legacy positional formats are rewritten to condenser_api, the only appbase
// API that accepts the condenser wire format.
func TestTranslateToAppbase_legacyFormatsTranslated(t *testing.T) {
	router := newTestRouter("steemd")

	tests := []struct {
		name           string
		raw            map[string]interface{}
		expectedAPI    string
		expectedMethod interface{} // string for direct methods, "call" kept as-is
		expectedParam0 interface{} // for call-style: expected params[0]
	}{
		{
			name:           "bare get_state",
			raw:            map[string]interface{}{"method": "get_state", "params": []interface{}{"/trending"}},
			expectedAPI:    "condenser_api",
			expectedMethod: "condenser_api.get_state",
		},
		{
			name:           "bare get_block",
			raw:            map[string]interface{}{"method": "get_block", "params": []interface{}{float64(106191898)}},
			expectedAPI:    "condenser_api",
			expectedMethod: "condenser_api.get_block",
		},
		{
			name:           "bare get_dynamic_global_properties without params",
			raw:            map[string]interface{}{"method": "get_dynamic_global_properties"},
			expectedAPI:    "condenser_api",
			expectedMethod: "condenser_api.get_dynamic_global_properties",
		},
		{
			name:           "direct database_api.get_state with positional args",
			raw:            map[string]interface{}{"method": "database_api.get_state", "params": []interface{}{"/@user/transfers"}},
			expectedAPI:    "condenser_api",
			expectedMethod: "condenser_api.get_state",
		},
		{
			name:           "jussi-namespaced steemd.database_api.get_block",
			raw:            map[string]interface{}{"method": "steemd.database_api.get_block", "params": []interface{}{float64(1)}},
			expectedAPI:    "condenser_api",
			expectedMethod: "condenser_api.get_block",
		},
		{
			name:           "call-style database_api get_state",
			raw:            map[string]interface{}{"method": "call", "params": []interface{}{"database_api", "get_state", []interface{}{"/trending"}}},
			expectedAPI:    "condenser_api",
			expectedMethod: "call",
			expectedParam0: "condenser_api",
		},
		{
			name:           "call-style follow_api get_blog",
			raw:            map[string]interface{}{"method": "call", "params": []interface{}{"follow_api", "get_blog", []interface{}{"user", float64(10), float64(20)}}},
			expectedAPI:    "condenser_api",
			expectedMethod: "call",
			expectedParam0: "condenser_api",
		},
		{
			name:           "call-style network_broadcast_api broadcast_transaction_synchronous",
			raw:            map[string]interface{}{"method": "call", "params": []interface{}{"network_broadcast_api", "broadcast_transaction_synchronous", []interface{}{map[string]interface{}{"ref_block_num": float64(62429)}}}},
			expectedAPI:    "condenser_api",
			expectedMethod: "call",
			expectedParam0: "condenser_api",
		},
		{
			name:           "call-style pre-appbase numeric API index 0",
			raw:            map[string]interface{}{"method": "call", "params": []interface{}{float64(0), "get_dynamic_global_properties", []interface{}{}}},
			expectedAPI:    "condenser_api",
			expectedMethod: "call",
			expectedParam0: "condenser_api",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := newTranslateRequest(t, tt.raw)
			translateToAppbase(req, router)

			if req.URN.API != tt.expectedAPI {
				t.Errorf("URN.API = %q, want %q", req.URN.API, tt.expectedAPI)
			}
			if req.Method != tt.expectedMethod {
				t.Errorf("Method = %q, want %q", req.Method, tt.expectedMethod)
			}
			if req.URN.Namespace != "appbase" {
				t.Errorf("URN.Namespace = %q, want %q (appbase for routing)", req.URN.Namespace, "appbase")
			}
			if tt.expectedParam0 != nil {
				paramsSlice, ok := req.Params.([]interface{})
				if !ok {
					t.Fatal("Params should be []interface{}")
				}
				if paramsSlice[0] != tt.expectedParam0 {
					t.Errorf("Params[0] = %v, want %v", paramsSlice[0], tt.expectedParam0)
				}
			}
		})
	}
}

func TestTranslateToAppbase_callStyle_preservesMethodAndArgs(t *testing.T) {
	router := newTestRouter("steemd")

	req := newTranslateRequest(t, map[string]interface{}{
		"method": "call",
		"params": []interface{}{"database_api", "get_state", []interface{}{"/@test/transfers"}},
	})

	translateToAppbase(req, router)

	paramsSlice := req.Params.([]interface{})
	if paramsSlice[1] != "get_state" {
		t.Errorf("Params[1] = %q, want %q", paramsSlice[1], "get_state")
	}
	args, ok := paramsSlice[2].([]interface{})
	if !ok {
		t.Fatal("Params[2] should be []interface{}")
	}
	if args[0] != "/@test/transfers" {
		t.Errorf("Params[2][0] = %q, want %q", args[0], "/@test/transfers")
	}
}

// Requests routed to other services (hivemind bridge.*, overseer, ...) must
// never be rewritten to condenser_api or rerouted to the steemd/appbase
// upstream, even when they use positional params.
func TestTranslateToAppbase_otherNamespacesPassthrough(t *testing.T) {
	router := newTestRouter("steemd")

	tests := []map[string]interface{}{
		{"method": "bridge.get_ranked_posts", "params": []interface{}{"trending", "", "", float64(20), ""}},
		{"method": "hivemind.bridge.get_ranked_posts", "params": []interface{}{"trending", "", "", float64(20), ""}},
		{"method": "bridge.get_account_posts", "params": map[string]interface{}{"account": "moecki"}},
	}

	for _, raw := range tests {
		req := newTranslateRequest(t, raw)
		origURN := req.URN.String()
		origNamespace := req.URN.Namespace

		translateToAppbase(req, router)

		if req.Method != raw["method"] {
			t.Errorf("%v: Method = %q, want unchanged %q", raw["method"], req.Method, raw["method"])
		}
		if req.URN.String() != origURN {
			t.Errorf("%v: URN = %q, want unchanged %q", raw["method"], req.URN.String(), origURN)
		}
		if req.URN.Namespace != origNamespace {
			t.Errorf("%v: Namespace = %q, want unchanged %q", raw["method"], req.URN.Namespace, origNamespace)
		}
	}
}

// Direct *_api.method requests with legacy positional args are translated
// when either the steemd or the appbase upstream enables the flag — so an
// appbase-only deployment with translate_to_appbase: true keeps working.
func TestTranslateToAppbase_appbaseFlagOnly(t *testing.T) {
	router := newTestRouter("appbase") // no steemd upstream configured

	req := newTranslateRequest(t, map[string]interface{}{
		"method": "database_api.get_state",
		"params": []interface{}{"/trending"},
	})

	translateToAppbase(req, router)

	if req.URN.API != "condenser_api" {
		t.Errorf("URN.API = %q, want %q", req.URN.API, "condenser_api")
	}
	if req.Method != "condenser_api.get_state" {
		t.Errorf("Method = %q, want %q", req.Method, "condenser_api.get_state")
	}
}

func TestTranslateToAppbase_condenserAPIUnchanged(t *testing.T) {
	router := newTestRouter("steemd")

	req := newTranslateRequest(t, map[string]interface{}{
		"method": "condenser_api.get_state",
		"params": []interface{}{"/trending"},
	})

	translateToAppbase(req, router)

	if req.URN.API != "condenser_api" {
		t.Errorf("URN.API should remain %q, got %q", "condenser_api", req.URN.API)
	}
	if req.Method != "condenser_api.get_state" {
		t.Errorf("Method should remain unchanged, got %q", req.Method)
	}
	if req.URN.Namespace != "appbase" {
		t.Errorf("URN.Namespace should remain %q, got %q", "appbase", req.URN.Namespace)
	}
}

func TestTranslateToAppbase_noTranslationWhenNotConfigured(t *testing.T) {
	router := newTestRouter() // empty - no translate_to_appbase

	tests := []map[string]interface{}{
		{"method": "get_block", "params": []interface{}{float64(1)}},
		{"method": "call", "params": []interface{}{"network_broadcast_api", "broadcast_transaction_synchronous", []interface{}{}}},
		{"method": "database_api.get_state", "params": []interface{}{"/trending"}},
	}

	for _, raw := range tests {
		req := newTranslateRequest(t, raw)
		translateToAppbase(req, router)

		if req.Method != raw["method"] {
			t.Errorf("Method = %q, want unchanged %q", req.Method, raw["method"])
		}
		if got, ok := req.Params.([]interface{}); ok && len(got) > 0 {
			if got[0] == "condenser_api" && raw["params"].([]interface{})[0] != "condenser_api" {
				t.Errorf("Params[0] rewritten to condenser_api, want unchanged")
			}
		}
	}
}

// Translated legacy requests must land on the appbase.condenser_api.* URNs so
// specific config entries (e.g. appbase.condenser_api.get_state → hivemind)
// keep matching.
func TestTranslateToAppbase_urnString(t *testing.T) {
	router := newTestRouter("steemd")

	req := newTranslateRequest(t, map[string]interface{}{
		"method": "call",
		"params": []interface{}{"database_api", "get_state", []interface{}{"/@user/transfers"}},
	})

	translateToAppbase(req, router)

	urnStr := req.URN.String()
	expectedPrefix := "appbase.condenser_api.get_state"
	if len(urnStr) < len(expectedPrefix) || urnStr[:len(expectedPrefix)] != expectedPrefix {
		t.Errorf("URN.String() = %q, want prefix %q", urnStr, expectedPrefix)
	}
}
