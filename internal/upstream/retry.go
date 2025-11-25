package upstream

import (
	"context"
	"fmt"
	"math"
	"strings"
	"time"
)

// RetryConfig holds retry configuration
type RetryConfig struct {
	MaxRetries      int
	InitialBackoff  time.Duration
	MaxBackoff      time.Duration
	BackoffMultiplier float64
}

// DefaultRetryConfig returns default retry configuration
func DefaultRetryConfig() *RetryConfig {
	return &RetryConfig{
		MaxRetries:       3,
		InitialBackoff:   100 * time.Millisecond,
		MaxBackoff:       5 * time.Second,
		BackoffMultiplier: 2.0,
	}
}

// RetryableError indicates an error that can be retried
type RetryableError struct {
	Err error
}

func (e *RetryableError) Error() string {
	return fmt.Sprintf("retryable error: %v", e.Err)
}

func (e *RetryableError) Unwrap() error {
	return e.Err
}

// IsRetryableError checks if an error is retryable
func IsRetryableError(err error) bool {
	if err == nil {
		return false
	}
	
	// Network errors, timeouts, and 5xx errors are retryable
	errStr := err.Error()
	retryablePatterns := []string{
		"timeout",
		"connection refused",
		"connection reset",
		"no such host",
		"network is unreachable",
		"temporary failure",
		"502",
		"503",
		"504",
	}
	
	for _, pattern := range retryablePatterns {
		if contains(errStr, pattern) {
			return true
		}
	}
	
	return false
}

// Retry executes a function with retry logic
func Retry(ctx context.Context, config *RetryConfig, fn func() error) error {
	var lastErr error
	
	for attempt := 0; attempt <= config.MaxRetries; attempt++ {
		if attempt > 0 {
			// Calculate backoff
			backoff := time.Duration(float64(config.InitialBackoff) * math.Pow(config.BackoffMultiplier, float64(attempt-1)))
			if backoff > config.MaxBackoff {
				backoff = config.MaxBackoff
			}
			
			// Wait before retry
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(backoff):
			}
		}
		
		// Execute function
		err := fn()
		if err == nil {
			return nil
		}
		
		lastErr = err
		
		// Check if error is retryable
		if !IsRetryableError(err) {
			return err
		}
	}
	
	return fmt.Errorf("max retries exceeded: %w", lastErr)
}

// RetryWithResult executes a function with retry logic and returns a result
func RetryWithResult[T any](ctx context.Context, config *RetryConfig, fn func() (T, error)) (T, error) {
	var zero T
	var lastErr error
	
	for attempt := 0; attempt <= config.MaxRetries; attempt++ {
		if attempt > 0 {
			// Calculate backoff
			backoff := time.Duration(float64(config.InitialBackoff) * math.Pow(config.BackoffMultiplier, float64(attempt-1)))
			if backoff > config.MaxBackoff {
				backoff = config.MaxBackoff
			}
			
			// Wait before retry
			select {
			case <-ctx.Done():
				return zero, ctx.Err()
			case <-time.After(backoff):
			}
		}
		
		// Execute function
		result, err := fn()
		if err == nil {
			return result, nil
		}
		
		lastErr = err
		
		// Check if error is retryable
		if !IsRetryableError(err) {
			return zero, err
		}
	}
	
	return zero, fmt.Errorf("max retries exceeded: %w", lastErr)
}

// contains checks if a string contains a substring (case-insensitive)
func contains(s, substr string) bool {
	return strings.Contains(strings.ToLower(s), strings.ToLower(substr))
}

