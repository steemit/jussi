package errors

// NewUpstreamCircuitOpenError creates an error for requests rejected by
// the upstream circuit breaker. CodeUpstreamResponseErr keeps client
// behaviour unchanged (same class as any other upstream failure); the
// distinguishing signal for operators is the details text and the
// jussi_upstream_circuit_state metric.
func NewUpstreamCircuitOpenError(message string) *JSONRPCError {
	return &JSONRPCError{
		Code:    CodeUpstreamResponseErr,
		Message: "Upstream temporarily unavailable",
		Data:    map[string]interface{}{"details": message},
	}
}
