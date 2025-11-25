package cache

import (
	"context"
	"sync"
	"time"
)

type memoryCacheEntry struct {
	value      interface{}
	expiresAt  time.Time
}

// MemoryCache implements an in-memory cache with TTL support
type MemoryCache struct {
	mu       sync.RWMutex
	data     map[string]*memoryCacheEntry
	maxTTL   time.Duration
}

// NewMemoryCache creates a new in-memory cache
func NewMemoryCache() *MemoryCache {
	return &MemoryCache{
		data: make(map[string]*memoryCacheEntry),
	}
}

// Get retrieves a value by key
func (c *MemoryCache) Get(ctx context.Context, key string) (interface{}, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	entry, exists := c.data[key]
	if !exists {
		return nil, nil
	}

	// Check expiration
	if !entry.expiresAt.IsZero() && time.Now().After(entry.expiresAt) {
		// Expired, but don't delete here (lazy deletion)
		return nil, nil
	}

	return entry.value, nil
}

// Set stores a value with optional expiration
func (c *MemoryCache) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	entry := &memoryCacheEntry{
		value: value,
	}

	if expiration > 0 {
		entry.expiresAt = time.Now().Add(expiration)
		// Track max TTL for optimization
		if expiration > c.maxTTL {
			c.maxTTL = expiration
		}
	}

	c.data[key] = entry
	return nil
}

// MGet retrieves multiple values by keys
func (c *MemoryCache) MGet(ctx context.Context, keys []string) ([]interface{}, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()

	results := make([]interface{}, len(keys))
	now := time.Now()

	for i, key := range keys {
		entry, exists := c.data[key]
		if !exists {
			results[i] = nil
			continue
		}

		// Check expiration
		if !entry.expiresAt.IsZero() && now.After(entry.expiresAt) {
			results[i] = nil
			continue
		}

		results[i] = entry.value
	}

	return results, nil
}

// SetMany stores multiple key-value pairs
func (c *MemoryCache) SetMany(ctx context.Context, data map[string]interface{}, expiration time.Duration) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	now := time.Now()
	for key, value := range data {
		entry := &memoryCacheEntry{
			value: value,
		}

		if expiration > 0 {
			entry.expiresAt = now.Add(expiration)
			if expiration > c.maxTTL {
				c.maxTTL = expiration
			}
		}

		c.data[key] = entry
	}

	return nil
}

// Delete removes a key
func (c *MemoryCache) Delete(ctx context.Context, key string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	delete(c.data, key)
	return nil
}

// Clear removes all keys
func (c *MemoryCache) Clear(ctx context.Context) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	c.data = make(map[string]*memoryCacheEntry)
	return nil
}

// Close closes the cache (no-op for memory cache)
func (c *MemoryCache) Close() error {
	return nil
}

// CleanupExpired removes expired entries (should be called periodically)
func (c *MemoryCache) CleanupExpired() {
	c.mu.Lock()
	defer c.mu.Unlock()

	now := time.Now()
	for key, entry := range c.data {
		if !entry.expiresAt.IsZero() && now.After(entry.expiresAt) {
			delete(c.data, key)
		}
	}
}

