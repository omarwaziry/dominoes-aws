#!/usr/bin/env python3
"""
Test validation script to ensure all test modules can be imported and basic functionality works
"""

import sys
import os
import unittest
import importlib

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def validate_test_module(module_path, module_name):
    """Validate that a test module can be imported and has test cases"""
    print(f"Validating {module_name}...")
    
    try:
        # Import the module
        module = importlib.import_module(module_path)
        
        # Find test classes
        test_classes = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and 
                issubclass(attr, unittest.TestCase) and 
                attr != unittest.TestCase):
                test_classes.append(attr)
        
        if not test_classes:
            print(f"  ❌ No test classes found in {module_name}")
            return False
        
        print(f"  ✅ Found {len(test_classes)} test class(es)")
        
        # Count test methods
        total_tests = 0
        for test_class in test_classes:
            test_methods = [method for method in dir(test_class) 
                          if method.startswith('test_')]
            total_tests += len(test_methods)
            print(f"    - {test_class.__name__}: {len(test_methods)} test methods")
        
        print(f"  Total test methods: {total_tests}")
        return True
        
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Validation error: {e}")
        return False

def validate_test_structure():
    """Validate the overall test directory structure"""
    print("Validating test directory structure...")
    
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Expected directories and files
    expected_structure = {
        'integration': ['test_load_balancer.py'],
        'load_testing': ['test_auto_scaling.py'],
        'infrastructure': ['test_cloudformation_validation.py'],
        'security': ['test_security_configuration.py']
    }
    
    issues = []
    
    for subdir, files in expected_structure.items():
        subdir_path = os.path.join(test_dir, subdir)
        
        if not os.path.exists(subdir_path):
            issues.append(f"Missing directory: {subdir}")
            continue
        
        # Check for __init__.py
        init_file = os.path.join(subdir_path, '__init__.py')
        if not os.path.exists(init_file):
            issues.append(f"Missing __init__.py in {subdir}")
        
        # Check for expected test files
        for file in files:
            file_path = os.path.join(subdir_path, file)
            if not os.path.exists(file_path):
                issues.append(f"Missing test file: {subdir}/{file}")
    
    if issues:
        print("  ❌ Structure issues found:")
        for issue in issues:
            print(f"    - {issue}")
        return False
    else:
        print("  ✅ Test directory structure is valid")
        return True

def run_syntax_check():
    """Run basic syntax check on all test files"""
    print("\nRunning syntax checks...")
    
    test_modules = [
        ('tests.integration.test_load_balancer', 'Integration Tests'),
        ('tests.load_testing.test_auto_scaling', 'Load Testing'),
        ('tests.infrastructure.test_cloudformation_validation', 'Infrastructure Tests'),
        ('tests.security.test_security_configuration', 'Security Tests')
    ]
    
    all_valid = True
    
    for module_path, module_name in test_modules:
        if not validate_test_module(module_path, module_name):
            all_valid = False
    
    return all_valid

def run_basic_test_discovery():
    """Run basic test discovery to ensure tests can be loaded"""
    print("\nRunning test discovery...")
    
    try:
        # Create test loader
        loader = unittest.TestLoader()
        
        # Discover tests in each directory
        test_dirs = ['integration', 'load_testing', 'infrastructure', 'security']
        
        total_tests = 0
        
        for test_dir in test_dirs:
            test_dir_path = os.path.join(os.path.dirname(__file__), test_dir)
            
            if os.path.exists(test_dir_path):
                suite = loader.discover(test_dir_path, pattern='test_*.py')
                test_count = suite.countTestCases()
                total_tests += test_count
                print(f"  {test_dir}: {test_count} tests discovered")
        
        print(f"  Total tests discovered: {total_tests}")
        
        if total_tests == 0:
            print("  ❌ No tests discovered")
            return False
        else:
            print("  ✅ Test discovery successful")
            return True
            
    except Exception as e:
        print(f"  ❌ Test discovery failed: {e}")
        return False

def check_dependencies():
    """Check that required dependencies are available"""
    print("\nChecking dependencies...")
    
    required_packages = [
        'boto3',
        'botocore',
        'requests',
        'yaml',
        'concurrent.futures'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"  ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"  ❌ {package} (missing)")
    
    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        print("Install with: pip install " + ' '.join(missing_packages))
        return False
    else:
        print("  ✅ All dependencies available")
        return True

def main():
    """Main validation function"""
    print("Test Suite Validation")
    print("=" * 50)
    
    all_checks_passed = True
    
    # Check dependencies
    if not check_dependencies():
        all_checks_passed = False
    
    # Validate test structure
    if not validate_test_structure():
        all_checks_passed = False
    
    # Run syntax checks
    if not run_syntax_check():
        all_checks_passed = False
    
    # Run test discovery
    if not run_basic_test_discovery():
        all_checks_passed = False
    
    print("\n" + "=" * 50)
    
    if all_checks_passed:
        print("✅ All validation checks passed!")
        print("\nYou can now run the comprehensive tests:")
        print("  python tests/run_comprehensive_tests.py")
        print("\nOr set up the test environment first:")
        print("  python tests/setup_test_environment.py")
        sys.exit(0)
    else:
        print("❌ Some validation checks failed!")
        print("Please fix the issues above before running tests.")
        sys.exit(1)

if __name__ == '__main__':
    main()