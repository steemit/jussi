package ws

import (
	"context"
	"encoding/json"
	"fmt"
	"net"

	"github.com/gobwas/ws"
	"github.com/gobwas/ws/wsutil"
)

// Client represents a WebSocket client connection
type Client struct {
	conn net.Conn
}

// NewClient creates a new WebSocket client
func NewClient(url string) (*Client, error) {
	conn, _, _, err := ws.Dial(context.Background(), url)
	if err != nil {
		return nil, fmt.Errorf("failed to connect: %w", err)
	}

	return &Client{
		conn: conn,
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
	// Simple check - in production, implement proper ping/pong
	return c.conn != nil
}

