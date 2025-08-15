#!/usr/bin/env python3
"""
Comprehensive test runner for AWS scalable web application
Runs all test suites: integration, load testing, infrastructure, and security
"""

import unittest
import sys
import os
import argparse
import time
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_test_suite(test_module, suite_name, verbose=True):
    """Run a specific test suite and return results"""
    print(f"\n{'='*60}")
    print(f"Running {suite_name} Tests")
    print(f"{'='*60}")
    
    # Create test loader
    loader = unittest.TestLoader()
    
    try:
        # Load the test module
        suite = loader.loadTestsFromModule(test_module)
        
        # Create test runner
        runner = unittest.TextTestRunner(
            verbosity=2 if verbose else 1,
            stream=sys.stdout,
            buffer=True
        )
        
        # Run tests
        start_time = time.time()
        result = runner.run(suite)
        end_time = time.time()
        
        # Print summary
        duration = end_time - start_time
        print(f"\n{suite_name} Tests Summary:")
        print(f"  Tests run: {result.testsRun}")
        print(f"  Failures: {len(result.failures)}")
        print(f"  Errors: {len(result.errors)}")
        print(f"  Skipped: {len(result.skipped)}")
        print(f"  Duration: {duration:.2f} seconds")
        
        return result
        
    except Exception as e:
        print(f"Error running {suite_name} tests: {e}")
        return None

def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description='Run comprehensive test suite')
    parser.add_argument('--suite', choices=['integration', 'load', 'infrastructure', 'security', 'all'],
                       default='all', help='Test suite to run')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--skip-aws', action='store_true', help='Skip tests requiring AWS credentials')
    
    args = parser.parse_args()
    
    # Set environment variables for test configuration
    if args.skip_aws:
        os.environ['SKIP_AWS_TESTS'] = 'true'
    
    print(f"Starting comprehensive test run at {datetime.now()}")
    print(f"Test suite: {args.suite}")
    print(f"Verbose: {args.verbose}")
    print(f"Skip AWS: {args.skip_aws}")
    
    # Import test modules
    test_modules = {}
    results = {}
    
    try:
        if args.suite in ['integration', 'all']:
            from tests.integration import test_load_balancer
            test_modules['Integration'] = test_load_balancer
        
        if args.suite in ['load', 'all']:
            from tests.load_testing import test_auto_scaling
            test_modules['Load Testing'] = test_auto_scaling
        
        if args.suite in ['infrastructure', 'all']:
            from tests.infrastructure import test_cloudformation_validation
            test_modules['Infrastructure'] = test_cloudformation_validation
        
        if args.suite in ['security', 'all']:
            from tests.security import test_security_configuration
            test_modules['Security'] = test_security_configuration
            
    except ImportError as e:
        print(f"Error importing test modules: {e}")
        sys.exit(1)
    
    # Run test suites
    total_start_time = time.time()
    
    for suite_name, test_module in test_modules.items():
        result = run_test_suite(test_module, suite_name, args.verbose)
        results[suite_name] = result
    
    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    
    # Print overall summary
    print(f"\n{'='*60}")
    print("OVERALL TEST SUMMARY")
    print(f"{'='*60}")
    
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0
    
    for suite_name, result in results.items():
        if result:
            total_tests += result.testsRun
            total_failures += len(result.failures)
            total_errors += len(result.errors)
            total_skipped += len(result.skipped)
            
            status = "PASS" if (len(result.failures) == 0 and len(result.errors) == 0) else "FAIL"
            print(f"  {suite_name:15} {status:4} ({result.testsRun} tests)")
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Total Failures: {total_failures}")
    print(f"Total Errors: {total_errors}")
    print(f"Total Skipped: {total_skipped}")
    print(f"Total Duration: {total_duration:.2f} seconds")
    
    # Exit with appropriate code
    if total_failures > 0 or total_errors > 0:
        print("\nSome tests failed!")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)

if __name__ == '__main__':
    main()