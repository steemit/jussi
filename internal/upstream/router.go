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
	if upstreamConfig != nil && upstreamConfig.UpstreamsRaw != nil {
		router.parseUpstreamConfig()
	}

	return router, nil
}

// GetUpstream returns upstream information for a given URN
func (r *Router) GetUpstream(urn string) (*UpstreamInfo, bool) {
	// Try to get from configuration first
	if url := r.getURLFromConfig(urn); url != "" {
		return &UpstreamInfo{
			URL:     url,
			TTL:     300,
			Timeout: 30,
		}, true
	}

	// Fallback to hardcoded default only if config is not available
	return &UpstreamInfo{
		URL:     "https://api.steem.fans",
		TTL:     300,
		Timeout: 30,
	}, true
}

// ShouldTranslateToAppbase returns whether the namespace should be translated to appbase
func (r *Router) ShouldTranslateToAppbase(namespace string) bool {
	return r.translateToAppbase[namespace]
}

// GetAllURLs returns all configured URLs
func (r *Router) GetAllURLs() []string {
	urls := r.getAllURLsFromConfig()
	if len(urls) > 0 {
		return urls
	}

	// Fallback to hardcoded default
	return []string{"https://api.steem.fans"}
}

// GetNamespaces returns all configured namespaces
func (r *Router) GetNamespaces() []string {
	namespaces := make([]string, 0, len(r.namespaces))
	for namespace := range r.namespaces {
		namespaces = append(namespaces, namespace)
	}
	return namespaces
}

// parseUpstreamConfig parses the upstream configuration from UpstreamsRaw
func (r *Router) parseUpstreamConfig() {
	if r.upstreamConfig == nil || r.upstreamConfig.UpstreamsRaw == nil {
		return
	}

	// Parse steemd namespace
	if steemdRaw, ok := r.upstreamConfig.UpstreamsRaw["steemd"]; ok {
		r.namespaces["steemd"] = true
		if urls, ok := steemdRaw.([]interface{}); ok {
			for _, urlEntry := range urls {
				if urlArray, ok := urlEntry.([]interface{}); ok && len(urlArray) >= 1 {
					if urlStr, ok := urlArray[0].(string); ok {
						r.urlTrie.Insert("steemd", urlStr)
					}
				}
			}
		}
	}

	// Parse appbase namespace
	if appbaseRaw, ok := r.upstreamConfig.UpstreamsRaw["appbase"]; ok {
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

// getAllURLsFromConfig collects all URLs from configuration
func (r *Router) getAllURLsFromConfig() []string {
	var urls []string

	if r.upstreamConfig == nil || r.upstreamConfig.UpstreamsRaw == nil {
		return urls
	}

	// Collect from steemd
	if steemdRaw, ok := r.upstreamConfig.UpstreamsRaw["steemd"]; ok {
		if urlList, ok := steemdRaw.([]interface{}); ok {
			for _, urlEntry := range urlList {
				if urlArray, ok := urlEntry.([]interface{}); ok && len(urlArray) >= 1 {
					if urlStr, ok := urlArray[0].(string); ok {
						urls = append(urls, urlStr)
					}
				}
			}
		}
	}

	// Collect from appbase
	if appbaseRaw, ok := r.upstreamConfig.UpstreamsRaw["appbase"]; ok {
		if appbaseMap, ok := appbaseRaw.(map[string]interface{}); ok {
			for _, apiUrls := range appbaseMap {
				if urlList, ok := apiUrls.([]interface{}); ok {
					for _, urlEntry := range urlList {
						if urlArray, ok := urlEntry.([]interface{}); ok && len(urlArray) >= 1 {
							if urlStr, ok := urlArray[0].(string); ok {
								// Avoid duplicates
								found := false
								for _, existing := range urls {
									if existing == urlStr {
										found = true
										break
									}
								}
								if !found {
									urls = append(urls, urlStr)
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
