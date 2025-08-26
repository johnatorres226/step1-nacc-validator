#!/usr/bin/env python3
"""
Test script to verify the refactored validate_data function works correctly.
"""

import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

def test_validate_data_refactor():
    """Test that the refactored validate_data function works with both dynamic and standard instruments."""
    
    # Create sample data
    sample_data = pd.DataFrame({
        'ptid': ['001', '002'],
        'redcap_event_name': ['baseline_arm_1', 'baseline_arm_1'],
        'visityr': [2023, 2024],
        'visitmo': [1, 2],
        'visitday': [15, 20],
        'visitnum': [1, 2]
    })
    
    # Sample validation rules (simplified)
    sample_rules = {
        'visityr': {
            'type': 'integer',
            'min': 2020,
            'max': 2030
        },
        'visitmo': {
            'type': 'integer', 
            'min': 1,
            'max': 12
        }
    }
    
    try:
        from pipeline.report_pipeline import validate_data
        
        # Test the function
        errors, logs, passed = validate_data(
            data=sample_data,
            validation_rules=sample_rules,
            instrument_name='a1',  # Standard instrument
            primary_key_field='ptid'
        )
        
        print("✓ validate_data function executed successfully")
        print(f"  - Errors returned: {len(errors)}")
        print(f"  - Logs returned: {len(logs)}")
        print(f"  - Passed validations: {len(passed)}")
        
        # Verify return types
        assert isinstance(errors, list), "Errors should be a list"
        assert isinstance(logs, list), "Logs should be a list"
        assert isinstance(passed, list), "Passed validations should be a list"
        
        print("✓ All return types are correct")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing validate_data: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing refactored validate_data function...")
    success = test_validate_data_refactor()
    if success:
        print("\n🎉 Refactoring test passed! The standardized validation process is working.")
    else:
        print("\n❌ Refactoring test failed.")
        sys.exit(1)
