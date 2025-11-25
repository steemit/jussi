package upstream

// Trie implements a prefix trie for longest-prefix matching
// Used for routing JSON-RPC methods to upstream configurations
type Trie struct {
	root *trieNode
}

type trieNode struct {
	children map[string]*trieNode
	value    interface{}
}

// NewTrie creates a new empty trie
func NewTrie() *Trie {
	return &Trie{
		root: &trieNode{
			children: make(map[string]*trieNode),
		},
	}
}

// Insert inserts a key-value pair into the trie
// Key is a dot-separated string (e.g., "steemd.database_api.get_block")
func (t *Trie) Insert(key string, value interface{}) {
	parts := splitKey(key)
	node := t.root
	for _, part := range parts {
		if node.children[part] == nil {
			node.children[part] = &trieNode{
				children: make(map[string]*trieNode),
			}
		}
		node = node.children[part]
	}
	node.value = value
}

// LongestPrefix finds the longest matching prefix and returns the value
// Returns (matched prefix, value, true) if found, (empty, nil, false) otherwise
func (t *Trie) LongestPrefix(key string) (string, interface{}, bool) {
	parts := splitKey(key)
	node := t.root
	var matched []string
	var lastValue interface{}
	var found bool

	for _, part := range parts {
		if node.children[part] == nil {
			break
		}
		node = node.children[part]
		matched = append(matched, part)
		if node.value != nil {
			lastValue = node.value
			found = true
		}
	}

	if found {
		return joinKey(matched), lastValue, true
	}
	return "", nil, false
}

// splitKey splits a dot-separated key into parts
func splitKey(key string) []string {
	if key == "" {
		return []string{}
	}
	parts := []string{}
	start := 0
	for i := 0; i < len(key); i++ {
		if key[i] == '.' {
			if start < i {
				parts = append(parts, key[start:i])
			}
			start = i + 1
		}
	}
	if start < len(key) {
		parts = append(parts, key[start:])
	}
	return parts
}

// joinKey joins parts back into a dot-separated key
func joinKey(parts []string) string {
	if len(parts) == 0 {
		return ""
	}
	result := parts[0]
	for i := 1; i < len(parts); i++ {
		result += "." + parts[i]
	}
	return result
}

