package cache

import (
	"context"
	"encoding/json"
	"time"

	"github.com/redis/go-redis/v9"
)

// RedisCache implements Redis cache backend
type RedisCache struct {
	client *redis.Client
}

// NewRedisCache creates a new Redis cache from a URL.
// Prefer NewRedisCacheFromConfig in application code: ParseURL errors can
// echo the URL back, and a password-bearing URL should not end up in logs.
func NewRedisCache(redisURL string) (*RedisCache, error) {
	opt, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, err
	}

	return newRedisCacheFromOptions(opt)
}

// RedisCacheConfig carries the explicit Redis connection settings used to
// build go-redis options without round-tripping through a URL.
type RedisCacheConfig struct {
	Address      string
	Password     string
	DB           int
	PoolSize     int
	ReadTimeout  time.Duration
	WriteTimeout time.Duration
	DialTimeout  time.Duration
}

// NewRedisCacheFromConfig creates a new Redis cache from discrete settings.
func NewRedisCacheFromConfig(cfg RedisCacheConfig) (*RedisCache, error) {
	return newRedisCacheFromOptions(&redis.Options{
		Addr:         cfg.Address,
		Password:     cfg.Password,
		DB:           cfg.DB,
		PoolSize:     cfg.PoolSize,
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
		DialTimeout:  cfg.DialTimeout,
	})
}

func newRedisCacheFromOptions(opt *redis.Options) (*RedisCache, error) {
	client := redis.NewClient(opt)

	// Test connection
	ctx := context.Background()
	if err := client.Ping(ctx).Err(); err != nil {
		_ = client.Close()
		return nil, err
	}

	return &RedisCache{
		client: client,
	}, nil
}

// Get retrieves a value by key
func (c *RedisCache) Get(ctx context.Context, key string) (interface{}, error) {
	data, err := c.client.Get(ctx, key).Result()
	if err == redis.Nil {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	// Decompress and deserialize
	var value interface{}
	if err := json.Unmarshal([]byte(data), &value); err != nil {
		return nil, err
	}

	return value, nil
}

// Set stores a value with optional expiration
func (c *RedisCache) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	// Serialize and compress
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}

	return c.client.Set(ctx, key, data, expiration).Err()
}

// MGet retrieves multiple values by keys
func (c *RedisCache) MGet(ctx context.Context, keys []string) ([]interface{}, error) {
	results, err := c.client.MGet(ctx, keys...).Result()
	if err != nil {
		return nil, err
	}

	values := make([]interface{}, len(results))
	for i, result := range results {
		if result == nil {
			values[i] = nil
			continue
		}

		// Deserialize
		var value interface{}
		if err := json.Unmarshal([]byte(result.(string)), &value); err != nil {
			values[i] = nil
			continue
		}
		values[i] = value
	}

	return values, nil
}

// SetMany stores multiple key-value pairs
func (c *RedisCache) SetMany(ctx context.Context, data map[string]interface{}, expiration time.Duration) error {
	pipe := c.client.Pipeline()
	
	for key, value := range data {
		jsonData, err := json.Marshal(value)
		if err != nil {
			continue
		}
		pipe.Set(ctx, key, jsonData, expiration)
	}

	_, err := pipe.Exec(ctx)
	return err
}

// Delete removes a key
func (c *RedisCache) Delete(ctx context.Context, key string) error {
	return c.client.Del(ctx, key).Err()
}

// Clear removes all keys (use with caution!)
func (c *RedisCache) Clear(ctx context.Context) error {
	return c.client.FlushDB(ctx).Err()
}

// Close closes the Redis connection
func (c *RedisCache) Close() error {
	return c.client.Close()
}

