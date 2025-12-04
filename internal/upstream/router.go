package upstream

import (
	"github.com/steemit/jussi/internal/config"
)

// UpstreamInfo holds upstream configuration information
type UpstreamInfo struct {
	URL     string
	TTL     int
	Timeout int
}

// Router handles upstream routing
type Router struct {
	urlTrie            *Trie
	ttlTrie            *Trie
	timeoutTrie        *Trie
	namespaces         map[string]bool
	translateToAppbase map[string]bool
	upstreamConfig     *config.UpstreamRawConfig
}

// NewRouter creates a new router with the given upstream configuration
func NewRouter(upstreamConfig *config.UpstreamRawConfig) (*Router, error) {
	router := &Router{
		urlTrie:            NewTrie(),
		ttlTrie:            NewTrie(),
		timeoutTrie:        NewTrie(),
		namespaces:         make(map[string]bool),
		translateToAppbase: make(map[string]bool),
		upstreamConfig:     upstreamConfig,
	}

	// Parse upstream configuration if available
	if upstreamConfig != nil {
		router.parseUpstreamConfig()
	}

	return router, nil
}

// GetUpstream returns upstream information for a given URN
// Returns false if no upstream configuration is found
func (r *Router) GetUpstream(urn string) (*UpstreamInfo, bool) {
	// Try to get from configuration first
	url := r.getURLFromConfig(urn)
	if url == "" {
		return nil, false
	}

	// Get TTL and Timeout from configuration (with longest prefix matching)
	ttl := r.getTTLFromConfig(urn)
	timeout := r.getTimeoutFromConfig(urn)

	return &UpstreamInfo{
		URL:     url,
		TTL:     ttl,
		Timeout: timeout,
	}, true
}

// ShouldTranslateToAppbase returns whether the namespace should be translated to appbase
func (r *Router) ShouldTranslateToAppbase(namespace string) bool {
	return r.translateToAppbase[namespace]
}

// GetSteemdURLs returns all configured steemd URLs
// Panics if steemd is not configured (required for global params)
func (r *Router) GetSteemdURLs() []string {
	var urls []string
	urlSet := make(map[string]bool)

	if r.upstreamConfig == nil {
		panic("upstream configuration is required but not found")
	}

	// Collect from upstreams array
	if len(r.upstreamConfig.Upstreams) == 0 {
		panic("upstreams configuration is required but not found")
	}

	for _, upstream := range r.upstreamConfig.Upstreams {
		if upstream.Name == "steemd" {
			for _, urlEntry := range upstream.URLs {
				if len(urlEntry) >= 2 {
					if url, ok := urlEntry[1].(string); ok {
						if !urlSet[url] {
							urls = append(urls, url)
							urlSet[url] = true
						}
					}
				}
			}
		}
	}

	if len(urls) == 0 {
		panic("steemd upstream is required but not found in configuration")
	}

	return urls
}

// GetAllURLs returns all configured URLs
func (r *Router) GetAllURLs() []string {
	urls := r.getAllURLsFromConfig()
	if len(urls) == 0 {
		panic("upstreams configuration is required but contains no URLs")
	}
	return urls
}

// GetNamespaces returns all configured namespaces
func (r *Router) GetNamespaces() []string {
	namespaces := make([]string, 0, len(r.namespaces))
	for namespace := range r.namespaces {
		namespaces = append(namespaces, namespace)
	}
	return namespaces
}

// parseUpstreamConfig parses the upstream configuration
// Uses Legacy format: upstreams array with urls/ttls/timeouts
func (r *Router) parseUpstreamConfig() {
	if r.upstreamConfig == nil {
		return
	}

	// Parse Legacy format (array)
	if len(r.upstreamConfig.Upstreams) > 0 {
		r.parseLegacyFormat()
	}
}

// parseLegacyFormat parses Legacy format: upstreams array with urls/ttls/timeouts
func (r *Router) parseLegacyFormat() {
	for _, upstream := range r.upstreamConfig.Upstreams {
		name := upstream.Name
		r.namespaces[name] = true

		if upstream.TranslateToAppbase {
			r.translateToAppbase[name] = true
		}

		// Parse URLs
		for _, urlEntry := range upstream.URLs {
			if len(urlEntry) >= 2 {
				if namespace, ok := urlEntry[0].(string); ok {
					if url, ok := urlEntry[1].(string); ok {
						r.urlTrie.Insert(namespace, url)
					}
				}
			}
		}

		// Parse TTLs (fine-grained: namespace.api.method)
		for _, ttlEntry := range upstream.TTLs {
			if len(ttlEntry) >= 2 {
				if pattern, ok := ttlEntry[0].(string); ok {
					var ttl int
					switch v := ttlEntry[1].(type) {
					case float64:
						ttl = int(v)
					case int:
						ttl = v
					}
					r.ttlTrie.Insert(pattern, ttl)
				}
			}
		}

		// Parse Timeouts (fine-grained: namespace.api.method)
		for _, timeoutEntry := range upstream.Timeouts {
			if len(timeoutEntry) >= 2 {
				if pattern, ok := timeoutEntry[0].(string); ok {
					var timeout int
					switch v := timeoutEntry[1].(type) {
					case float64:
						timeout = int(v)
					case int:
						timeout = v
					}
					r.timeoutTrie.Insert(pattern, timeout)
				}
			}
		}
	}
}

