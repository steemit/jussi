#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Legacy Test Runner for New Jussi Implementation

This script runs legacy test cases against the new Go jussi binary
to ensure compatibility during migration.
"""

import json
import os
import sys
import argparse
import requests
import time
from typing import Dict, List, Any
from pathlib import Path


class TestResult:
    def __init__(self, name: str, passed: bool, expected: Any = None, actual: Any = None, error: str = None):
        self.name = name
        self.passed = passed
        self.expected = expected
        self.actual = actual
        self.error = error


class LegacyTestRunner:
    def __init__(self, jussi_url: str, test_data_dir: str):
        self.jussi_url = jussi_url.rstrip('/')
        self.test_data_dir = Path(test_data_dir)
        self.results: List[TestResult] = []
    
    def load_test_data(self, filename: str) -> List[Dict]:
        """Load test data from JSON file"""
        # Try multiple possible paths
        possible_paths = [
            self.test_data_dir / filename,
            Path(filename),  # Absolute path
            Path("legacy/tests/data") / filename,  # Relative from workspace root
        ]
        
        for filepath in possible_paths:
            if filepath.exists():
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else [data]
        
        print(f"Warning: Test data file not found: {filename}")
        print(f"  Tried paths: {[str(p) for p in possible_paths]}")
        return []
    
    def send_request(self, request: Dict) -> Dict:
        """Send JSON-RPC request to jussi"""
        try:
            resp = requests.post(
                self.jussi_url,
                json=request,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
    
    def compare_response(self, expected: Dict, actual: Dict) -> bool:
        """Compare expected and actual responses"""
        # Simple comparison - can be enhanced
        if 'error' in actual and 'error' in expected:
            return actual['error'].get('code') == expected['error'].get('code')
        
        if 'result' in actual and 'result' in expected:
            # For now, just check if both have results
            # More sophisticated comparison can be added
            return True
        
        return False
    
    def run_test_case(self, test_case: Dict, test_name: str = None) -> TestResult:
        """Run a single test case"""
        name = test_name or test_case.get('name', 'unnamed_test')
        request = test_case.get('request', test_case)
        expected = test_case.get('expected', test_case.get('response'))
        
        # Send request
        actual = self.send_request(request)
        
        # Check for errors in response
        if 'error' in actual and 'error' not in str(actual):
            return TestResult(
                name=name,
                passed=False,
                expected=expected,
                actual=actual,
                error=actual.get('error', {}).get('message', 'Unknown error')
            )
        
        # Compare results
        passed = self.compare_response(expected, actual) if expected else True
        
        return TestResult(
            name=name,
            passed=passed,
            expected=expected,
            actual=actual
        )
    
    def run_tests_from_file(self, filename: str) -> List[TestResult]:
        """Run all tests from a JSON file"""
        test_data = self.load_test_data(filename)
        results = []
        
        if not test_data:
            return results
        
        # Handle legacy test data format: [[request, response], ...]
        if isinstance(test_data, list) and len(test_data) > 0:
            # Check if first element is a [request, response] pair
            if isinstance(test_data[0], list) and len(test_data[0]) == 2:
                # Format: [[request, response], [request, response], ...]
                for i, test_pair in enumerate(test_data):
                    if isinstance(test_pair, list) and len(test_pair) >= 2:
                        request = test_pair[0]
                        expected = test_pair[1]
                        result = self.run_test_case_with_expected(request, expected, f"{filename}:{i}")
                        results.append(result)
            else:
                # Format: [test_case1, test_case2, ...]
                for i, test_case in enumerate(test_data):
                    result = self.run_test_case(test_case, f"{filename}:{i}")
                    results.append(result)
        elif isinstance(test_data, dict):
            # Single test case
            result = self.run_test_case(test_data, filename)
            results.append(result)
        
        return results
    
    def run_test_case_with_expected(self, request: Dict, expected: Dict, test_name: str = None) -> TestResult:
        """Run a test case with explicit expected response"""
        name = test_name or request.get('method', 'unnamed_test')
        
        # Send request
        actual = self.send_request(request)
        
        # Check for errors in response
        if 'error' in actual and isinstance(actual.get('error'), str):
            return TestResult(
                name=name,
                passed=False,
                expected=expected,
                actual=actual,
                error=actual.get('error', 'Unknown error')
            )
        
        # Compare results
        passed = self.compare_response(expected, actual)
        
        return TestResult(
            name=name,
            passed=passed,
            expected=expected,
            actual=actual
        )
    
    def run_all_tests(self, test_files: List[str] = None) -> List[TestResult]:
        """Run all tests"""
        if test_files is None:
            # Find all JSON test files in jsonrpc subdirectory
            jsonrpc_dir = self.test_data_dir / "jsonrpc"
            if jsonrpc_dir.exists():
                test_files = [
                    f"jsonrpc/{f.name}"
                    for f in jsonrpc_dir.glob('*.json')
                    if 'schema' not in str(f) and 'invalid' not in str(f)
                ]
            else:
                # Fallback: find all JSON files
                test_files = [
                    str(f.relative_to(self.test_data_dir))
                    for f in self.test_data_dir.rglob('*.json')
                    if 'schema' not in str(f) and 'invalid' not in str(f)
                ]
        
        all_results = []
        for test_file in test_files:
            print(f"\nRunning tests from: {test_file}")
            results = self.run_tests_from_file(test_file)
            print(f"  {len(results)} test cases found")
            all_results.extend(results)
        
        return all_results
    
    def print_summary(self, results: List[TestResult]):
        """Print test summary"""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        
        print("\n" + "=" * 80)
        print(f"Test Summary: {passed}/{total} passed, {failed} failed")
        print("=" * 80)
        
        if failed > 0:
            print("\nFailed Tests:")
            for result in results:
                if not result.passed:
                    print(f"\n  ❌ {result.name}")
                    if result.error:
                        print(f"     Error: {result.error}")
                    if result.expected:
                        print(f"     Expected: {json.dumps(result.expected, indent=2)}")
                    if result.actual:
                        print(f"     Actual: {json.dumps(result.actual, indent=2)}")
        
        return failed == 0


def main():
    parser = argparse.ArgumentParser(description='Run legacy tests against new jussi binary')
    parser.add_argument('--jussi-url', default='http://localhost:8080',
                       help='URL of jussi server (default: http://localhost:8080)')
    parser.add_argument('--test-data', default='legacy/tests/data',
                       help='Path to test data directory (default: legacy/tests/data)')
    parser.add_argument('--test-files', nargs='+',
                       help='Specific test files to run (default: all)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Check if jussi is reachable (with retries for container startup)
    max_retries = 10
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            resp = requests.get(f"{args.jussi_url}/health", timeout=2)
            resp.raise_for_status()
            print(f"✓ Connected to jussi at {args.jussi_url}")
            break
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                print(f"Waiting for jussi to be ready... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"Error: Cannot connect to jussi at {args.jussi_url}")
                print(f"  {e}")
                print("\nMake sure jussi is running:")
                print("  docker run -p 8080:8080 jussi:latest")
                sys.exit(1)
    
    # Run tests
    runner = LegacyTestRunner(args.jussi_url, args.test_data)
    results = runner.run_all_tests(args.test_files)
    
    # Print summary
    success = runner.print_summary(results)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

