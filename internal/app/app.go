package app

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/steemit/jussi/internal/cache"
	"github.com/steemit/jussi/internal/config"
	"github.com/steemit/jussi/internal/handlers"
	"github.com/steemit/jussi/internal/logging"
	"github.com/steemit/jussi/internal/middleware"
	"github.com/steemit/jussi/internal/telemetry"
	"github.com/steemit/jussi/internal/upstream"
	"github.com/steemit/jussi/internal/ws"
	"go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin"
)

// App represents the application
type App struct {
	config      *config.Config
	logger      *logging.Logger
	cacheGroup  *cache.CacheGroup
	router      *upstream.Router
	httpClient  *upstream.HTTPClient
	wsPools     map[string]*ws.Pool
	shutdown    func()
}

// NewApp creates a new application instance
func NewApp(cfg *config.Config) (*App, error) {
	// Validate configuration
	if err := config.ValidateConfig(cfg); err != nil {
		return nil, fmt.Errorf("configuration validation failed: %w", err)
	}

	logger := logging.NewLogger(
		cfg.Logging.Level,
		cfg.Logging.Format,
		cfg.Logging.Output,
		cfg.Logging.IncludeCaller,
	)

	// Initialize cache
	cacheGroup, err := initCache(cfg, logger)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize cache: %w", err)
	}

	// Initialize upstream router
	router, err := upstream.NewRouter(cfg.Upstream.RawConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize router: %w", err)
	}

	// Validate upstream URLs if enabled
	if cfg.Upstream.TestURLs {
		if err := upstream.ValidateUpstreamURLs(cfg); err != nil {
			logger.Warn().Err(err).Msg("Upstream URL validation failed, continuing anyway")
			// Don't fail startup if URL validation fails, just log a warning
		}
	}

	// Initialize HTTP client
	httpClient := upstream.NewHTTPClient()

	// Initialize WebSocket pools
	wsPools, err := initWebSocketPools(cfg, router, logger)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize WebSocket pools: %w", err)
	}

	// Initialize OpenTelemetry
	shutdownTelemetry, err := telemetry.Setup(
		cfg.Telemetry.ServiceName,
		cfg.Telemetry.TracesEndpoint,
	)
	if err != nil {
		logger.Error().Err(err).Msg("Failed to initialize OpenTelemetry")
	}

	app := &App{
		config:     cfg,
		logger:     logger,
		cacheGroup: cacheGroup,
		router:     router,
		httpClient: httpClient,
		wsPools:    wsPools,
		shutdown:   shutdownTelemetry,
	}

	return app, nil
}

// initCache initializes the cache system
func initCache(cfg *config.Config, logger *logging.Logger) (*cache.CacheGroup, error) {
	var memoryCache cache.Cache = cache.NewMemoryCache()
	var redisCache cache.Cache

	if cfg.Cache.RedisURL != "" {
		redis, err := cache.NewRedisCache(cfg.Cache.RedisURL)
		if err != nil {
			logger.Warn().Err(err).Msg("Failed to connect to Redis, using memory cache only")
		} else {
			redisCache = redis
			logger.Info().Msg("Redis cache initialized")
		}
	}

	return cache.NewCacheGroup(memoryCache, redisCache), nil
}

// initWebSocketPools initializes WebSocket connection pools
func initWebSocketPools(cfg *config.Config, router *upstream.Router, logger *logging.Logger) (map[string]*ws.Pool, error) {
	pools := make(map[string]*ws.Pool)
	
	// Get all upstream URLs
	allURLs := router.GetAllURLs()
	
	// WebSocket pool configuration
	minSize := cfg.Upstream.WebSocketPool.MinSize
	maxSize := cfg.Upstream.WebSocketPool.MaxSize
	
	// Default values if not configured
	if minSize <= 0 {
		minSize = 8
	}
	if maxSize <= 0 {
		maxSize = 8
	}
	if minSize > maxSize {
		maxSize = minSize
	}
	
	// Create pools for WebSocket URLs
	for _, urlStr := range allURLs {
		if strings.HasPrefix(urlStr, "ws://") || strings.HasPrefix(urlStr, "wss://") {
			logger.Info().
				Str("url", urlStr).
				Int("min_size", minSize).
				Int("max_size", maxSize).
				Msg("Initializing WebSocket pool")
			
			pool, err := ws.NewPool(urlStr, minSize, maxSize)
			if err != nil {
				logger.Warn().
					Err(err).
					Str("url", urlStr).
					Msg("Failed to initialize WebSocket pool, will create on demand")
				// Don't fail startup, pools will be created on demand
				continue
			}
			
			pools[urlStr] = pool
			logger.Info().
				Str("url", urlStr).
				Msg("WebSocket pool initialized")
		}
	}
	
	return pools, nil
}

