package cache

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/steemit/steemgosdk/api"
	"github.com/steemit/jussi/internal/upstream"
)

// GlobalParamsInfo holds global parameters from the blockchain
type GlobalParamsInfo struct {
	HeadBlockNumber int64     `json:"head_block_number"`
	LastUpdate      time.Time `json:"last_update"`
}

// GlobalParams manages cached global blockchain parameters with TTL
type GlobalParams struct {
	params     *GlobalParamsInfo
	mutex      sync.RWMutex
	ttl        time.Duration
	router     *upstream.Router
	steemdURLs []string
}

// NewGlobalParams creates a new global params cache with 3 second TTL
// Requires router to get steemd URLs from configuration
func NewGlobalParams(router *upstream.Router) *GlobalParams {
	// Get steemd URLs from configuration (will panic if not configured)
	steemdURLs := router.GetSteemdURLs()
	
	return &GlobalParams{
		ttl:        3 * time.Second,
		router:     router,
		steemdURLs: steemdURLs,
	}
}

// GetHeadBlockNumber returns the latest block number, fetching if cache is stale
func (gp *GlobalParams) GetHeadBlockNumber(ctx context.Context) (int64, error) {
	gp.mutex.RLock()
	
	// Check if cache is still valid
	if gp.params != nil && time.Since(gp.params.LastUpdate) < gp.ttl {
		blockNum := gp.params.HeadBlockNumber
		gp.mutex.RUnlock()
		return blockNum, nil
	}
	gp.mutex.RUnlock()

	// Cache is stale or empty, fetch new data
	return gp.fetchAndCache(ctx)
}

// fetchAndCache fetches the latest global params and caches it
func (gp *GlobalParams) fetchAndCache(ctx context.Context) (int64, error) {
	gp.mutex.Lock()
	defer gp.mutex.Unlock()

	// Double-check in case another goroutine already updated
	if gp.params != nil && time.Since(gp.params.LastUpdate) < gp.ttl {
		return gp.params.HeadBlockNumber, nil
	}

	// Fetch from API
	blockNum, err := gp.fetchHeadBlockNumber(ctx)
	if err != nil {
		// If we have stale data, return it instead of error
		if gp.params != nil {
			return gp.params.HeadBlockNumber, nil
		}
		return 0, err
	}

	// Update cache
	gp.params = &GlobalParamsInfo{
		HeadBlockNumber: blockNum,
		LastUpdate:      time.Now(),
	}

	return blockNum, nil
}

// fetchHeadBlockNumber fetches the latest block number using steemgosdk
func (gp *GlobalParams) fetchHeadBlockNumber(ctx context.Context) (int64, error) {
	// Try each steemd URL until one succeeds
	for _, url := range gp.steemdURLs {
		blockNum, err := gp.trySteemdURL(ctx, url)
		if err == nil {
			return blockNum, nil
		}
	}

	return 0, fmt.Errorf("failed to fetch block number from all steemd endpoints")
}

// trySteemdURL tries to fetch block number from a specific steemd URL using steemgosdk
func (gp *GlobalParams) trySteemdURL(ctx context.Context, url string) (int64, error) {
	// Create API client using steemgosdk
	steemAPI := api.NewAPI(url)

	// Call get_dynamic_global_properties using steemgosdk
	// Note: steemgosdk doesn't support context, but we keep ctx parameter for future compatibility
	dgp, err := steemAPI.GetDynamicGlobalProperties()
	if err != nil {
		return 0, fmt.Errorf("steemgosdk GetDynamicGlobalProperties failed: %w", err)
	}

	// Convert UInt32 to int64
	return int64(dgp.HeadBlockNumber), nil
}

