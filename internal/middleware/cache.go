package middleware

import (
	"context"
	"encoding/json"
	"time"

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

	// Parse request body without consuming it
	var body interface{}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.Next()
		return
	}
	
	// Store parsed body in context for later use
	c.Set("parsed_body", body)

		// Generate cache key from request
		cacheKey, err := generateCacheKey(body)
		if err != nil || cacheKey == "" {
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

		// Get response body
		responseBody, exists := c.Get("response_body")
		if !exists {
			return
		}

		bodyBytes, ok := responseBody.([]byte)
		if !ok || len(bodyBytes) == 0 {
			return
		}

		// Parse response
		var response interface{}
		if err := json.Unmarshal(bodyBytes, &response); err != nil {
			return
		}

		// Get TTL from context (set by processor)
		ttl, _ := c.Get("cache_ttl")
		ttlDuration := 3 * time.Second // Default
		if ttlInt, ok := ttl.(int); ok {
			ttlDuration = time.Duration(ttlInt) * time.Second
		}

		// Store in cache
		ctx := c.Request.Context()
		_ = cacheGroup.Set(ctx, cacheKey.(string), response, ttlDuration)
	}
}

// generateCacheKey generates a cache key from request
func generateCacheKey(request interface{}) (string, error) {
	// Handle single request
	if reqMap, ok := request.(map[string]interface{}); ok {
		return cache.GenerateCacheKeyFromRequest(reqMap)
	}
	
	// Handle batch request - use JSON string as key
	if batch, ok := request.([]interface{}); ok {
		data, err := json.Marshal(batch)
		if err != nil {
			return "", err
		}
		// For batch requests, use JSON string as cache key
		return string(data), nil
	}
	
	return "", nil
}

