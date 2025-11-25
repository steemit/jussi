package cache

import (
	"time"
)

// TTL constants matching Python implementation
const (
	TTLNoExpire                    = 0
	TTLNoCache                     = -1
	TTLExpireIfIrreversible        = -2
	TTLDefault                     = 3
)

// CalculateTTL calculates the actual TTL value based on configuration and context
func CalculateTTL(configuredTTL int, isIrreversible bool, lastIrreversibleBlockNum int) time.Duration {
	switch configuredTTL {
	case TTLNoCache:
		return 0 // Don't cache
	case TTLNoExpire:
		return 0 // Cache forever (no expiration)
	case TTLExpireIfIrreversible:
		if isIrreversible {
			// Block is irreversible, cache forever
			return 0
		}
		// Block is not irreversible, don't cache
		return 0
	default:
		// Positive number means seconds
		if configuredTTL > 0 {
			return time.Duration(configuredTTL) * time.Second
		}
		// Default TTL
		return TTLDefault * time.Second
	}
}

// IsCacheable checks if a response should be cached based on TTL
func IsCacheable(ttl int) bool {
	return ttl != TTLNoCache
}

// ShouldExpire checks if cached value should expire
func ShouldExpire(ttl int) bool {
	return ttl != TTLNoExpire && ttl != TTLExpireIfIrreversible
}

