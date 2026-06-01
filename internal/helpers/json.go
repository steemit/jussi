package helpers

import (
	"bytes"
	"encoding/json"
	"fmt"
)

// MarshalJSONWithoutHTMLEscape serializes v to JSON with HTML escaping
// disabled. This function MUST be used for all upstream request serialization
// instead of json.Marshal.
//
// # Background
//
// Go's encoding/json package escapes HTML special characters by default:
//
//	<  → \u003c
//	>  → \u003e
//	&  → \u0026
//
// This behavior is documented in json.Marshal:
// "String values encode as JSON strings coercing invalid UTF-8 and replacing
// HTML characters <, >, and & with \u003c, \u003e, and \u0026 so that the JSON
// will be safe to embed inside HTML <script> tags."
//
// # Root Cause
//
// steemd (the Steem blockchain node) uses the FC (Fast Compiling) library's
// JSON parser, which does NOT understand \uXXXX Unicode escape sequences.
// When FC's parseEscape() encounters a backslash, it reads the next character
// and handles only a limited set: \t, \n, \r, \\, and a few others. For any
// other character (including 'u'), it returns the literal character without
// interpreting the escape.
//
// This means \u003e is parsed as five literal characters: 'u', '0', '0', '3', 'e',
// instead of the single character '>'.
//
// # Impact
//
// When jussi-next forwards a broadcast_transaction request to steemd, if the
// transaction body contains '>' (common in Markdown blockquotes), Go's
// json.Marshal would escape it to \u003e. steemd's FC parser would then see
// 'u003e' instead of '>'. The body content no longer matches what was signed
// by the client, causing signature verification to fail with:
//
//	"Missing Posting Authority"
//
// This bug only affects posts/comments that contain HTML special characters.
// Short comments without these characters are unaffected.
//
// # Why jussi-legacy (Python) worked
//
// Python's json.dumps() does NOT escape < > & by default, so the literal
// characters were preserved end-to-end.
//
// # Trailing newline handling
//
// json.Encoder.Encode() appends a trailing '\n' for stream-friendliness
// (so multiple encoded values can be concatenated and still parsed correctly).
// We strip this newline with bytes.TrimSuffix to match json.Marshal's
// behavior and ensure byte-exact payloads, which is important for:
//
//   - Content-Length calculation
//   - Signature verification (any byte difference breaks the signature)
//   - Consistency with json.Marshal expectations throughout the codebase
//
// # Usage
//
// Use this function for ALL upstream request serialization. Do NOT use
// json.Marshal for request bodies that will be sent to steemd.
//
//	// Correct
//	body, err := helpers.MarshalJSONWithoutHTMLEscape(payload)
//
//	// Incorrect - will break transaction signatures
//	body, err := json.Marshal(payload)
func MarshalJSONWithoutHTMLEscape(v interface{}) ([]byte, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return nil, fmt.Errorf("failed to marshal JSON: %w", err)
	}
	// json.Encoder.Encode appends a trailing newline for stream-friendliness.
	// Strip it to match json.Marshal behavior and keep byte-exact payloads.
	return bytes.TrimSuffix(buf.Bytes(), []byte("\n")), nil
}
