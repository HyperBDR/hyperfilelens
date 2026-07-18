package remote

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/gorilla/websocket"

	"hyperfilelens/agent/internal/infra/config"
	"hyperfilelens/agent/internal/platform/tlsclient"
)

// Session is a short-lived WebSocket uplink for CLI one-shot commands.
type Session struct {
	conn *websocket.Conn
}

// Connect dials the control plane once using the effective agent configuration.
func Connect(ctx context.Context, provider config.Provider) (*Session, error) {
	if provider == nil {
		return nil, ErrNotConnected
	}
	cfg := provider.Current()
	wss := strings.TrimSpace(cfg.WSSURL)
	if wss == "" {
		return nil, fmt.Errorf("HFL_WSS_URL not configured (set via agent.env or hfl-agent config set)")
	}

	u, err := url.Parse(wss)
	if err != nil {
		return nil, err
	}
	q := u.Query()
	if q.Get("node_id") == "" && strings.TrimSpace(cfg.NodeID) != "" {
		q.Set("node_id", strings.TrimSpace(cfg.NodeID))
	}
	if q.Get("token") == "" && strings.TrimSpace(cfg.NodeToken) != "" {
		q.Set("token", strings.TrimSpace(cfg.NodeToken))
	}
	u.RawQuery = q.Encode()

	dialer := websocket.Dialer{
		HandshakeTimeout: handshakeTimeout,
		Proxy:            http.ProxyFromEnvironment,
		TLSClientConfig:  tlsclient.Config(),
	}
	conn, resp, err := dialer.DialContext(ctx, u.String(), nil)
	if err != nil {
		if resp != nil {
			_ = resp.Body.Close()
		}
		return nil, err
	}
	_ = conn.SetReadDeadline(time.Time{})
	_ = conn.SetWriteDeadline(time.Time{})
	return &Session{conn: conn}, nil
}

// SendJSON sends one uplink JSON frame.
func (s *Session) SendJSON(ctx context.Context, payload any) error {
	if s == nil || s.conn == nil {
		return ErrNotConnected
	}
	_ = ctx
	return s.conn.WriteJSON(payload)
}

// Close closes the WebSocket session.
func (s *Session) Close() error {
	if s == nil || s.conn == nil {
		return nil
	}
	err := s.conn.Close()
	s.conn = nil
	return err
}

// Ensure Session implements config.Provider-independent sender at call sites via wire.Sender.
var _ interface {
	SendJSON(context.Context, any) error
} = (*Session)(nil)
