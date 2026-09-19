package errors

// NewUpstreamCircuitOpenError creates an error for requests rejected by
// the upstream circuit breaker. CodeUpstreamResponseErr keeps client
// behaviour unchanged (same class as any other upstream failure). The
// message must not carry the upstream URL or hostname — the response is
// public; the identifying signals for operators are the
// jussi_upstream_circuit_state / rejects metrics and the server-side
// warn log at the rejection site.
func NewUpstreamCircuitOpenError(message string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeUpstreamResponseErr,
		Message: "Upstream temporarily unavailable",
		Data:    map[string]interface{}{"details": message},
	}
}
