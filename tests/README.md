# Jussi Test Suite

This directory contains tests for the new Go implementation of jussi.

## Directory Structure

```
tests/
├── legacy_runner/      # Scripts to run legacy tests against new binary
├── integration/        # Go integration tests (to be created)
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

- [x] URN parsing tests (`internal/urn/urn_test.go`)
- [ ] Router/upstream tests
- [ ] Validation tests
- [ ] Cache tests
- [ ] Integration/E2E tests

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

The legacy test runner (`legacy_runner/run_tests.py`) allows running legacy Python test cases against the new Go binary without converting them.

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