// getURLFromConfig tries to get URL from configuration
// Falls back to appbase or steemd if namespace is not configured
func (r *Router) getURLFromConfig(urn string) string {
	// Try exact match first
	if _, value, found := r.urlTrie.LongestPrefix(urn); found {
		if urlStr, ok := value.(string); ok {
			return urlStr
		}
	}

	// Try namespace-based lookup
	parts := splitURN(urn)
	if len(parts) > 0 {
		namespace := parts[0]
		if _, value, found := r.urlTrie.LongestPrefix(namespace); found {
			if urlStr, ok := value.(string); ok {
				return urlStr
			}
		}

		// Fallback: if namespace not found, try appbase first, then steemd
		// This matches legacy behavior where unconfigured namespaces fall back to appbase/steemd
		if namespace != "appbase" && namespace != "steemd" {
			// Try appbase
			if _, value, found := r.urlTrie.LongestPrefix("appbase"); found {
				if urlStr, ok := value.(string); ok {
					return urlStr
				}
			}
			// Try steemd
			if _, value, found := r.urlTrie.LongestPrefix("steemd"); found {
				if urlStr, ok := value.(string); ok {
					return urlStr
				}
			}
		}
	}

	return ""
}

// getTTLFromConfig gets TTL for a given URN using longest prefix matching
// Falls back to appbase or steemd if namespace is not configured
func (r *Router) getTTLFromConfig(urn string) int {
	// Try longest prefix match
	if _, value, found := r.ttlTrie.LongestPrefix(urn); found {
		if ttl, ok := value.(int); ok {
			return ttl
		}
	}

	// Try namespace-based lookup
	parts := splitURN(urn)
	if len(parts) > 0 {
		namespace := parts[0]
		if _, value, found := r.ttlTrie.LongestPrefix(namespace); found {
			if ttl, ok := value.(int); ok {
				return ttl
			}
		}

		// Fallback: if namespace not found, try appbase first, then steemd
		if namespace != "appbase" && namespace != "steemd" {
			// Try appbase
			if _, value, found := r.ttlTrie.LongestPrefix("appbase"); found {
				if ttl, ok := value.(int); ok {
					return ttl
				}
			}
			// Try steemd
			if _, value, found := r.ttlTrie.LongestPrefix("steemd"); found {
				if ttl, ok := value.(int); ok {
					return ttl
				}
			}
		}
	}

	// Default TTL
	return 3
}

// getTimeoutFromConfig gets Timeout for a given URN using longest prefix matching
// Falls back to appbase or steemd if namespace is not configured
func (r *Router) getTimeoutFromConfig(urn string) int {
	// Try longest prefix match
	if _, value, found := r.timeoutTrie.LongestPrefix(urn); found {
		if timeout, ok := value.(int); ok {
			return timeout
		}
	}

	// Try namespace-based lookup
	parts := splitURN(urn)
	if len(parts) > 0 {
		namespace := parts[0]
		if _, value, found := r.timeoutTrie.LongestPrefix(namespace); found {
			if timeout, ok := value.(int); ok {
				return timeout
			}
		}

		// Fallback: if namespace not found, try appbase first, then steemd
		if namespace != "appbase" && namespace != "steemd" {
			// Try appbase
			if _, value, found := r.timeoutTrie.LongestPrefix("appbase"); found {
				if timeout, ok := value.(int); ok {
					return timeout
				}
			}
			// Try steemd
			if _, value, found := r.timeoutTrie.LongestPrefix("steemd"); found {
				if timeout, ok := value.(int); ok {
					return timeout
				}
			}
		}
	}

	// Default timeout
	return 30
}

// getAllURLsFromConfig collects all URLs from configuration
// Returns empty slice if no configuration (caller should panic)
func (r *Router) getAllURLsFromConfig() []string {
	var urls []string
	urlSet := make(map[string]bool)

	if r.upstreamConfig == nil {
		return urls
	}

	// Collect from upstreams array
	for _, upstream := range r.upstreamConfig.Upstreams {
		for _, urlEntry := range upstream.URLs {
			if len(urlEntry) >= 2 {
				if url, ok := urlEntry[1].(string); ok {
					if !urlSet[url] {
						urls = append(urls, url)
						urlSet[url] = true
					}
				}
			}
		}
	}

	return urls
}

// splitURN splits a URN into its components
func splitURN(urn string) []string {
	// Simple split by dot for now
	// TODO: Implement proper URN parsing
	parts := []string{}
	current := ""
	for _, char := range urn {
		if char == '.' {
			if current != "" {
				parts = append(parts, current)
				current = ""
			}
		} else {
			current += string(char)
		}
	}
	if current != "" {
		parts = append(parts, current)
	}
	return parts
}
