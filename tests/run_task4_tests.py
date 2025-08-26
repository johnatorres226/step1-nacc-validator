"""
Test runner for Task 4: Testing and Validation.

This script runs all the comprehensive tests for the refactored pipeline components
and generates a test report.
"""
import subprocess
import sys
import os
from pathlib import Path
import importlib.util


def run_test_file(test_file_path: str) -> tuple[bool, str]:
    """
    Run a single test file and return success status and output.
    
    Args:
        test_file_path: Path to the test file to run
        
    Returns:
        Tuple of (success, output)
    """
    try:
        # Run pytest on the specific file
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            test_file_path, 
            '-v', 
            '--tb=short'
        ], capture_output=True, text=True)
        
        success = result.returncode == 0
        output = result.stdout + result.stderr
        
        return success, output
        
    except Exception as e:
        return False, f"Error running test: {str(e)}"


def check_imports(test_file_path: str) -> tuple[bool, str]:
    """
    Check if a test file can import its dependencies.
    
    Args:
        test_file_path: Path to the test file
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        spec = importlib.util.spec_from_file_location("test_module", test_file_path)
        if spec is None:
            return False, f"Could not load spec for {test_file_path}"
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        return True, "Imports successful"
        
    except ImportError as e:
        return False, f"Import error: {str(e)}"
    except Exception as e:
        return False, f"Error checking imports: {str(e)}"


def run_all_tests():
    """Run all tests and generate comprehensive report."""
    
    print("="*80)
    print("TASK 4: TESTING AND VALIDATION - TEST RUNNER")
    print("="*80)
    print()
    
    # Define test files to run
    test_files = [
        "tests/unit/test_pipeline_results_simple.py",
        "tests/unit/test_data_processing_simple.py",
        "tests/integration/test_pipeline_integration.py",
        "tests/performance/test_performance.py"
    ]
    
    # Track results
    total_tests = len(test_files)
    passed_tests = 0
    failed_tests = 0
    import_errors = 0
    
    results = []
    
    # Check if test files exist and run them
    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"❌ Test file not found: {test_file}")
            failed_tests += 1
            results.append((test_file, False, "File not found"))
            continue
        
        print(f"🔍 Checking imports for: {test_file}")
        import_success, import_message = check_imports(test_file)
        
        if not import_success:
            print(f"❌ Import check failed: {import_message}")
            import_errors += 1
            results.append((test_file, False, f"Import error: {import_message}"))
            continue
        
        print(f"✅ Imports OK: {test_file}")
        print(f"🧪 Running tests in: {test_file}")
        
        # Run the actual tests
        test_success, test_output = run_test_file(test_file)
        
        if test_success:
            print(f"✅ Tests passed: {test_file}")
            passed_tests += 1
            results.append((test_file, True, "All tests passed"))
        else:
            print(f"❌ Tests failed: {test_file}")
            failed_tests += 1
            results.append((test_file, False, f"Test failures: {test_output}"))
        
        print()
    
    # Generate final report
    print("="*80)
    print("TEST EXECUTION SUMMARY")
    print("="*80)
    print(f"Total test files: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    print(f"Import errors: {import_errors}")
    print()
    
    # Detailed results
    print("DETAILED RESULTS:")
    print("-" * 40)
    for test_file, success, message in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_file}")
        if not success:
            print(f"    Error: {message[:100]}...")
    print()
    
    # Overall status
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED! Pipeline refactoring is successful.")
        return 0
    elif passed_tests > 0:
        print(f"⚠️  PARTIAL SUCCESS: {passed_tests}/{total_tests} test files passed.")
        return 1
    else:
        print("💥 ALL TESTS FAILED! Review implementation.")
        return 2


def run_basic_functionality_tests():
    """Run basic functionality tests without pytest."""
    
    print("="*80)
    print("BASIC FUNCTIONALITY TESTS")
    print("="*80)
    print()
    
    try:
        # Test 1: Pipeline results import
        print("🔍 Test 1: Testing pipeline results import...")
        from pipeline.core.pipeline_results import DataFetchResult, RulesLoadingResult
        print("✅ Pipeline results import successful")
        
        # Test 2: Data processing imports  
        print("🔍 Test 2: Testing data processing import...")
        from pipeline.core.data_processing import build_variable_maps, preprocess_cast_types
        print("✅ Data processing import successful")
        
        # Test 3: Pipeline orchestrator import
        print("🔍 Test 3: Testing pipeline orchestrator import...")
        from pipeline.core.pipeline_orchestrator import PipelineOrchestrator
        print("✅ Pipeline orchestrator import successful")
        
        # Test 4: Improved pipeline import
        print("🔍 Test 4: Testing improved pipeline import...")
        from pipeline.report_pipeline import run_improved_report_pipeline
        print("✅ Improved pipeline import successful")
        
        # Test 5: Basic result object creation
        print("🔍 Test 5: Testing result object creation...")
        import pandas as pd
        from datetime import datetime
        
        result = DataFetchResult(
            data=pd.DataFrame({'id': [1, 2]}),
            records_processed=2,
            execution_time=1.0,
            source_info={'server': 'test'},
            fetch_timestamp=datetime.now(),
            success=True
        )
        assert result.success == True
        assert result.records_processed == 2
        print("✅ Result object creation successful")
        
        # Test 6: Basic variable mapping
        print("🔍 Test 6: Testing variable mapping...")
        instruments = ['a1', 'b3']
        rules_cache = {
            'a1': {'field1': {'type': 'text'}},
            'b3': {'field2': {'type': 'number'}}
        }
        
        variable_map, instrument_map = build_variable_maps(instruments, rules_cache)
        assert isinstance(variable_map, dict)
        assert isinstance(instrument_map, dict)
        print("✅ Variable mapping successful")
        
        print()
        print("🎉 ALL BASIC FUNCTIONALITY TESTS PASSED!")
        print("The refactored pipeline components are working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {str(e)}")
        return False


if __name__ == "__main__":
    print("Starting Task 4 test validation...")
    print()
    
    # First run basic functionality tests
    basic_success = run_basic_functionality_tests()
    
    print()
    print("="*80)
    
    if basic_success:
        # If basic tests pass, run the full test suite
        exit_code = run_all_tests()
        sys.exit(exit_code)
    else:
        print("💥 BASIC FUNCTIONALITY TESTS FAILED!")
        print("Please fix import and basic functionality issues before running full tests.")
        sys.exit(3)
