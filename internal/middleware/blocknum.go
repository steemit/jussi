package middleware

import (
	"encoding/json"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
)

// BlockNumberTracker holds the block number tracker
var globalBlockTracker *cache.BlockNumberTracker

// InitBlockNumberTracker initializes the global block number tracker
func InitBlockNumberTracker() {
	globalBlockTracker = cache.NewBlockNumberTracker()
}

// GetBlockNumberTracker returns the global block number tracker
func GetBlockNumberTracker() *cache.BlockNumberTracker {
	if globalBlockTracker == nil {
		InitBlockNumberTracker()
	}
	return globalBlockTracker
}

// UpdateBlockNumberMiddleware updates the last irreversible block number from responses
func UpdateBlockNumberMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Process request
		c.Next()

		// Check if this is a get_dynamic_global_properties response
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
		var response map[string]interface{}
		if err := json.Unmarshal(bodyBytes, &response); err != nil {
			return
		}

		// Check if this is a get_dynamic_global_properties response
		// We need to check the original request to determine this
		// For now, we'll check the response structure
		result, ok := response["result"].(map[string]interface{})
		if !ok {
			return
		}

		// Check for last_irreversible_block_num field
		if lastIrreversibleBlockNum, exists := result["last_irreversible_block_num"]; exists {
			var blockNum int
			switch v := lastIrreversibleBlockNum.(type) {
			case int:
				blockNum = v
			case float64:
				blockNum = int(v)
			case string:
				if num, err := strconv.Atoi(v); err == nil {
					blockNum = num
				} else {
					return
				}
			default:
				return
			}

			// Update global tracker
			tracker := GetBlockNumberTracker()
			tracker.UpdateLastIrreversibleBlockNum(blockNum)
		}
	}
}

