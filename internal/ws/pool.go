package ws

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// Pool manages a pool of WebSocket connections
type Pool struct {
	url      string
	minSize  int
	maxSize  int
	clients  chan *Client
	mu       sync.Mutex
	active   int
}

// NewPool creates a new WebSocket connection pool
func NewPool(url string, minSize, maxSize int) (*Pool, error) {
	pool := &Pool{
		url:     url,
		minSize: minSize,
		maxSize: maxSize,
		clients: make(chan *Client, maxSize),
	}

	// Pre-populate pool
	for i := 0; i < minSize; i++ {
		client, err := NewClient(url)
		if err != nil {
			// Log error but continue
			continue
		}
		pool.clients <- client
		pool.active++
	}

	return pool, nil
}

// Acquire gets a client from the pool
func (p *Pool) Acquire(ctx context.Context) (*Client, error) {
	select {
	case client := <-p.clients:
		// Check if client is still alive
		if !client.IsAlive() {
			// Create new client
			newClient, err := NewClient(p.url)
			if err != nil {
				return nil, err
			}
			return newClient, nil
		}
		return client, nil
	case <-ctx.Done():
		return nil, ctx.Err()
	default:
		// Pool exhausted, create new connection if under max
		p.mu.Lock()
		if p.active < p.maxSize {
			p.active++
			p.mu.Unlock()
			return NewClient(p.url)
		}
		p.mu.Unlock()

		// Wait for available connection
		select {
		case client := <-p.clients:
			return client, nil
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(5 * time.Second):
			return nil, fmt.Errorf("timeout waiting for connection")
		}
	}
}

// Release returns a client to the pool
func (p *Pool) Release(client *Client) {
	if client == nil {
		return
	}

	// Check if client is still alive
	if !client.IsAlive() {
		p.mu.Lock()
		p.active--
		p.mu.Unlock()
		_ = client.Close()
		return
	}

	select {
	case p.clients <- client:
		// Successfully returned to pool
	default:
		// Pool full, close connection
		p.mu.Lock()
		p.active--
		p.mu.Unlock()
		_ = client.Close()
	}
}

// Close closes all connections in the pool
func (p *Pool) Close() error {
	close(p.clients)
	for client := range p.clients {
		_ = client.Close()
	}
	return nil
}

