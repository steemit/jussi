package upstream

import (
	"fmt"

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
// Panics if no upstream configuration is found
func (r *Router) GetUpstream(urn string) (*UpstreamInfo, bool) {
	// Try to get from configuration first
	url := r.getURLFromConfig(urn)
	if url == "" {
		panic(fmt.Sprintf("no upstream configuration found for URN: %s", urn))
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

	// Legacy format: collect from upstreams array
	if len(r.upstreamConfig.Upstreams) > 0 {
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
		if len(urls) > 0 {
			return urls
		}
		panic("steemd upstream is required but not found in configuration")
	}

	// Simplified format: collect from upstreams map
	if r.upstreamConfig.UpstreamsMap == nil {
		panic("upstreams configuration is required but not found")
	}

	// Collect from steemd
	if steemdRaw, ok := r.upstreamConfig.UpstreamsMap["steemd"]; ok {
		if urlList, ok := steemdRaw.([]interface{}); ok {
			for _, urlEntry := range urlList {
				if urlArray, ok := urlEntry.([]interface{}); ok && len(urlArray) >= 1 {
					if urlStr, ok := urlArray[0].(string); ok {
						if !urlSet[urlStr] {
							urls = append(urls, urlStr)
							urlSet[urlStr] = true
						}
					}
				}
			}
		}
		if len(urls) > 0 {
			return urls
		}
		panic("steemd upstream is configured but contains no valid URLs")
	}

	panic("steemd upstream is required but not found in configuration")
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
// Supports both Legacy format (upstreams array) and simplified format (upstreams object)
func (r *Router) parseUpstreamConfig() {
	if r.upstreamConfig == nil {
		return
	}

	// Check if Legacy format (array) is used
	if len(r.upstreamConfig.Upstreams) > 0 {
		r.parseLegacyFormat()
		return
	}

	// Otherwise, use simplified format (object map)
	if r.upstreamConfig.UpstreamsMap != nil {
		r.parseSimplifiedFormat()
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

// parseSimplifiedFormat parses simplified format: upstreams object map
func (r *Router) parseSimplifiedFormat() {
	// Parse steemd namespace
	if steemdRaw, ok := r.upstreamConfig.UpstreamsMap["steemd"]; ok {
		r.namespaces["steemd"] = true
		if urls, ok := steemdRaw.([]interface{}); ok {
			for _, urlEntry := range urls {
				if urlArray, ok := urlEntry.([]interface{}); ok && len(urlArray) >= 1 {
					if urlStr, ok := urlArray[0].(string); ok {
						r.urlTrie.Insert("steemd", urlStr)
						// Extract TTL and Timeout if provided [url, ttl, timeout]
						if len(urlArray) >= 2 {
							if ttl, ok := urlArray[1].(float64); ok {
								r.ttlTrie.Insert("steemd", int(ttl))
							} else if ttl, ok := urlArray[1].(int); ok {
								r.ttlTrie.Insert("steemd", ttl)
							}
						}
						if len(urlArray) >= 3 {
							if timeout, ok := urlArray[2].(float64); ok {
								r.timeoutTrie.Insert("steemd", int(timeout))
							} else if timeout, ok := urlArray[2].(int); ok {
								r.timeoutTrie.Insert("steemd", timeout)
							}
						}
					}
				}
			}
		}
	}

	// Parse appbase namespace
	if appbaseRaw, ok := r.upstreamConfig.UpstreamsMap["appbase"]; ok {
		if appbaseMap, ok := appbaseRaw.(map[string]interface{}); ok {
			for apiName, apiUrls := range appbaseMap {
				namespace := "appbase." + apiName
				r.namespaces[namespace] = true
				r.translateToAppbase[namespace] = true

				if urls, ok := apiUrls.([]interface{}); ok {
					for _, urlEntry := range urls {
						if urlArray, ok := urlEntry.([]interface{}); ok && len(urlArray) >= 1 {
							if urlStr, ok := urlArray[0].(string); ok {
								r.urlTrie.Insert(namespace, urlStr)
								// Extract TTL and Timeout if provided [url, ttl, timeout]
								if len(urlArray) >= 2 {
									if ttl, ok := urlArray[1].(float64); ok {
										r.ttlTrie.Insert(namespace, int(ttl))
									} else if ttl, ok := urlArray[1].(int); ok {
										r.ttlTrie.Insert(namespace, ttl)
									}
								}
								if len(urlArray) >= 3 {
									if timeout, ok := urlArray[2].(float64); ok {
										r.timeoutTrie.Insert(namespace, int(timeout))
									} else if timeout, ok := urlArray[2].(int); ok {
										r.timeoutTrie.Insert(namespace, timeout)
									}
								}
							}
						}
					}
				}
			}
		}
	}
}

// getURLFromConfig tries to get URL from configuration
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
	}

	return ""
}

// getTTLFromConfig gets TTL for a given URN using longest prefix matching
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
	}

	// Default TTL
	return 300
}

// getTimeoutFromConfig gets Timeout for a given URN using longest prefix matching
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

	// Legacy format: collect from upstreams array
	if len(r.upstreamConfig.Upstreams) > 0 {
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

	// Simplified format: collect from upstreams map
	if r.upstreamConfig.UpstreamsMap == nil {
		return urls
	}

	// Collect from steemd
	if steemdRaw, ok := r.upstreamConfig.UpstreamsMap["steemd"]; ok {
		if urlList, ok := steemdRaw.([]interface{}); ok {
			for _, urlEntry := range urlList {
				if urlArray, ok := urlEntry.([]interface{}); ok && len(urlArray) >= 1 {
					if urlStr, ok := urlArray[0].(string); ok {
						if !urlSet[urlStr] {
							urls = append(urls, urlStr)
							urlSet[urlStr] = true
						}
					}
				}
			}
		}
	}

	// Collect from appbase
	if appbaseRaw, ok := r.upstreamConfig.UpstreamsMap["appbase"]; ok {
		if appbaseMap, ok := appbaseRaw.(map[string]interface{}); ok {
			for _, apiUrls := range appbaseMap {
				if urlList, ok := apiUrls.([]interface{}); ok {
					for _, urlEntry := range urlList {
						if urlArray, ok := urlEntry.([]interface{}); ok && len(urlArray) >= 1 {
							if urlStr, ok := urlArray[0].(string); ok {
								if !urlSet[urlStr] {
									urls = append(urls, urlStr)
									urlSet[urlStr] = true
								}
							}
						}
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
