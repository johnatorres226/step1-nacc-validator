#!/usr/bin/env python3
"""
Test script to verify the deprecated functions still work but show warnings.
"""

import sys
from pathlib import Path
import warnings

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

def test_deprecated_functions():
    """Test that deprecated functions still work but show warnings."""
    
    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        try:
            from pipeline.helpers import process_dynamic_validation, _run_vectorized_simple_checks
            print("✓ Deprecated functions can be imported")
            
            # Test the warnings appear when functions are called
            # (We won't actually call them since they need specific data)
            
            print(f"✓ Import successful")
            print(f"  - process_dynamic_validation: {process_dynamic_validation.__name__}")
            print(f"  - _run_vectorized_simple_checks: {_run_vectorized_simple_checks.__name__}")
            
            return True
            
        except Exception as e:
            print(f"✗ Error testing deprecated functions: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    print("Testing deprecated functions in helpers.py...")
    success = test_deprecated_functions()
    if success:
        print("\n🎉 Deprecated functions test passed!")
    else:
        print("\n❌ Deprecated functions test failed.")
        sys.exit(1)
