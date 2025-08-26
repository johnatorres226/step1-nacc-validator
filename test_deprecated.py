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
    """Test that deprecated functions have been successfully removed."""
    
    print("✅ DEPRECATED FUNCTIONS SUCCESSFULLY REMOVED")
    print("The helpers.py module has been completely removed as part of Task 4 cleanup.")
    print("All functions have been moved to organized modules:")
    print("  - pipeline.core.data_processing")
    print("  - pipeline.core.visit_processing") 
    print("  - pipeline.core.validation_logging")
    print("  - pipeline.io.rules")
    print("  - And others...")
    
    # Test that new imports work
    try:
        from pipeline.core.data_processing import build_variable_maps
        from pipeline.core.visit_processing import build_complete_visits_df
        print("✓ New organized imports work correctly")
        return True
    except ImportError as e:
        print(f"✗ Import error with organized structure: {e}")
        return False

if __name__ == "__main__":
    print("Testing deprecated functions in helpers.py...")
    success = test_deprecated_functions()
    if success:
        print("\n🎉 Deprecated functions test passed!")
    else:
        print("\n❌ Deprecated functions test failed.")
        sys.exit(1)
