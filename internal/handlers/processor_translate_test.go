package handlers

import (
	"strings"
	"testing"

	"github.com/steemit/jussi/internal/request"
	"github.com/steemit/jussi/internal/urn"
)

func TestTranslateLegacyAPI_databaseAPI(t *testing.T) {
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
		})
	}
}

func TestTranslateLegacyAPI_nonLegacyAPI(t *testing.T) {
	// Non-legacy APIs should not be translated
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
	// follow_api is NOT a legacy API, should not be translated
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
	// Verify the URN string is correct after translation for routing purposes
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
	// URN.String() with params appends params=..., so check prefix
	if req.URN.API != "condenser_api" {
		t.Errorf("URN.API = %q, want %q", req.URN.API, "condenser_api")
	}
	// The URN string should start with the expected prefix for routing
	urnStr := req.URN.String()
	if !strings.HasPrefix(urnStr, expectedURN) {
		t.Errorf("URN.String() = %q, want prefix %q", urnStr, expectedURN)
	}
}
