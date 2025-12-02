# Jussi Test Suite

This directory contains tests for the new Go implementation of jussi.

## Directory Structure

```
tests/
├── legacy_runner/      # ⚠️ Deprecated: E2E test runner (to be removed after integration tests migration)
├── integration/        # Go integration tests (to be created - will replace legacy_runner)
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

# 4. Run legacy test runner
cd tests
python3 legacy_runner/run_tests.py \
    --jussi-url http://localhost:8080 \
    --test-data ../legacy/tests/data

# 5. Cleanup
docker stop jussi-test
docker rm jussi-test
```

#### Option 3: Run Specific Test Files

```bash
python3 legacy_runner/run_tests.py \
    --jussi-url http://localhost:8080 \
    --test-data ../legacy/tests/data \
    --test-files jsonrpc/appbase.json jsonrpc/steemd.json
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

- [x] Trie tests (`internal/upstream/trie_test.go`)
  - Tests prefix trie for URL/TTL/timeout lookup

### Pending Migrations

- [ ] Integration/E2E tests (⚠️ **Critical - legacy_runner depends on this**)
  - HTTP request/response tests
  - Middleware tests
  - Full request flow tests
  - Migration of `legacy/tests/data/jsonrpc/appbase.json` and `steemd.json` test cases
  - Once complete, `legacy_runner/` can be removed

- [ ] Additional validator tests
  - Get block request detection
  - Broadcast transaction validation
  - Custom JSON operation validation

- [ ] Cache middleware tests
  - Cache hit/miss behavior
  - Cache expiration logic
  - Cache group operations

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

> **⚠️ Deprecated**: The legacy test runner is kept for now to provide E2E integration testing until Go integration tests are fully migrated. It will be removed once `tests/integration/` tests are complete.

The legacy test runner (`legacy_runner/run_tests.py`) allows running legacy Python test cases against the new Go binary without converting them. It provides end-to-end HTTP request/response testing using real JSON-RPC test data.

### Usage

```bash
python3 legacy_runner/run_tests.py \
    --jussi-url http://localhost:8080 \
    --test-data ../legacy/tests/data \
    [--test-files file1.json file2.json] \
    [--verbose]
```

### Output

The runner prints:
- Test execution progress
- Summary with pass/fail counts
- Detailed failure information for failed tests

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

