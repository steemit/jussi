package cache

import (
	"testing"
	"time"
)

func TestCalculateTTL(t *testing.T) {
	tests := []struct {
		name                    string
		configTTL              int
		expectedTTL            time.Duration
	}{
		{
			name:                   "TTL no cache",
			configTTL:             TTLNoCache,
			expectedTTL:           0,
		},
		{
			name:                   "TTL no expire",
			configTTL:             TTLNoExpire,
			expectedTTL:           0,
		},
		{
			name:                   "TTL expire if irreversible",
			configTTL:             TTLExpireIfIrreversible,
			expectedTTL:           0 * time.Second,
		},
		{
			name:                   "Fixed TTL",
			configTTL:             300,
			expectedTTL:           300 * time.Second,
		},
		{
			name:                   "Default TTL",
			configTTL:             TTLDefault,
			expectedTTL:           3 * time.Second,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ttl := CalculateTTL(tt.configTTL, false, 0)
			
			if ttl != tt.expectedTTL {
				t.Errorf("expected TTL %v, got %v", tt.expectedTTL, ttl)
			}
		})
	}
}

func TestIsCacheable(t *testing.T) {
	tests := []struct {
		name      string
		ttl       int
		expected  bool
	}{
		{
			name:     "no cache",
			ttl:      TTLNoCache,
			expected: false,
		},
		{
			name:     "no expire",
			ttl:      TTLNoExpire,
			expected: true,
		},
		{
			name:     "expire if irreversible",
			ttl:      TTLExpireIfIrreversible,
			expected: true,
		},
		{
			name:     "fixed TTL",
			ttl:      300,
			expected: true,
		},
		{
			name:     "default TTL",
			ttl:      TTLDefault,
			expected: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsCacheable(tt.ttl)
			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
		})
	}
}

func TestShouldExpire(t *testing.T) {
	tests := []struct {
		name     string
		ttl      int
		expected bool
	}{
		{
			name:     "no expire",
			ttl:      TTLNoExpire,
			expected: false,
		},
		{
			name:     "expire if irreversible",
			ttl:      TTLExpireIfIrreversible,
			expected: true,
		},
		{
			name:     "fixed TTL",
			ttl:      300,
			expected: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := ShouldExpire(tt.ttl)
			if result != tt.expected {
				t.Errorf("expected %v, got %v", tt.expected, result)
			}
		})
	}
}
