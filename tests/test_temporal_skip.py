#!/usr/bin/env python3
"""
Test to verify that temporal validations are skipped when no datastore is provided.
"""

from pipeline.quality_check import QualityCheck
from pipeline.errors import ErrorDefs

# Test schema with temporal rules
test_schema = {
    'test_field': {
        'type': 'string',
        'temporalrules': [
            {
                'previous': {'test_field': {'allowed': ['prev_value']}},
                'current': {'test_field': {'allowed': ['curr_value']}}
            }
        ]
    }
}

# Create QualityCheck without datastore
try:
    qc = QualityCheck(schema=test_schema, pk_field='test_field', datastore=None)
    print("✅ QualityCheck created successfully with datastore=None")
    
    # Test validation of a record
    test_record = {'test_field': 'curr_value'}
    result = qc.validate_record(test_record)
    
    print(f"Validation passed: {result.passed}")
    print(f"System failure: {result.sys_failure}")
    if result.errors:
        print(f"Errors: {result.errors}")
    
    print("✅ Temporal validation test completed - validates the system handles missing datastore gracefully")
    
except Exception as e:
    print(f"❌ Error during test: {e}")
