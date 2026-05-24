package middleware

import (
	"net"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

// LocalhostOnlyMiddleware restricts access to localhost only
func LocalhostOnlyMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Get client IP
		clientIP := c.ClientIP()
		
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
		clientIP := c.ClientIP()
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