// SetupRouter configures the Gin router
func (a *App) SetupRouter() *gin.Engine {
	if a.config.Logging.Level == "DEBUG" {
		gin.SetMode(gin.DebugMode)
	} else {
		gin.SetMode(gin.ReleaseMode)
	}

	router := gin.New()
	router.Use(gin.Recovery())

	// OpenTelemetry middleware
	router.Use(otelgin.Middleware(a.config.Telemetry.ServiceName))

	// Request ID middleware
	router.Use(middleware.RequestIDMiddleware())

	// Tracing middleware
	router.Use(middleware.TracingMiddleware())

	// Error middleware
	router.Use(middleware.ErrorMiddleware())

	// Initialize block number tracker
	middleware.InitBlockNumberTracker()

	// Response capture middleware (must be before cache lookup)
	router.Use(middleware.ResponseCaptureMiddleware())

	// Update block number middleware (must be after response capture)
	router.Use(middleware.UpdateBlockNumberMiddleware())

	// Cache lookup middleware
	router.Use(middleware.CacheLookupMiddleware(a.cacheGroup))

	// Cache store middleware (must be after handlers)
	router.Use(middleware.CacheStoreMiddleware(a.cacheGroup))

	// Limits middleware
	limitsConfig := &middleware.LimitsConfig{
		BatchSizeLimit:      a.config.Server.BatchSizeLimit,
		AccountHistoryLimit: a.config.Limits.AccountHistoryLimit,
		BlacklistAccounts:   a.config.Limits.BlacklistAccounts,
	}
	router.Use(middleware.LimitsMiddleware(limitsConfig))

	// Setup handlers with dependencies
	jsonrpcHandler := &handlers.JSONRPCHandler{
		CacheGroup: a.cacheGroup,
		Router:     a.router,
		HTTPClient: a.httpClient,
		WSPools:    a.wsPools,
		Logger:     a.logger,
	}
	healthHandler := &handlers.HealthHandler{}
	metricsHandler := &handlers.MetricsHandler{}

	// Register routes
	router.POST("/", jsonrpcHandler.HandleJSONRPC)
	router.GET("/health", healthHandler.HandleHealth)
	
	if a.config.Prometheus.Enabled {
		router.GET(a.config.Prometheus.Path, metricsHandler.HandleMetrics)
	}

	return router
}

// Run starts the application
func (a *App) Run() error {
	router := a.SetupRouter()

	server := &http.Server{
		Addr:         fmt.Sprintf("%s:%d", a.config.Server.Host, a.config.Server.Port),
		Handler:      router,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	// Start server in goroutine
	go func() {
		a.logger.Info().
			Str("host", a.config.Server.Host).
			Int("port", a.config.Server.Port).
			Msg("Server starting")
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			a.logger.Fatal().Err(err).Msg("Server failed to start")
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	a.logger.Info().Msg("Shutting down server")

	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		a.logger.Error().Err(err).Msg("Server forced to shutdown")
	}

	// Close resources
	if a.shutdown != nil {
		a.shutdown()
	}
	if a.cacheGroup != nil {
		_ = a.cacheGroup.Close()
	}
	if a.httpClient != nil {
		_ = a.httpClient.Close()
	}
	
	// Close WebSocket pools
	for url, pool := range a.wsPools {
		if err := pool.Close(); err != nil {
			a.logger.Warn().Err(err).Str("url", url).Msg("Error closing WebSocket pool")
		} else {
			a.logger.Info().Str("url", url).Msg("WebSocket pool closed")
		}
	}

	a.logger.Info().Msg("Server exited")
	return nil
}

