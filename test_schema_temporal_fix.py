#!/usr/bin/env python3
"""
Test script to verify that temporal rules are excluded from schema when include_temporal_rules=False
"""

import sys
import os
sys.path.append('src')

from pipeline.utils.schema_builder import build_cerberus_schema_for_instrument

def test_temporal_exclusion():
    """Test that temporal rules are excluded when include_temporal_rules=False"""
    print("Testing schema building with temporal rules exclusion...")
    
    # Test with temporal rules included (default)
    print("\n1. Testing with temporal rules INCLUDED:")
    try:
        schema_with_temporal = build_cerberus_schema_for_instrument(
            "a1_participant_demographics", 
            include_temporal_rules=True
        )
        
        # Count how many fields have temporal rules
        temporal_count = 0
        for field, rules in schema_with_temporal.items():
            if 'temporalrules' in rules:
                temporal_count += 1
                print(f"   Field '{field}' has temporal rules")
                if temporal_count >= 3:  # Just show first few
                    print("   ... (and more)")
                    break
        
        print(f"   Total fields with temporal rules: {temporal_count}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test with temporal rules excluded
    print("\n2. Testing with temporal rules EXCLUDED:")
    try:
        schema_without_temporal = build_cerberus_schema_for_instrument(
            "a1_participant_demographics", 
            include_temporal_rules=False
        )
        
        # Count how many fields have temporal rules
        temporal_count = 0
        for field, rules in schema_without_temporal.items():
            if 'temporalrules' in rules:
                temporal_count += 1
                print(f"   Field '{field}' has temporal rules")
        
        print(f"   Total fields with temporal rules: {temporal_count}")
        
        if temporal_count == 0:
            print("   ✅ SUCCESS: No temporal rules found in schema!")
        else:
            print("   ❌ FAILURE: Temporal rules still present in schema")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_temporal_exclusion()
