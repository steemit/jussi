package cache

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"
)

// BlockInfo holds the latest block information
type BlockInfo struct {
	HeadBlockNumber int64     `json:"head_block_number"`
	LastUpdate      time.Time `json:"last_update"`
}

// BlockCache manages cached block information with TTL
type BlockCache struct {
	blockInfo *BlockInfo
	mutex     sync.RWMutex
	ttl       time.Duration
	client    *http.Client
}

// NewBlockCache creates a new block cache with 3 second TTL
func NewBlockCache() *BlockCache {
	return &BlockCache{
		ttl: 3 * time.Second,
		client: &http.Client{
			Timeout: 5 * time.Second,
		},
	}
}

// GetLatestBlockNumber returns the latest block number, fetching if cache is stale
func (bc *BlockCache) GetLatestBlockNumber(ctx context.Context) (int64, error) {
	bc.mutex.RLock()
	
	// Check if cache is still valid
	if bc.blockInfo != nil && time.Since(bc.blockInfo.LastUpdate) < bc.ttl {
		blockNum := bc.blockInfo.HeadBlockNumber
		bc.mutex.RUnlock()
		return blockNum, nil
	}
	bc.mutex.RUnlock()

	// Cache is stale or empty, fetch new data
	return bc.fetchAndCache(ctx)
}

// fetchAndCache fetches the latest block info and caches it
func (bc *BlockCache) fetchAndCache(ctx context.Context) (int64, error) {
	bc.mutex.Lock()
	defer bc.mutex.Unlock()

	// Double-check in case another goroutine already updated
	if bc.blockInfo != nil && time.Since(bc.blockInfo.LastUpdate) < bc.ttl {
		return bc.blockInfo.HeadBlockNumber, nil
	}

	// Fetch from API
	blockNum, err := bc.fetchLatestBlockNumber(ctx)
	if err != nil {
		// If we have stale data, return it instead of error
		if bc.blockInfo != nil {
			return bc.blockInfo.HeadBlockNumber, nil
		}
		return 0, err
	}

	// Update cache
	bc.blockInfo = &BlockInfo{
		HeadBlockNumber: blockNum,
		LastUpdate:      time.Now(),
	}

	return blockNum, nil
}

// fetchLatestBlockNumber fetches the latest block number from the API
func (bc *BlockCache) fetchLatestBlockNumber(ctx context.Context) (int64, error) {
	// Create JSON-RPC request
	reqBody := map[string]interface{}{
		"jsonrpc": "2.0",
		"method":  "get_dynamic_global_properties",
		"params":  []interface{}{},
		"id":      1,
	}

	reqBytes, err := json.Marshal(reqBody)
	if err != nil {
		return 0, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Try multiple endpoints
	endpoints := []string{
		"https://api.steemit.com",
		"https://api.justyy.com",
	}

	for _, endpoint := range endpoints {
		blockNum, err := bc.tryEndpoint(ctx, endpoint, reqBytes)
		if err == nil {
			return blockNum, nil
		}
	}

	return 0, fmt.Errorf("failed to fetch block number from all endpoints")
}

// tryEndpoint tries to fetch block number from a specific endpoint
func (bc *BlockCache) tryEndpoint(ctx context.Context, endpoint string, reqBytes []byte) (int64, error) {
	req, err := http.NewRequestWithContext(ctx, "POST", endpoint, 
		bytes.NewReader(reqBytes))
	if err != nil {
		return 0, err
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := bc.client.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return 0, fmt.Errorf("HTTP %d", resp.StatusCode)
	}

	var result struct {
		Result struct {
			HeadBlockNumber int64 `json:"head_block_number"`
		} `json:"result"`
		Error *struct {
			Code    int    `json:"code"`
			Message string `json:"message"`
		} `json:"error"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, err
	}

	if result.Error != nil {
		return 0, fmt.Errorf("API error: %s", result.Error.Message)
	}

	return result.Result.HeadBlockNumber, nil
}
