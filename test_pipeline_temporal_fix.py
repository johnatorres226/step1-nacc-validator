#!/usr/bin/env python3
"""
Test script to verify the QC pipeline no longer produces temporal rule errors
"""

import sys
import os
sys.path.append('src')
import pandas as pd

# Simple test that creates a validation process like the pipeline would
from pipeline.report_pipeline import validate_data
from pipeline.utils.schema_builder import build_cerberus_schema_for_instrument
from pipeline.utils.instrument_mapping import load_json_rules_for_instrument

def test_pipeline_temporal_fix():
    """Test that the pipeline no longer has temporal rule errors"""
    print("Testing QC pipeline with temporal rules fix...")
    
    # Create a simple test record
    test_data = pd.DataFrame([{
        'ptid': 'TEST001',
        'birthyr': 1980,
        'sex': 1,
        'race': 1,
        'maristat': 1,
        'livsitua': 1
    }])
    
    print(f"Test data shape: {test_data.shape}")
    print("Test data:")
    print(test_data.head())
    
    try:
        # Load validation rules
        validation_rules = load_json_rules_for_instrument("a1_participant_demographics")
        
        # This should use the modified validation that excludes temporal rules
        errors, logs, passed_records = validate_data(
            data=test_data,
            validation_rules=validation_rules,
            instrument_name="a1_participant_demographics",
            primary_key_field="ptid"
        )
        
        print(f"\nValidation results:")
        print(f"  - Errors: {len(errors)}")
        print(f"  - Logs: {len(logs)}")
        print(f"  - Passed records: {len(passed_records)}")
        
        # Check if any temporal rule errors occurred
        temporal_errors = [err for err in errors if 'temporal' in str(err).lower() or 'datastore' in str(err).lower()]
        
        if temporal_errors:
            print(f"\n❌ Found {len(temporal_errors)} temporal rule errors:")
            for err in temporal_errors[:5]:  # Show first few
                print(f"   {err}")
        else:
            print("\n✅ SUCCESS: No temporal rule errors found!")
            
        # Show some sample errors if any
        if errors and len(errors) <= 10:
            print(f"\nSample errors (non-temporal):")
            for err in errors[:5]:
                print(f"   {err}")
        
    except Exception as e:
        print(f"\n❌ Error during pipeline test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline_temporal_fix()
