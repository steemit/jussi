package helpers

// DeepCopyMap creates a deep copy of a map[string]interface{}.
// Nested maps and slices are recursively copied so that the returned
// map shares no references with the original.  This is essential for
// the cache layer: without a deep copy, concurrent batch goroutines
// would mutate the same cached map (e.g. overwriting the "id" field),
// causing response-id corruption and data races.
func DeepCopyMap(src map[string]interface{}) map[string]interface{} {
	if src == nil {
		return nil
	}
	dst := make(map[string]interface{}, len(src))
	for k, v := range src {
		switch val := v.(type) {
		case map[string]interface{}:
			dst[k] = DeepCopyMap(val)
		case []interface{}:
			dst[k] = DeepCopySlice(val)
		default:
			dst[k] = v
		}
	}
	return dst
}

// DeepCopySlice creates a deep copy of a []interface{}.
func DeepCopySlice(src []interface{}) []interface{} {
	if src == nil {
		return nil
	}
	dst := make([]interface{}, len(src))
	for i, v := range src {
		switch val := v.(type) {
		case map[string]interface{}:
			dst[i] = DeepCopyMap(val)
		case []interface{}:
			dst[i] = DeepCopySlice(val)
		default:
			dst[i] = v
		}
	}
	return dst
}
