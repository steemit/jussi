package cache

import (
	"context"
	"time"
)

// CacheGroup manages multiple cache tiers (memory + Redis)
type CacheGroup struct {
	memoryCache Cache
	redisCache  Cache
}

// NewCacheGroup creates a new cache group
func NewCacheGroup(memoryCache Cache, redisCache Cache) *CacheGroup {
	return &CacheGroup{
		memoryCache: memoryCache,
		redisCache:  redisCache,
	}
}

// Get retrieves a value, checking memory first, then Redis
func (cg *CacheGroup) Get(ctx context.Context, key string) (interface{}, error) {
	// Try memory cache first
	if cg.memoryCache != nil {
		value, err := cg.memoryCache.Get(ctx, key)
		if err == nil && value != nil {
			return value, nil
		}
	}

	// Fall back to Redis
	if cg.redisCache != nil {
		value, err := cg.redisCache.Get(ctx, key)
		if err == nil && value != nil {
			// Store in memory cache for next time
			if cg.memoryCache != nil {
				_ = cg.memoryCache.Set(ctx, key, value, 0) // No expiration for memory
			}
			return value, nil
		}
	}

	return nil, nil
}

// MGet retrieves multiple values
func (cg *CacheGroup) MGet(ctx context.Context, keys []string) ([]interface{}, error) {
	results := make([]interface{}, len(keys))
	missingKeys := make([]string, 0)

	// Check memory cache first
	if cg.memoryCache != nil {
		memoryResults, err := cg.memoryCache.MGet(ctx, keys)
		if err == nil {
			for i, value := range memoryResults {
				results[i] = value
				if value == nil {
					missingKeys = append(missingKeys, keys[i])
				}
			}
		} else {
			missingKeys = keys
		}
	} else {
		missingKeys = keys
	}

	// If all found in memory, return
	if len(missingKeys) == 0 {
		return results, nil
	}

	// Check Redis for missing keys
	if cg.redisCache != nil {
		redisResults, err := cg.redisCache.MGet(ctx, missingKeys)
		if err == nil {
			missingIndex := 0
			for i, key := range keys {
				if results[i] == nil && missingIndex < len(redisResults) {
					value := redisResults[missingIndex]
					results[i] = value
					// Store in memory if found
					if value != nil && cg.memoryCache != nil {
						_ = cg.memoryCache.Set(ctx, key, value, 0)
					}
					missingIndex++
				}
			}
		}
	}

	return results, nil
}

// Set stores a value in both caches
func (cg *CacheGroup) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	var err error

	if cg.memoryCache != nil {
		if memErr := cg.memoryCache.Set(ctx, key, value, expiration); memErr != nil {
			err = memErr
		}
	}

	if cg.redisCache != nil {
		if redisErr := cg.redisCache.Set(ctx, key, value, expiration); redisErr != nil {
			if err == nil {
				err = redisErr
			}
		}
	}

	return err
}

// SetMany stores multiple key-value pairs
func (cg *CacheGroup) SetMany(ctx context.Context, data map[string]interface{}, expiration time.Duration) error {
	var err error

	if cg.memoryCache != nil {
		if memErr := cg.memoryCache.SetMany(ctx, data, expiration); memErr != nil {
			err = memErr
		}
	}

	if cg.redisCache != nil {
		if redisErr := cg.redisCache.SetMany(ctx, data, expiration); redisErr != nil {
			if err == nil {
				err = redisErr
			}
		}
	}

	return err
}

// Delete removes a key from both caches
func (cg *CacheGroup) Delete(ctx context.Context, key string) error {
	var err error

	if cg.memoryCache != nil {
		if memErr := cg.memoryCache.Delete(ctx, key); memErr != nil {
			err = memErr
		}
	}

	if cg.redisCache != nil {
		if redisErr := cg.redisCache.Delete(ctx, key); redisErr != nil {
			if err == nil {
				err = redisErr
			}
		}
	}

	return err
}

// Clear clears both caches
func (cg *CacheGroup) Clear(ctx context.Context) error {
	var err error

	if cg.memoryCache != nil {
		if memErr := cg.memoryCache.Clear(ctx); memErr != nil {
			err = memErr
		}
	}

	if cg.redisCache != nil {
		if redisErr := cg.redisCache.Clear(ctx); redisErr != nil {
			if err == nil {
				err = redisErr
			}
		}
	}

	return err
}

// Close closes all cache connections
func (cg *CacheGroup) Close() error {
	var err error

	if cg.memoryCache != nil {
		if memErr := cg.memoryCache.Close(); memErr != nil {
			err = memErr
		}
	}

	if cg.redisCache != nil {
		if redisErr := cg.redisCache.Close(); redisErr != nil {
			if err == nil {
				err = redisErr
			}
		}
	}

	return err
}

