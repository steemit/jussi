package cache

import (
	"context"
	"testing"
	"time"
)

func TestCacheGroupGet(t *testing.T) {
	ctx := context.Background()
	mem1 := NewMemoryCache()
	mem2 := NewMemoryCache()
	mem3 := NewMemoryCache()

	cacheGroup := NewCacheGroup(mem1, mem2)
	// Note: Go implementation uses memory + redis, not multiple memory caches
	// So we test with memory as primary and nil as secondary for now

	// Set value in first cache
	err := mem1.Set(ctx, "key", "value1", 180*time.Second)
	if err != nil {
		t.Fatalf("failed to set in mem1: %v", err)
	}

	// Get should return value from first cache
	value, err := cacheGroup.Get(ctx, "key")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if value != "value1" {
		t.Errorf("expected 'value1', got %v", value)
	}

	// Delete from first cache
	err = mem1.Delete(ctx, "key")
	if err != nil {
		t.Fatalf("failed to delete from mem1: %v", err)
	}

	// Set in second cache (redis cache)
	err = mem2.Set(ctx, "key", "value2", 180*time.Second)
	if err != nil {
		t.Fatalf("failed to set in mem2: %v", err)
	}

	// Get should return value from second cache (fallback to redis)
	value, err = cacheGroup.Get(ctx, "key")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if value != "value2" {
		t.Errorf("expected 'value2', got %v", value)
	}

	// Value should also be promoted to memory cache
	value1, err := mem1.Get(ctx, "key")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if value1 != "value2" {
		t.Errorf("expected 'value2' to be promoted to mem1, got %v", value1)
	}

	// Delete from both caches
	err = mem1.Delete(ctx, "key")
	if err != nil {
		t.Fatalf("failed to delete from mem1: %v", err)
	}
	err = mem2.Delete(ctx, "key")
	if err != nil {
		t.Fatalf("failed to delete from mem2: %v", err)
	}

	// Get should return nil
	value, err = cacheGroup.Get(ctx, "key")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if value != nil {
		t.Errorf("expected nil, got %v", value)
	}

	_ = mem3 // Suppress unused variable warning
}

func TestCacheGroupSet(t *testing.T) {
	ctx := context.Background()
	mem1 := NewMemoryCache()
	mem2 := NewMemoryCache()

	cacheGroup := NewCacheGroup(mem1, mem2)

	// Set value in cache group
	err := cacheGroup.Set(ctx, "key", "value", 180*time.Second)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Both caches should have the value
	value1, err := mem1.Get(ctx, "key")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if value1 != "value" {
		t.Errorf("expected 'value' in mem1, got %v", value1)
	}

	value2, err := mem2.Get(ctx, "key")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if value2 != "value" {
		t.Errorf("expected 'value' in mem2, got %v", value2)
	}
}

func TestCacheGroupClear(t *testing.T) {
	ctx := context.Background()
	mem1 := NewMemoryCache()
	mem2 := NewMemoryCache()

	cacheGroup := NewCacheGroup(mem1, mem2)

	// Set values in both caches
	err := mem1.Set(ctx, "key1", "value1", 180*time.Second)
	if err != nil {
		t.Fatalf("failed to set in mem1: %v", err)
	}
	err = mem2.Set(ctx, "key2", "value2", 180*time.Second)
	if err != nil {
		t.Fatalf("failed to set in mem2: %v", err)
	}

	// Clear cache group
	err = cacheGroup.Clear(ctx)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Both caches should be empty
	value1, err := mem1.Get(ctx, "key1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if value1 != nil {
		t.Errorf("expected nil in mem1, got %v", value1)
	}

	value2, err := mem2.Get(ctx, "key2")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if value2 != nil {
		t.Errorf("expected nil in mem2, got %v", value2)
	}
}

func TestCacheGroupMGet(t *testing.T) {
	ctx := context.Background()
	mem1 := NewMemoryCache()
	mem2 := NewMemoryCache()

	cacheGroup := NewCacheGroup(mem1, mem2)

	keys := []string{"key0", "key1", "key2"}
	values := []interface{}{"value0", "value1", "value2"}

	// Set values in cache group
	for i, key := range keys {
		err := cacheGroup.Set(ctx, key, values[i], 180*time.Second)
		if err != nil {
			t.Fatalf("failed to set %s: %v", key, err)
		}
	}

	// MGet should return all values
	results, err := cacheGroup.MGet(ctx, keys)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(results) != len(values) {
		t.Errorf("expected %d results, got %d", len(values), len(results))
	}

	for i, result := range results {
		if result != values[i] {
			t.Errorf("expected %v at index %d, got %v", values[i], i, result)
		}
	}

	// Clear first cache
	err = mem1.Clear(ctx)
	if err != nil {
		t.Fatalf("failed to clear mem1: %v", err)
	}

	// MGet should still return values from second cache
	results, err = cacheGroup.MGet(ctx, keys)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	for i, result := range results {
		if result != values[i] {
			t.Errorf("expected %v at index %d, got %v", values[i], i, result)
		}
	}

	// Clear second cache
	err = mem2.Clear(ctx)
	if err != nil {
		t.Fatalf("failed to clear mem2: %v", err)
	}

	// MGet should return nil values (both caches cleared)
	// Note: values might still be in mem1 from the promotion, so clear it too
	err = mem1.Clear(ctx)
	if err != nil {
		t.Fatalf("failed to clear mem1: %v", err)
	}

	results, err = cacheGroup.MGet(ctx, keys)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	for i, result := range results {
		if result != nil {
			t.Errorf("expected nil at index %d, got %v", i, result)
		}
	}
}

func TestCacheGroupSetMany(t *testing.T) {
	ctx := context.Background()
	mem1 := NewMemoryCache()
	mem2 := NewMemoryCache()

	cacheGroup := NewCacheGroup(mem1, mem2)

	keys := []string{"key0", "key1", "key2"}
	values := []interface{}{"value0", "value1", "value2"}
	pairs := make(map[string]interface{})
	for i, key := range keys {
		pairs[key] = values[i]
	}

	// SetMany should store in both caches
	err := cacheGroup.SetMany(ctx, pairs, 180*time.Second)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Both caches should have all values
	for i, key := range keys {
		value1, err := mem1.Get(ctx, key)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if value1 != values[i] {
			t.Errorf("expected %v in mem1 for %s, got %v", values[i], key, value1)
		}

		value2, err := mem2.Get(ctx, key)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if value2 != values[i] {
			t.Errorf("expected %v in mem2 for %s, got %v", values[i], key, value2)
		}
	}
}

func TestCacheGroupGetPriority(t *testing.T) {
	ctx := context.Background()
	mem1 := NewMemoryCache()
	mem2 := NewMemoryCache()

	cacheGroup := NewCacheGroup(mem1, mem2)

	// Set different values in both caches
	err := mem1.Set(ctx, "key", "value1", 180*time.Second)
	if err != nil {
		t.Fatalf("failed to set in mem1: %v", err)
	}
	err = mem2.Set(ctx, "key", "value2", 180*time.Second)
	if err != nil {
		t.Fatalf("failed to set in mem2: %v", err)
	}

	// Get should return value from first cache (memory has priority)
	value, err := cacheGroup.Get(ctx, "key")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if value != "value1" {
		t.Errorf("expected 'value1' (from mem1), got %v", value)
	}
}

