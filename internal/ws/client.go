package ws

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"sync"
	"time"

	"github.com/gobwas/ws"
	"github.com/gobwas/ws/wsutil"
)

// Client represents a WebSocket client connection
type Client struct {
	conn      net.Conn
	lastPing  time.Time
	mu        sync.RWMutex
}

var (
	pingInterval = 30 * time.Second
	pingTimeout  = 5 * time.Second
)

// NewClient creates a new WebSocket client
func NewClient(url string) (*Client, error) {
	conn, _, _, err := ws.Dial(context.Background(), url)
	if err != nil {
		return nil, fmt.Errorf("failed to connect: %w", err)
	}

	return &Client{
		conn:     conn,
		lastPing: time.Now(),
	}, nil
}

// Send sends a message
func (c *Client) Send(ctx context.Context, payload map[string]interface{}) error {
	data, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal: %w", err)
	}

	return wsutil.WriteClientMessage(c.conn, ws.OpText, data)
}

// Receive receives a message
func (c *Client) Receive(ctx context.Context) (map[string]interface{}, error) {
	msg, _, err := wsutil.ReadServerData(c.conn)
	if err != nil {
		return nil, fmt.Errorf("failed to read: %w", err)
	}

	var result map[string]interface{}
	if err := json.Unmarshal(msg, &result); err != nil {
		return nil, fmt.Errorf("failed to unmarshal: %w", err)
	}

	return result, nil
}

// Close closes the connection
func (c *Client) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// IsAlive checks if connection is alive
func (c *Client) IsAlive() bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	
	if c.conn == nil {
		return false
	}
	
	// Check if we need to ping
	now := time.Now()
	if now.Sub(c.lastPing) > pingInterval {
		// Try to ping
		if err := c.ping(); err != nil {
			return false
		}
		c.mu.Lock()
		c.lastPing = now
		c.mu.Unlock()
	}
	
	return true
}

// ping sends a ping frame to check connection health
func (c *Client) ping() error {
	c.mu.RLock()
	conn := c.conn
	c.mu.RUnlock()
	
	if conn == nil {
		return fmt.Errorf("connection is nil")
	}
	
	// Set write deadline
	if err := conn.SetWriteDeadline(time.Now().Add(pingTimeout)); err != nil {
		return err
	}
	
	// Send ping frame
	return ws.WriteFrame(conn, ws.NewPingFrame(nil))
}

