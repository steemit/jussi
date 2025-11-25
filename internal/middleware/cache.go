package middleware

import (
	"context"
	"encoding/json"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
)

// CacheLookupMiddleware checks cache before processing request
func CacheLookupMiddleware(cacheGroup *cache.CacheGroup) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Only process POST requests
		if c.Request.Method != "POST" {
			c.Next()
			return
		}

		// Parse request body
		var body interface{}
		if err := c.ShouldBindJSON(&body); err != nil {
			c.Next()
			return
		}

		// Generate cache key from request
		cacheKey := generateCacheKey(body)
		if cacheKey == "" {
			c.Next()
			return
		}

		// Check cache
		ctx := context.Background()
		cachedValue, err := cacheGroup.Get(ctx, cacheKey)
		if err == nil && cachedValue != nil {
			// Cache hit - return cached response
			c.JSON(200, cachedValue)
			c.Header("x-jussi-cache-hit", cacheKey)
			c.Abort()
			return
		}

		// Cache miss - continue to next handler
		c.Set("cache_key", cacheKey)
		c.Next()
	}
}

// CacheStoreMiddleware stores response in cache
// Note: This is a simplified version. In production, you'd need to capture
// the response body using a custom response writer wrapper.
func CacheStoreMiddleware(cacheGroup *cache.CacheGroup) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Process response
		c.Next()

		// Check if response was cached
		if c.GetHeader("x-jussi-cache-hit") != "" {
			return
		}

		// Get cache key
		cacheKey, exists := c.Get("cache_key")
		if !exists || cacheKey == "" {
			return
		}

		// TODO: Capture response body for caching
		// This requires a custom response writer wrapper
		// For now, this is a placeholder
		_ = cacheGroup
		_ = cacheKey
	}
}

// generateCacheKey generates a cache key from request
func generateCacheKey(request interface{}) string {
	// Simple implementation - should use URN-based key generation
	data, err := json.Marshal(request)
	if err != nil {
		return ""
	}
	// In production, use proper URN-based key generation
	return string(data) // Placeholder
}

