package middleware

import (
	"net"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

// LocalhostOnlyMiddleware restricts access to localhost only.
//
// In production deployments behind a reverse proxy (e.g. AWS ELB,
// CloudFlare, nginx), the immediate client IP is the proxy's IP, not the
// original caller.  To correctly enforce localhost-only access in such
// environments, the middleware first checks the X-Forwarded-For header
// (when present) and falls back to the connection-level IP.  If you run
// jussi without a reverse proxy, the connection-level IP is used directly.
func LocalhostOnlyMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		clientIP := resolveClientIP(c)

		// Parse the IP
		ip := net.ParseIP(clientIP)
		if ip == nil {
			c.JSON(http.StatusForbidden, gin.H{
				"error": "Access denied: invalid IP address",
			})
			c.Abort()
			return
		}

		// Check if it's localhost
		if !isLocalhost(ip, clientIP) {
			c.JSON(http.StatusForbidden, gin.H{
				"error": "Access denied: metrics endpoint only accessible from localhost",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}

// resolveClientIP returns the best-effort client IP.
// When behind a trusted reverse proxy, X-Forwarded-For contains the
// original client IP.  Otherwise the gin connection IP is used.
func resolveClientIP(c *gin.Context) string {
	// Check X-Forwarded-For header first
	forwarded := c.GetHeader("X-Forwarded-For")
	if forwarded != "" {
		// X-Forwarded-For can contain multiple IPs: client, proxy1, proxy2, ...
		// The left-most is the original client.
		parts := strings.Split(forwarded, ",")
		if len(parts) > 0 {
			candidate := strings.TrimSpace(parts[0])
			if candidate != "" {
				return candidate
			}
		}
	}

	// Fall back to X-Real-Ip
	realIP := c.GetHeader("X-Real-Ip")
	if realIP != "" {
		return realIP
	}

	// Fall back to gin's connection-level IP
	return c.ClientIP()
}

// isLocalhost checks if the IP is localhost
func isLocalhost(ip net.IP, clientIP string) bool {
	// Check for IPv4 localhost
	if ip.Equal(net.IPv4(127, 0, 0, 1)) {
		return true
	}

	// Check for IPv6 localhost
	if ip.Equal(net.IPv6loopback) {
		return true
	}

	// Check for string representations
	if clientIP == "127.0.0.1" || clientIP == "::1" || clientIP == "localhost" {
		return true
	}

	// Check if it's in the 127.0.0.0/8 range
	if ip.To4() != nil {
		return ip.To4()[0] == 127
	}

	return false
}

// IPWhitelistMiddleware restricts access to whitelisted IPs
func IPWhitelistMiddleware(allowedIPs []string) gin.HandlerFunc {
	// Parse allowed IPs once
	var allowedNets []*net.IPNet
	var allowedIPAddrs []net.IP

	for _, ipStr := range allowedIPs {
		// Try to parse as CIDR
		if strings.Contains(ipStr, "/") {
			_, ipNet, err := net.ParseCIDR(ipStr)
			if err == nil {
				allowedNets = append(allowedNets, ipNet)
				continue
			}
		}

		// Try to parse as IP
		if ip := net.ParseIP(ipStr); ip != nil {
			allowedIPAddrs = append(allowedIPAddrs, ip)
		}
	}

	return func(c *gin.Context) {
		clientIP := resolveClientIP(c)
		ip := net.ParseIP(clientIP)

		if ip == nil {
			c.JSON(http.StatusForbidden, gin.H{
				"error": "Access denied: invalid IP address",
			})
			c.Abort()
			return
		}

		// Check against allowed IPs
		for _, allowedIP := range allowedIPAddrs {
			if ip.Equal(allowedIP) {
				c.Next()
				return
			}
		}

		// Check against allowed networks
		for _, allowedNet := range allowedNets {
			if allowedNet.Contains(ip) {
				c.Next()
				return
			}
		}

		c.JSON(http.StatusForbidden, gin.H{
			"error": "Access denied: IP not in whitelist",
		})
		c.Abort()
	}
}
