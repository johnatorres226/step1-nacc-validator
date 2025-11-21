#!/usr/bin/env python3
"""Test compatibility rule evaluation with empty values."""

from nacc_form_validator.quality_check import QualityCheck

# Test schema: if anxiet=1 then anxiety=1
schema = {
    'anxiet': {'type': 'integer', 'allowed': [1], 'nullable': True},
    'anxiety': {
        'type': 'integer',
        'required': True,
        'allowed': [0, 1, 2, 9],
        'compatibility': [
            {
                'index': 0,
                'if': {'anxiet': {'allowed': [1]}},
                'then': {'anxiety': {'allowed': [1]}}
            }
        ]
    }
}

print("=" * 70)
print("Test 1 - Empty string anxiet (should NOT trigger rule)")
print("=" * 70)
test_record = {'anxiet': '', 'anxiety': 0}
print(f"Data BEFORE validation: anxiet='{test_record['anxiet']}', anxiety={test_record['anxiety']}")

qc = QualityCheck(pk_field='test', schema=schema, strict=False)
passed, sys_failure, errors, error_tree = qc.validate_record(test_record)

print(f"Data AFTER validation: anxiet={test_record.get('anxiet')}, anxiety={test_record['anxiety']}")
print(f"Passed: {passed}")
print(f"Errors: {errors}")
print()

print("=" * 70)
print("Test 2 - None anxiet (should NOT trigger rule)")
print("=" * 70)
test_record2 = {'anxiet': None, 'anxiety': 0}
print(f"Data: anxiet=None, anxiety=0")

passed2, sys_failure2, errors2, error_tree2 = qc.validate_record(test_record2)
print(f"Passed: {passed2}")
print(f"Errors: {errors2}")
print()

print("=" * 70)
print("Test 3 - anxiet=1 (SHOULD trigger rule and fail)")
print("=" * 70)
test_record3 = {'anxiet': 1, 'anxiety': 0}
print(f"Data: anxiet=1, anxiety=0")

passed3, sys_failure3, errors3, error_tree3 = qc.validate_record(test_record3)
print(f"Passed: {passed3}")
print(f"Errors: {errors3}")
print()

print("=" * 70)
print("Test 4 - anxiet=1, anxiety=1 (SHOULD pass)")
print("=" * 70)
test_record4 = {'anxiet': 1, 'anxiety': 1}
print(f"Data: anxiet=1, anxiety=1")

passed4, sys_failure4, errors4, error_tree4 = qc.validate_record(test_record4)
print(f"Passed: {passed4}")
print(f"Errors: {errors4}")
