// Package wire defines the control-plane ↔ Agent WebSocket JSON protocol.
//
// It is aligned with the backend implementation in apps/node/ws/wire.py.
// All frame types, parsing, and uplink builders live here for a single place to read or change the protocol.
package wire
