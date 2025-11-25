package upstream

import (
	"fmt"
	"net/url"
	"strconv"
	"strings"

	"github.com/steemit/jussi/internal/config"
	"github.com/steemit/jussi/internal/urn"
)

// Router handles upstream routing based on URN
type Router struct {
	urls     *Trie
	ttls     *Trie
	timeouts *Trie
	namespaces map[string]bool
	translateToAppbase map[string]bool
}

// NewRouter creates a new upstream router from configuration
func NewRouter(upstreamConfig *config.UpstreamRawConfig) (*Router, error) {
	router := &Router{
		urls:      NewTrie(),
		ttls:      NewTrie(),
		timeouts:  NewTrie(),
		namespaces: make(map[string]bool),
		translateToAppbase: make(map[string]bool),
	}

	// Build routing tables from configuration
	for _, upstream := range upstreamConfig.Upstreams {
		router.namespaces[upstream.Name] = true
		if upstream.TranslateToAppbase {
			router.translateToAppbase[upstream.Name] = true
		}

		// Build URL trie
		for _, urlEntry := range upstream.URLs {
			if len(urlEntry) != 2 {
				continue
			}
			prefix, ok1 := urlEntry[0].(string)
			urlValue, ok2 := urlEntry[1].(string)
			if !ok1 || !ok2 {
				continue
			}
			router.urls.Insert(prefix, urlValue)
		}

		// Build TTL trie
		for _, ttlEntry := range upstream.TTLs {
			if len(ttlEntry) != 2 {
				continue
			}
			prefix, ok := ttlEntry[0].(string)
			if !ok {
				continue
			}
			ttlValue := parseTTL(ttlEntry[1])
			router.ttls.Insert(prefix, ttlValue)
		}

		// Build timeout trie
		for _, timeoutEntry := range upstream.Timeouts {
			if len(timeoutEntry) != 2 {
				continue
			}
			prefix, ok := timeoutEntry[0].(string)
			if !ok {
				continue
			}
			timeoutValue := parseTimeout(timeoutEntry[1])
			router.timeouts.Insert(prefix, timeoutValue)
		}
	}

	// Validate URLs if needed
	if err := router.validateURLs(); err != nil {
		return nil, fmt.Errorf("invalid upstream URLs: %w", err)
	}

	return router, nil
}

// GetUpstream returns upstream configuration for a given URN
func (r *Router) GetUpstream(urn *urn.URN) (*Upstream, error) {
	urnStr := urn.String()
	
	// Get URL
	_, urlValue, found := r.urls.LongestPrefix(urnStr)
	if !found {
		return nil, fmt.Errorf("no matching upstream URL for URN: %s", urnStr)
	}
	urlStr, ok := urlValue.(string)
	if !ok {
		return nil, fmt.Errorf("invalid URL type for URN: %s", urnStr)
	}

	// Validate URL format
	if !strings.HasPrefix(urlStr, "http://") && 
	   !strings.HasPrefix(urlStr, "https://") &&
	   !strings.HasPrefix(urlStr, "ws://") &&
	   !strings.HasPrefix(urlStr, "wss://") {
		return nil, fmt.Errorf("invalid URL format: %s", urlStr)
	}

	// Get TTL
	_, ttlValue, found := r.ttls.LongestPrefix(urnStr)
	ttl := 3 // default
	if found {
		if ttlInt, ok := ttlValue.(int); ok {
			ttl = ttlInt
		}
	}

	// Get timeout
	_, timeoutValue, found := r.timeouts.LongestPrefix(urnStr)
	timeout := 5 // default
	if found {
		if timeoutInt, ok := timeoutValue.(int); ok {
			timeout = timeoutInt
		}
	}

	return &Upstream{
		URL:     urlStr,
		TTL:     ttl,
		Timeout: timeout,
	}, nil
}

// ShouldTranslateToAppbase checks if a namespace should be translated to appbase format
func (r *Router) ShouldTranslateToAppbase(urn *urn.URN) bool {
	return r.translateToAppbase[urn.Namespace]
}

// GetNamespaces returns all configured namespaces
func (r *Router) GetNamespaces() []string {
	namespaces := make([]string, 0, len(r.namespaces))
	for ns := range r.namespaces {
		namespaces = append(namespaces, ns)
	}
	return namespaces
}

// validateURLs validates all upstream URLs
func (r *Router) validateURLs() error {
	// Collect all URLs
	urls := make(map[string]bool)
	
	// This is a simplified validation - in production, you might want to
	// actually test connectivity
	for _, upstream := range []*Trie{r.urls} {
		// For now, we'll validate during GetUpstream
		_ = upstream
	}
	
	_ = urls
	return nil
}

// Upstream represents upstream service configuration
type Upstream struct {
	URL     string
	TTL     int
	Timeout int
}

// parseTTL parses TTL value from configuration
func parseTTL(v interface{}) int {
	switch val := v.(type) {
	case float64:
		return int(val)
	case int:
		return val
	case string:
		if i, err := strconv.Atoi(val); err == nil {
			return i
		}
	}
	return 3 // default
}

// parseTimeout parses timeout value from configuration
func parseTimeout(v interface{}) int {
	switch val := v.(type) {
	case float64:
		return int(val)
	case int:
		return val
	case string:
		if i, err := strconv.Atoi(val); err == nil {
			return i
		}
	}
	return 5 // default
}

// ValidateURL validates a URL string
func ValidateURL(urlStr string) error {
	_, err := url.Parse(urlStr)
	return err
}

