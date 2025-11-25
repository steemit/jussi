package cache

import (
	"encoding/json"
	"fmt"

	"github.com/steemit/jussi/internal/urn"
)

// GenerateCacheKey generates a cache key from URN
func GenerateCacheKey(urn *urn.URN) string {
	// Use URN string representation as cache key
	// This matches the Python implementation
	return urn.String()
}

// GenerateCacheKeyFromRequest generates a cache key from JSON-RPC request
func GenerateCacheKeyFromRequest(request map[string]interface{}) (string, error) {
	// Parse URN from request
	urn, err := urn.FromRequest(request)
	if err != nil {
		return "", fmt.Errorf("failed to parse URN: %w", err)
	}

	return GenerateCacheKey(urn), nil
}

// GenerateCacheKeyFromJSON generates a cache key from JSON string
func GenerateCacheKeyFromJSON(jsonData []byte) (string, error) {
	var request map[string]interface{}
	if err := json.Unmarshal(jsonData, &request); err != nil {
		return "", fmt.Errorf("failed to unmarshal: %w", err)
	}

	return GenerateCacheKeyFromRequest(request)
}

