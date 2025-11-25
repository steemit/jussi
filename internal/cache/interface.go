package cache

import (
	"context"
	"time"
)

// Cache defines the interface for cache backends
type Cache interface {
	// Get retrieves a value by key
	Get(ctx context.Context, key string) (interface{}, error)
	
	// Set stores a value with optional expiration
	Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error
	
	// MGet retrieves multiple values by keys
	MGet(ctx context.Context, keys []string) ([]interface{}, error)
	
	// SetMany stores multiple key-value pairs
	SetMany(ctx context.Context, data map[string]interface{}, expiration time.Duration) error
	
	// Delete removes a key
	Delete(ctx context.Context, key string) error
	
	// Clear removes all keys
	Clear(ctx context.Context) error
	
	// Close closes the cache connection
	Close() error
}

