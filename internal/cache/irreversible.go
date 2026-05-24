package cache

import (
	"fmt"
	"strconv"
)

// BlockNumberTracker tracks the last irreversible block number
type BlockNumberTracker struct {
	lastIrreversibleBlockNum int
}

// NewBlockNumberTracker creates a new block number tracker
func NewBlockNumberTracker() *BlockNumberTracker {
	return &BlockNumberTracker{
		lastIrreversibleBlockNum: 0,
	}
}

// UpdateLastIrreversibleBlockNum updates the last irreversible block number
func (b *BlockNumberTracker) UpdateLastIrreversibleBlockNum(blockNum int) {
	if blockNum > b.lastIrreversibleBlockNum {
		b.lastIrreversibleBlockNum = blockNum
	}
}

// GetLastIrreversibleBlockNum returns the last irreversible block number
func (b *BlockNumberTracker) GetLastIrreversibleBlockNum() int {
	return b.lastIrreversibleBlockNum
}

// BlockNumFromJSONRPCResponse extracts block number from a JSON-RPC response
func BlockNumFromJSONRPCResponse(response map[string]interface{}) (int, error) {
	// Try to get block number from result
	result, ok := response["result"]
	if !ok {
		return 0, fmt.Errorf("no result in response")
	}

	resultMap, ok := result.(map[string]interface{})
	if !ok {
		return 0, fmt.Errorf("result is not a map")
	}

	// Try different possible fields for block number
	var blockNum int
	var err error

	// Try "block_num" field
	if blockNumVal, exists := resultMap["block_num"]; exists {
		switch v := blockNumVal.(type) {
		case int:
			blockNum = v
		case float64:
			blockNum = int(v)
		case string:
			blockNum, err = strconv.Atoi(v)
			if err != nil {
				return 0, fmt.Errorf("invalid block_num format: %w", err)
			}
		default:
			return 0, fmt.Errorf("unsupported block_num type")
		}
		return blockNum, nil
	}

	// Try "block" -> "block_id" (extract from block ID)
	if block, exists := resultMap["block"]; exists {
		blockMap, ok := block.(map[string]interface{})
		if ok {
			if blockID, exists := blockMap["block_id"]; exists {
				blockIDStr, ok := blockID.(string)
				if ok && len(blockIDStr) >= 8 {
					// Block ID starts with block number in hex
					blockNumHex := blockIDStr[:8]
					blockNumInt, err := strconv.ParseInt(blockNumHex, 16, 32)
					if err == nil {
						return int(blockNumInt), nil
					}
				}
			}
		}
	}

	// Try "block_id" directly
	if blockID, exists := resultMap["block_id"]; exists {
		blockIDStr, ok := blockID.(string)
		if ok && len(blockIDStr) >= 8 {
			// Block ID starts with block number in hex
			blockNumHex := blockIDStr[:8]
			blockNumInt, err := strconv.ParseInt(blockNumHex, 16, 32)
			if err == nil {
				return int(blockNumInt), nil
			}
		}
	}

	return 0, fmt.Errorf("could not extract block number from response")
}

// IsBlockIrreversible checks if a block is irreversible
func IsBlockIrreversible(responseBlockNum int, lastIrreversibleBlockNum int) bool {
	return responseBlockNum <= lastIrreversibleBlockNum
}

// IrreversibleTTL calculates TTL based on block irreversibility
// Returns TTLDefault if block is irreversible, TTLNoCache otherwise
func IrreversibleTTL(response map[string]interface{}, lastIrreversibleBlockNum int) int {
	if response == nil {
		return TTLNoCache
	}

	if lastIrreversibleBlockNum <= 0 {
		// Invalid or missing last irreversible block number
		return TTLNoCache
	}

	responseBlockNum, err := BlockNumFromJSONRPCResponse(response)
	if err != nil {
		// Could not extract block number, don't cache
		return TTLNoCache
	}

	if IsBlockIrreversible(responseBlockNum, lastIrreversibleBlockNum) {
		// Block is irreversible, use default TTL
		return TTLDefault
	}

	// Block is not irreversible, don't cache
	return TTLNoCache
}

