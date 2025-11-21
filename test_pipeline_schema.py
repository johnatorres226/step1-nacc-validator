#!/usr/bin/env python3
"""Test the actual pipeline schema building and validation."""

from src.pipeline.utils.schema_builder import build_cerberus_schema_for_instrument
from nacc_form_validator.quality_check import QualityCheck

print("=" * 70)
print("Test: Building schema for a5d2 and validating anxiety field")
print("=" * 70)

# Build schema the same way the pipeline does
schema = build_cerberus_schema_for_instrument(
    instrument_name='a5d2_participant_health_history_clinician_assessed',
    include_temporal_rules=False,
    include_compatibility_rules=True
)

print(f"Schema has {len(schema)} fields")
print(f"anxiety field in schema: {'anxiety' in schema}")

if 'anxiety' in schema:
    print(f"\nanxiety schema:")
    import json
    print(json.dumps(schema['anxiety'], indent=2))

# Test validation with the actual schema
test_record = {
    'anxiet': '',  # Empty trigger
    'anxiety': 0   # Should be allowed since trigger is empty
}

qc = QualityCheck(pk_field='ptid', schema=schema, strict=False, datastore=None)
passed, sys_failure, errors, error_tree = qc.validate_record(test_record)

print(f"\nTest Record: anxiet='', anxiety=0")
print(f"Passed: {passed}")
print(f"Errors: {errors}")

if not passed:
    print("\n⚠️  PROBLEM: Empty trigger is causing compatibility rule to fire!")
else:
    print("\n✓ OK: Empty trigger does NOT fire compatibility rule")
