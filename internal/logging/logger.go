package logging

import (
	"io"
	"os"
	"time"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

// Logger wraps zerolog logger with Scalyr-optimized configuration
type Logger struct {
	logger zerolog.Logger
}

// NewLogger creates a new logger with Scalyr-optimized settings
func NewLogger(level, format, output string, includeCaller bool) *Logger {
	// Set log level
	logLevel, err := zerolog.ParseLevel(level)
	if err != nil {
		logLevel = zerolog.InfoLevel
	}
	zerolog.SetGlobalLevel(logLevel)

	// Configure timestamp format (RFC3339 for Scalyr)
	zerolog.TimeFieldFormat = time.RFC3339

	var writer io.Writer
	switch output {
	case "stderr":
		if format == "json" {
			writer = os.Stderr
		} else {
			writer = zerolog.ConsoleWriter{Out: os.Stderr, TimeFormat: time.RFC3339}
		}
	case "both":
		multi := zerolog.MultiLevelWriter(os.Stdout, os.Stderr)
		if format == "json" {
			writer = multi
		} else {
			writer = zerolog.ConsoleWriter{Out: multi, TimeFormat: time.RFC3339}
		}
	default: // stdout
		if format == "json" {
			writer = os.Stdout
		} else {
			writer = zerolog.ConsoleWriter{Out: os.Stdout, TimeFormat: time.RFC3339}
		}
	}

	logger := zerolog.New(writer).
		With().
		Timestamp().
		Str("service", "jussi").
		Logger()

	if includeCaller {
		logger = logger.With().Caller().Logger()
	}

	// Set global logger
	log.Logger = logger

	return &Logger{
		logger: logger,
	}
}

// GetLogger returns the underlying zerolog logger
func (l *Logger) GetLogger() zerolog.Logger {
	return l.logger
}

// WithContext adds context fields to the logger
func (l *Logger) WithContext(fields map[string]interface{}) *zerolog.Event {
	event := l.logger.Info()
	for k, v := range fields {
		event = event.Interface(k, v)
	}
	return event
}

// Info logs an info message
func (l *Logger) Info() *zerolog.Event {
	return l.logger.Info()
}

// Error logs an error message
func (l *Logger) Error() *zerolog.Event {
	return l.logger.Error()
}

// Warn logs a warning message
func (l *Logger) Warn() *zerolog.Event {
	return l.logger.Warn()
}

// Debug logs a debug message
func (l *Logger) Debug() *zerolog.Event {
	return l.logger.Debug()
}

// Fatal logs a fatal message and exits
func (l *Logger) Fatal() *zerolog.Event {
	return l.logger.Fatal()
}

