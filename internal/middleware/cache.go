package middleware

import (
	"context"
	"encoding/json"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
	"github.com/steemit/jussi/internal/helpers"
)

// CacheLookupMiddleware checks cache before processing request
func CacheLookupMiddleware(cacheGroup *cache.CacheGroup) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Only process POST requests
		if c.Request.Method != "POST" {
			c.Next()
			return
		}

		// Use the body parsed by BodyParseMiddleware; fall back to parsing
		// ourselves only when that middleware is not in the chain (tests).
		var body interface{}
		if parsed, ok := ParsedBody(c); ok {
			body = parsed
		} else if err := c.ShouldBindJSON(&body); err != nil {
			c.Next()
			return
		} else {
			c.Set("parsed_body", body)
		}

		// Skip cache lookup for batch requests; they are cached
		// at the individual request level by the processor.
		if _, isBatch := body.([]interface{}); isBatch {
			c.Next()
			return
		}

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
			// Cache hit - inject current request's id into cached response
			// to avoid returning a stale id from a previous request.
			if cachedResp, ok := cachedValue.(map[string]interface{}); ok {
				if reqMap, ok := body.(map[string]interface{}); ok {
					// Deep copy the cached map to avoid mutating the shared
					// cache reference (memory cache returns the original pointer).
					respCopy := helpers.DeepCopyMap(cachedResp)
					respCopy["id"] = reqMap["id"]
					c.Header("x-jussi-cache-hit", cacheKey)
					c.JSON(200, respCopy)
					c.Abort()
					return
				}
			}
			c.Header("x-jussi-cache-hit", cacheKey)
			c.JSON(200, cachedValue)
			c.Abort()
			return
		}

		// Cache miss - continue to next handler
		c.Set("cache_key", cacheKey)
		c.Next()
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
