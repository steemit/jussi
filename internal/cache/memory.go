package cache

import (
	"context"
	"sync"
	"time"
)

// defaultMemoryCacheMaxEntries bounds the memory cache when no explicit
// max size is configured. Each entry holds a full JSON-RPC response, so
// 100k entries is already generous for a gateway cache tier.
const defaultMemoryCacheMaxEntries = 100000

// cleanupInterval controls how often the background goroutine removes
// expired entries. Lazy deletion in Get also removes entries on access,
// but keys that are never read again would otherwise leak forever.
const cleanupInterval = 30 * time.Second

type memoryCacheEntry struct {
	value     interface{}
	expiresAt time.Time
}

// MemoryCache implements an in-memory cache with TTL support, a bounded
// number of entries, and a background cleanup goroutine.
type MemoryCache struct {
	mu       sync.RWMutex
	data     map[string]*memoryCacheEntry
	maxSize  int
	stopOnce sync.Once
	stop     chan struct{}
}

// NewMemoryCache creates a new in-memory cache. The optional maxSize caps
// the number of stored entries; when the cap is reached, expired entries
// are purged and, if still at capacity, arbitrary entries are evicted.
// A non-positive maxSize falls back to defaultMemoryCacheMaxEntries.
func NewMemoryCache(maxSize ...int) *MemoryCache {
	limit := defaultMemoryCacheMaxEntries
	if len(maxSize) > 0 && maxSize[0] > 0 {
		limit = maxSize[0]
	}
	c := &MemoryCache{
		data:    make(map[string]*memoryCacheEntry),
		maxSize: limit,
		stop:    make(chan struct{}),
	}
	go c.cleanupLoop()
	return c
}

// cleanupLoop periodically removes expired entries until Close.
func (c *MemoryCache) cleanupLoop() {
	ticker := time.NewTicker(cleanupInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			c.CleanupExpired()
		case <-c.stop:
			return
		}
	}
}

// Get retrieves a value by key. Expired entries are removed on access.
func (c *MemoryCache) Get(ctx context.Context, key string) (interface{}, error) {
	c.mu.RLock()
	entry, exists := c.data[key]
	if !exists {
		c.mu.RUnlock()
		return nil, nil
	}
	expired := !entry.expiresAt.IsZero() && time.Now().After(entry.expiresAt)
	c.mu.RUnlock()

	if expired {
		c.mu.Lock()
		// Re-check under write lock: another goroutine may have removed or
		// replaced the entry in between.
		if cur, ok := c.data[key]; ok && cur == entry {
			delete(c.data, key)
		}
		c.mu.Unlock()
		return nil, nil
	}

	return entry.value, nil
}

// Set stores a value with optional expiration, enforcing the entry cap.
func (c *MemoryCache) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	if len(c.data) >= c.maxSize {
		c.evictLocked()
	}

	c.data[key] = &memoryCacheEntry{
		value:     value,
		expiresAt: expiryTime(expiration),
	}
	return nil
}

// MGet retrieves multiple values by keys
func (c *MemoryCache) MGet(ctx context.Context, keys []string) ([]interface{}, error) {
	results := make([]interface{}, len(keys))
	now := time.Now()

	c.mu.RLock()
	for i, key := range keys {
		entry, exists := c.data[key]
		if !exists {
			continue
		}
		if !entry.expiresAt.IsZero() && now.After(entry.expiresAt) {
			continue
		}
		results[i] = entry.value
	}
	c.mu.RUnlock()

	return results, nil
}

// SetMany stores multiple key-value pairs with optional expiration
func (c *MemoryCache) SetMany(ctx context.Context, data map[string]interface{}, expiration time.Duration) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	for key, value := range data {
		if len(c.data) >= c.maxSize {
			c.evictLocked()
		}
		c.data[key] = &memoryCacheEntry{
			value:     value,
			expiresAt: expiryTime(expiration),
		}
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

// Close stops the background cleanup goroutine
func (c *MemoryCache) Close() error {
	c.stopOnce.Do(func() { close(c.stop) })
	return nil
}

// CleanupExpired removes expired entries
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

// evictLocked makes room when the cache is at capacity. It must be called
// with c.mu held. Expired entries go first; if that is not enough, an
// arbitrary ~10% of remaining entries are dropped — responses are cache
// tiers, not databases, so random eviction is an acceptable trade for
// avoiding an O(n) oldest-entry scan on every insert.
func (c *MemoryCache) evictLocked() {
	now := time.Now()
	for key, entry := range c.data {
		if !entry.expiresAt.IsZero() && now.After(entry.expiresAt) {
			delete(c.data, key)
		}
	}
	if len(c.data) < c.maxSize {
		return
	}
	victims := len(c.data)/10 + 1
	for key := range c.data {
		if victims == 0 {
			break
		}
		delete(c.data, key)
		victims--
	}
}

func expiryTime(expiration time.Duration) time.Time {
	if expiration > 0 {
		return time.Now().Add(expiration)
	}
	return time.Time{}
}
