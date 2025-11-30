# Legacy Test Migration Guide

This document outlines strategies for migrating legacy Python tests to the new Go implementation.

## Migration Strategies

### Strategy 1: Direct Go Unit Tests (Recommended for Unit Tests)

**Best for**: URN parsing, router logic, cache logic, validation logic

**Approach**: Convert Python pytest tests directly to Go `*_test.go` files.

**Example Migration**:
- `legacy/tests/test_urn.py` → `internal/urn/urn_test.go` ✅ (Already done)
- `legacy/tests/test_upstreams.py` → `internal/upstream/router_test.go`
- `legacy/tests/test_validators.py` → `internal/validators/validators_test.go`

**Pros**:
- Fast execution
- Type safety
- Integrated with Go toolchain
- Easy CI/CD integration

**Cons**:
- Requires manual conversion
- Need to understand both codebases

### Strategy 2: Integration Tests via HTTP (Recommended for E2E Tests)

**Best for**: End-to-end request/response tests, middleware tests, full request flow

**Approach**: 
1. Build jussi binary in Docker
2. Start jussi server in test container
3. Use HTTP client to send requests and validate responses
4. Can reuse legacy test data (JSON files)

**Implementation**:

```go
// tests/integration/integration_test.go
package integration

import (
    "encoding/json"
    "net/http"
    "testing"
    "github.com/stretchr/testify/assert"
)

func TestCondenserAPIGetAccounts(t *testing.T) {
    // Load test data from legacy
    testData := loadLegacyTestData("legacy/tests/data/jsonrpc/appbase.json")
    
    for _, testCase := range testData {
        t.Run(testCase.Name, func(t *testing.T) {
            // Send HTTP request to jussi
            resp := sendJSONRPCRequest(t, "http://localhost:8080", testCase.Request)
            
            // Validate response
            assert.Equal(t, testCase.Expected.StatusCode, resp.StatusCode)
            // ... more assertions
        })
    }
}
```

**Pros**:
- Tests real HTTP behavior
- Can reuse legacy test data files
- Tests complete request flow
- Easy to parallelize

**Cons**:
- Slower than unit tests
- Requires running server
- More complex setup

### Strategy 3: Test Runner Script (Hybrid Approach)

**Best for**: Quick validation, regression testing, gradual migration

**Approach**:
1. Build jussi binary in Docker
2. Create Python/Shell script that:
   - Reads legacy test cases
   - Calls jussi binary via HTTP
   - Compares results with expected outputs
   - Reports differences

**Implementation**:

```python
# tests/legacy_runner.py
import json
import requests
import sys

def run_legacy_test(test_file):
    """Run legacy test cases against new jussi binary"""
    with open(test_file) as f:
        test_cases = json.load(f)
    
    jussi_url = "http://localhost:8080"
    results = []
    
    for test_case in test_cases:
        request = test_case['request']
        expected = test_case['expected']
        
        resp = requests.post(jussi_url, json=request)
        actual = resp.json()
        
        if actual != expected:
            results.append({
                'test': test_case['name'],
                'status': 'FAIL',
                'expected': expected,
                'actual': actual
            })
        else:
            results.append({
                'test': test_case['name'],
                'status': 'PASS'
            })
    
    return results

if __name__ == '__main__':
    results = run_legacy_test(sys.argv[1])
    # Print results, exit with error if any failed
```

**Pros**:
- Quick to implement
- Can run all legacy tests immediately
- Good for regression testing
- Minimal code changes needed

**Cons**:
- Less integrated with Go toolchain
- Requires Python runtime
- Slower feedback loop

## Recommended Migration Plan

### Phase 1: Setup Test Infrastructure

1. **Create test directory structure**:
   ```
   tests/
   ├── unit/           # Go unit tests (converted from legacy)
   ├── integration/    # HTTP integration tests
   ├── legacy_runner/  # Scripts to run legacy tests
   └── data/           # Test data (copied from legacy/tests/data)
   ```

2. **Create Docker test environment**:
   ```dockerfile
   # tests/Dockerfile.test
   FROM golang:1.23-alpine AS builder
   WORKDIR /app
   COPY . .
   RUN go build -o jussi-test ./cmd/jussi
   
   FROM alpine:latest
   RUN apk add --no-cache curl wget
   COPY --from=builder /app/jussi-test /usr/local/bin/jussi
   COPY DEV_config.json /app/
   EXPOSE 8080
   CMD ["jussi"]
   ```

