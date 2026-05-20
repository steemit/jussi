package handlers

import (
	"strings"
	"testing"

	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/urn"
)

func TestTranslateLegacyAPI_directMethod(t *testing.T) {
	tests := []struct {
		name           string
		inputAPI       string
		inputMethod    string
		expectedAPI    string
		expectedMethod string
	}{
		{
			name:           "database_api.get_state → condenser_api.get_state",
			inputAPI:       "database_api",
			inputMethod:    "database_api.get_state",
			expectedAPI:    "condenser_api",
			expectedMethod: "condenser_api.get_state",
		},
		{
			name:           "database_api.get_dynamic_global_properties",
			inputAPI:       "database_api",
			inputMethod:    "database_api.get_dynamic_global_properties",
			expectedAPI:    "condenser_api",
			expectedMethod: "condenser_api.get_dynamic_global_properties",
		},
		{
			name:           "database_api.get_block",
			inputAPI:       "database_api",
			inputMethod:    "database_api.get_block",
			expectedAPI:    "condenser_api",
			expectedMethod: "condenser_api.get_block",
		},
		{
			name:           "database_api.get_account_history",
			inputAPI:       "database_api",
			inputMethod:    "database_api.get_account_history",
			expectedAPI:    "condenser_api",
			expectedMethod: "condenser_api.get_account_history",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := &request.JSONRPCRequest{
				Method: tt.inputMethod,
				URN: &urn.URN{
					Namespace: "appbase",
					API:       tt.inputAPI,
					Method:    tt.inputMethod[strings.Index(tt.inputMethod, ".")+1:],
				},
			}

			translateLegacyAPI(req)

			if req.URN.API != tt.expectedAPI {
				t.Errorf("URN.API = %q, want %q", req.URN.API, tt.expectedAPI)
			}
			if req.Method != tt.expectedMethod {
				t.Errorf("Method = %q, want %q", req.Method, tt.expectedMethod)
			}
			if req.URN.Namespace != "appbase" {
				t.Errorf("URN.Namespace = %q, want %q", req.URN.Namespace, "appbase")
			}
		})
	}
}

func TestTranslateLegacyAPI_callStyle(t *testing.T) {
	tests := []struct {
		name           string
		params         []interface{}
		expectedParam0 string
	}{
		{
			name:           "call get_state",
			params:         []interface{}{"database_api", "get_state", []interface{}{"/trending"}},
			expectedParam0: "condenser_api",
		},
		{
			name:           "call get_dynamic_global_properties",
			params:         []interface{}{"database_api", "get_dynamic_global_properties", []interface{}{}},
			expectedParam0: "condenser_api",
		},
		{
			name:           "call get_block",
			params:         []interface{}{"database_api", "get_block", []interface{}{106191898}},
			expectedParam0: "condenser_api",
		},
		{
			name:           "call get_account_history",
			params:         []interface{}{"database_api", "get_account_history", []interface{}{"user", -1, 20}},
			expectedParam0: "condenser_api",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := &request.JSONRPCRequest{
				Method: "call",
				Params: tt.params,
				URN: &urn.URN{
					Namespace: "steemd",
					API:       "database_api",
					Method:    tt.params[1].(string),
				},
			}

			translateLegacyAPI(req)

			// Method should remain "call"
			if req.Method != "call" {
				t.Errorf("Method = %q, want %q", req.Method, "call")
			}
			// URN should be translated
			if req.URN.API != "condenser_api" {
				t.Errorf("URN.API = %q, want %q", req.URN.API, "condenser_api")
			}
			if req.URN.Namespace != "appbase" {
				t.Errorf("URN.Namespace = %q, want %q", req.URN.Namespace, "appbase")
			}
			// params[0] should be translated
			paramsSlice, ok := req.Params.([]interface{})
			if !ok {
				t.Fatal("Params should be []interface{}")
			}
			if paramsSlice[0] != tt.expectedParam0 {
				t.Errorf("Params[0] = %q, want %q", paramsSlice[0], tt.expectedParam0)
			}
		})
	}
}

func TestTranslateLegacyAPI_callStyle_preservesMethodAndArgs(t *testing.T) {
	// Verify that params[1] (method name) and params[2] (args) are unchanged
	req := &request.JSONRPCRequest{
		Method: "call",
		Params: []interface{}{"database_api", "get_state", []interface{}{"/@test/transfers"}},
		URN: &urn.URN{
			Namespace: "steemd",
			API:       "database_api",
			Method:    "get_state",
		},
	}

	translateLegacyAPI(req)

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

func TestTranslateLegacyAPI_nonLegacyAPI(t *testing.T) {
	req := &request.JSONRPCRequest{
		Method: "condenser_api.get_state",
		URN: &urn.URN{
			Namespace: "appbase",
			API:       "condenser_api",
			Method:    "get_state",
		},
	}

	translateLegacyAPI(req)

	if req.URN.API != "condenser_api" {
		t.Errorf("URN.API should remain %q, got %q", "condenser_api", req.URN.API)
	}
	if req.Method != "condenser_api.get_state" {
		t.Errorf("Method should remain unchanged, got %q", req.Method)
	}
}

func TestTranslateLegacyAPI_followAPI(t *testing.T) {
	req := &request.JSONRPCRequest{
		Method: "follow_api.get_blog",
		URN: &urn.URN{
			Namespace: "appbase",
			API:       "follow_api",
			Method:    "get_blog",
		},
	}

	translateLegacyAPI(req)

	if req.URN.API != "follow_api" {
		t.Errorf("URN.API should remain %q, got %q", "follow_api", req.URN.API)
	}
}

func TestTranslateLegacyAPI_urnString(t *testing.T) {
	req := &request.JSONRPCRequest{
		Method: "database_api.get_state",
		URN: &urn.URN{
			Namespace: "appbase",
			API:       "database_api",
			Method:    "get_state",
			Params:    []interface{}{"/trending"},
		},
	}

	translateLegacyAPI(req)

	expectedURN := "appbase.condenser_api.get_state"
	if req.URN.API != "condenser_api" {
		t.Errorf("URN.API = %q, want %q", req.URN.API, "condenser_api")
	}
	if req.URN.Namespace != "appbase" {
		t.Errorf("URN.Namespace = %q, want %q", req.URN.Namespace, "appbase")
	}
	urnStr := req.URN.String()
	if !strings.HasPrefix(urnStr, expectedURN) {
		t.Errorf("URN.String() = %q, want prefix %q", urnStr, expectedURN)
	}
}

func TestTranslateLegacyAPI_callStyle_namespaceSwitch(t *testing.T) {
	// Verify that steemd namespace is switched to appbase for correct routing
	req := &request.JSONRPCRequest{
		Method: "call",
		Params: []interface{}{"database_api", "get_state", []interface{}{"/@user/transfers"}},
		URN: &urn.URN{
			Namespace: "steemd",
			API:       "database_api",
			Method:    "get_state",
		},
	}

	translateLegacyAPI(req)

	if req.URN.Namespace != "appbase" {
		t.Errorf("URN.Namespace = %q, want %q (appbase for routing to hivemind)", req.URN.Namespace, "appbase")
	}
	urnStr := req.URN.String()
	expectedPrefix := "appbase.condenser_api.get_state"
	if !strings.HasPrefix(urnStr, expectedPrefix) {
		t.Errorf("URN.String() = %q, want prefix %q", urnStr, expectedPrefix)
	}
}
