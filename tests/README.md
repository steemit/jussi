# Jussi Test Suite

This directory contains tests for the new Go implementation of jussi.

## Directory Structure

```
tests/
├── integration/        # ✅ Go integration tests (complete - replaces legacy_runner)
├── unit/              # Additional unit tests (to be created)
└── data/              # Test data (symlink or copy from legacy/tests/data)
```

## Running Tests

### Unit Tests (Go)

```bash
# Run all unit tests
go test ./...

# Run with coverage
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out

# Run specific test
go test ./internal/urn/... -v
```

### Integration Tests (Legacy Runner)

#### Option 1: Using Docker Compose (Recommended)

```bash
# Start jussi and run tests
cd tests

# Without proxy
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

# With proxy (if needed)
HTTPS_PROXY=http://192.168.199.11:8001 \
HTTP_PROXY=http://192.168.199.11:8001 \
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Note: Port 8080 is not exposed to host to avoid conflicts.
# Test runner accesses jussi via Docker internal network (jussi-test:8080)
```

#### Option 2: Manual Setup

```bash
# 1. Build jussi binary
docker build -t jussi-test ..

# 2. Start jussi server
docker run -d --name jussi-test -p 8080:8080 jussi-test

# 3. Wait for server to be ready
sleep 5

# 4. Run integration tests
cd tests
go test ./integration/... -v

# 5. Cleanup
docker stop jussi-test
docker rm jussi-test
```

#### Option 3: Run Specific Test Files

```bash
go test ./tests/integration/... -v -run "TestAppbaseJSONRPC|TestSteemdJSONRPC"
```

## Test Migration Status

### Completed Migrations

- [x] URN parsing tests (`internal/urn/urn_test.go`)
  - Migrated from `legacy/tests/test_urn.py`
  - Tests URN parsing, string representation, and equality

- [x] Router/upstream tests (`internal/upstream/router_test.go`)
  - Migrated from `legacy/tests/test_upstreams.py`
  - Tests upstream configuration, URL routing, TTL/timeout lookup, namespace handling
  - Tests translate_to_appbase configuration

- [x] Cache key tests (`internal/cache/key_test.go`)
  - Migrated from `legacy/tests/test_cache_key.py`
  - Tests cache key generation from URN and JSON-RPC requests
  - Verifies cache key matches URN string representation

- [x] Validators tests (`internal/validators/validators_test.go`)
  - Extended with comprehensive test cases
  - Tests JSON-RPC request/response validation
  - Tests batch request validation
  - Tests ID and params type validation

- [x] TTL tests (`internal/cache/ttl_test.go`)
  - Tests TTL calculation and cacheability
  - Tests irreversible TTL calculation
  - Tests block number extraction from JSON-RPC responses

- [x] Trie tests (`internal/upstream/trie_test.go`)
  - Tests prefix trie for URL/TTL/timeout lookup

- [x] Cache group tests (`internal/cache/group_test.go`)
  - Migrated from `legacy/tests/test_cache_group.py`
  - Tests cache group get/set/clear operations
  - Tests cache priority (memory first, then Redis)
  - Tests MGet and SetMany operations

- [x] Extended validators tests (`internal/validators/validators_test.go`)
  - Added get block request detection tests
  - Added get block header request detection tests
  - Added broadcast transaction request detection tests
  - Added block number extraction from block ID tests
  - Added get block response validation tests
  - Added custom JSON operation length limit tests
  - Added custom JSON account blacklist tests
  - Added broadcast transaction limit tests

### Completed Migrations (Continued)

- [x] Integration/E2E tests (`tests/integration/`)
  - HTTP request/response tests (`server_test.go`)
  - Mock upstream server tests (`mock_upstream_test.go`)
  - JSON-RPC test case loader (`jsonrpc_test.go`)
  - Single and batch request handling
  - Request validation and error handling
  - Cache hit/miss behavior
  - Request ID middleware
  - Test case loading from `appbase.json` and `steemd.json` (all cases loaded)
  - Routes and health check tests (`routes_test.go`)
  - Cache middleware tests (`cache_middleware_test.go`)
  - All 77 appbase.json test cases passing ✅
  - All 84 steemd.json test cases passing ✅

### Pending Migrations

- [ ] Final verification and cleanup
  - All 77 appbase.json test cases are now passing ✅
  - All 84 steemd.json test cases are now passing ✅
  - ✅ `legacy_runner/` directory has been removed

- [x] Cache middleware tests (`tests/integration/cache_middleware_test.go`)
  - Cache hit/miss behavior in HTTP handlers
  - Cache behavior with batch requests
  - No-cache TTL (TTL=-1) behavior
  - Cache response verification

- [ ] Error handling tests
  - Upstream error propagation
  - JSON-RPC error formatting
  - Timeout handling

## Adding New Tests

### Unit Tests

Create `*_test.go` files alongside the code:

```go
// internal/urn/urn_test.go
package urn

import "testing"

func TestNewFeature(t *testing.T) {
    // Test implementation
}
```

### Integration Tests

Create integration tests in `tests/integration/`:

```go
// tests/integration/request_test.go
package integration

import (
    "testing"
    "net/http"
)

func TestJSONRPCRequest(t *testing.T) {
    // HTTP integration test
}
```

## Legacy Test Runner

> **✅ Migration Complete**: All tests have been successfully migrated to Go. The legacy test runner is **DEPRECATED** and ready for removal.

**Status**: 
- ✅ All unit tests migrated to Go
- ✅ All integration tests migrated to Go  
- ✅ All JSON-RPC test cases migrated (appbase.json: 77 cases ✅, steemd.json: 84 cases ✅)

The legacy test runner has been **REMOVED**. All tests are now in Go. See `MIGRATION_SUMMARY.md` for complete migration details.

### Migration Status

✅ **All tests have been migrated to Go integration tests.**

The legacy runner has been removed. Use Go tests instead:

```bash
# Run all integration tests
go test ./tests/integration/... -v

# Run specific test suites
go test ./tests/integration/... -run TestAppbaseJSONRPC
go test ./tests/integration/... -run TestSteemdJSONRPC
```

## CI/CD Integration

Tests can be integrated into CI/CD pipelines:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run unit tests
        run: go test ./...
      - name: Run integration tests
        run: |
          cd tests
          docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