3. **Create test helper utilities**:
   ```go
   // tests/helpers/http.go
   package helpers
   
   func SendJSONRPCRequest(url string, req map[string]interface{}) (map[string]interface{}, error) {
       // HTTP client implementation
   }
   
   func LoadTestData(path string) ([]TestCase, error) {
       // Load JSON test data
   }
   ```

### Phase 2: Migrate Critical Tests First

**Priority order**:
1. ✅ URN parsing tests (already done)
2. Router/upstream tests
3. Validation tests
4. Cache tests
5. Integration/E2E tests

### Phase 3: Create Legacy Test Runner

Create a script that can run legacy tests against the new binary:

```bash
#!/bin/bash
# tests/run_legacy_tests.sh

# Build jussi binary
docker build -f tests/Dockerfile.test -t jussi-test .

# Start jussi in background
docker run -d --name jussi-test -p 8080:8080 jussi-test

# Wait for server to be ready
sleep 5

# Run legacy test runner
python3 tests/legacy_runner/run_tests.py \
    --jussi-url http://localhost:8080 \
    --test-data legacy/tests/data

# Cleanup
docker stop jussi-test
docker rm jussi-test
```

### Phase 4: Gradual Migration

1. Convert high-priority tests to Go unit tests
2. Keep legacy runner for regression testing
3. Add new tests in Go format
4. Eventually deprecate legacy runner

## Example: Converting a Legacy Test

### Legacy Test (Python)
```python
def test_parse_jrpc_namespaces(full_urn_test_request_dict):
    jsonrpc_request, urn_parsed, urn, url, ttl, timeout = full_urn_test_request_dict
    result = _parse_jrpc(jsonrpc_request)
    assert result['namespace'] == urn_parsed['namespace']
    assert result['api'] == urn_parsed['api']
    assert result['method'] == urn_parsed['method']
```

### Go Test (Converted)
```go
func TestParseJRPCNamespaces(t *testing.T) {
    testCases := []struct {
        name     string
        request  map[string]interface{}
        expected URN
    }{
        {
            name: "appbase method",
            request: map[string]interface{}{
                "method": "condenser_api.get_accounts",
                "params": [][]string{{"steemit"}},
            },
            expected: URN{
                Namespace: "appbase",
                API:       "condenser_api",
                Method:    "get_accounts",
            },
        },
        // ... more test cases
    }
    
    for _, tc := range testCases {
        t.Run(tc.name, func(t *testing.T) {
            result, err := FromRequest(tc.request)
            if err != nil {
                t.Fatalf("unexpected error: %v", err)
            }
            
            if result.Namespace != tc.expected.Namespace {
                t.Errorf("expected namespace %s, got %s", 
                    tc.expected.Namespace, result.Namespace)
            }
            // ... more assertions
        })
    }
}
```

## Test Data Migration

Legacy tests use JSON files for test data. These can be reused:

1. **Copy test data**:
   ```bash
   cp -r legacy/tests/data tests/data
   ```

2. **Load in Go tests**:
   ```go
   func loadTestData(t *testing.T, filename string) []TestCase {
       data, err := os.ReadFile(filepath.Join("tests/data", filename))
       require.NoError(t, err)
       
       var testCases []TestCase
       err = json.Unmarshal(data, &testCases)
       require.NoError(t, err)
       
       return testCases
   }
   ```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-go@v2
        with:
          go-version: '1.23'
      - run: go test ./...
  
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build and run tests
        run: |
          docker-compose -f tests/docker-compose.test.yml up --build --abort-on-container-exit
```

## Tools and Utilities

### Test Data Converter

Create a tool to convert legacy test fixtures to Go test cases:

```go
// tools/convert_tests/main.go
package main

// Reads legacy test JSON files
// Generates Go test code
// Outputs to internal/*/*_test.go
```

### Test Coverage Comparison

Compare test coverage between legacy and new implementation:

```bash
# Legacy coverage
pytest --cov=jussi legacy/tests/

# New coverage
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

## Next Steps

1. **Immediate**: Set up test infrastructure (Phase 1)
2. **Short-term**: Create legacy test runner (Phase 3)
3. **Medium-term**: Migrate critical unit tests (Phase 2)
4. **Long-term**: Complete migration and deprecate legacy runner

## References

- Legacy test files: `legacy/tests/`
- Legacy test data: `legacy/tests/data/`
- Existing Go tests: `internal/*/*_test.go`

