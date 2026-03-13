# Compatibility Rule Errors Logged Under Wrong Variable

## Issue Summary
When a compatibility rule fails, the error is logged under the trigger variable (IF clause) instead of the actual failing variable (THEN/ELSE clause). This makes it difficult to identify which variable is causing the validation failure.

## Expected Behavior
When a compatibility rule fails, the error should be reported under the actual failing variable.

**Example:**
- Rule: `if othersign=1, then apraxsp must be in [1,2,3]`
- Data: `othersign=1, apraxsp=0`
- Expected: Error logged under `apraxsp` (the failing variable)

## Actual Behavior
The error is logged under `othersign` (the trigger variable), even though `apraxsp` is the variable that failed validation.

**Example error dictionary:**
```python
{
    'othersign': [
        "('apraxsp', ['unallowed value 0']) for if {'othersign': {'allowed': [1]}} "
        "then {'apraxsp': {'allowed': [1, 2, 3]}} - compatibility rule no: 0"
    ]
}
```

Note that the error is under the key `'othersign'` but the actual failing variable in the message is `'apraxsp'`.

## Root Cause
In `nacc_form_validator/nacc_validator.py`, the `_validate_compatibility()` method calls `self._error(field, ...)` where `field` is the trigger variable:

**Line 783-788:**
```python
if errors:
    for error in errors.items():  # error = ('apraxsp', ['unallowed value 0'])
        if error_def == ErrorDefs.COMPATIBILITY:
            self._error(
                field,  # ← BUG: This is the trigger variable (e.g., 'othersign')
                error_def,
                ...
            )
```

The `error` tuple contains the actual failing variable as `error[0]` (e.g., `'apraxsp'`), but the code passes `field` (the trigger variable) to `self._error()`.

## Reproduction Steps

1. Create a schema with a compatibility rule:
```python
from nacc_form_validator.nacc_validator import NACCValidator

schema = {
    "othersign": {
        "type": "integer",
        "nullable": True,
        "allowed": [0, 1, 8],
        "compatibility": [
            {
                "index": 0,
                "if": {"othersign": {"allowed": [1]}},
                "then": {"apraxsp": {"allowed": [1, 2, 3]}},
            }
        ],
    },
    "apraxsp": {
        "type": "integer",
        "nullable": True,
        "allowed": [0, 1, 2, 3, 8],
    },
}
```

2. Validate a record that fails the rule:
```python
record = {"othersign": 1, "apraxsp": 0}  # 0 is not in [1,2,3]
validator = NACCValidator(schema, allow_unknown=False)
is_valid = validator.validate(record)
print(validator.errors)
```

3. Observe the output:
```python
{'othersign': ["('apraxsp', ['unallowed value 0']) for if ..."]}
```

**Expected:**
```python
{'apraxsp': ["('apraxsp', ['unallowed value 0']) for if ..."]}
```

## Impact
- **Error Traceability:** Users cannot easily identify which variable failed validation by looking at error dictionary keys
- **CSV Reports:** When errors are exported to CSV with a "variable" column, the wrong variable name is recorded
- **Bulk Analysis:** Filtering errors by variable name returns incorrect results
- **Real-World Example:** In a b8_neurological_examination_findings form with 17 variables failing the same compatibility rule, all 17 errors are logged under `othersign` instead of their actual variable names (apraxsp, vhgazepal, opticatax, etc.)

## Suggested Fix
Change line 785 in `nacc_validator.py` from:
```python
self._error(field, error_def, ...)
```

To:
```python
self._error(error[0], error_def, ...)  # Use actual failing variable name
```

**However**, this may require verification that `error[0]` exists in the current validation schema context, as Cerberus may expect the field to be valid in the schema being validated.

## Workaround
Our downstream project has implemented a workaround by parsing the error message string to extract the actual variable name:

```python
import re

_COMPATIBILITY_ERROR_PATTERN = re.compile(r"^\('([^']+)',\s*\[")

def _extract_failing_variable(field_name: str, error_message: str) -> str:
    """Extract actual failing variable from compatibility error message."""
    match = _COMPATIBILITY_ERROR_PATTERN.search(error_message)
    if match:
        return match.group(1)
    return field_name
```

This allows us to correctly report the failing variable in our CSV output without modifying the upstream package.

## Environment
- Package version: nacc-form-validator (latest as of 2026-03-13, commit from 2026-01-12)
- Python version: 3.11.9
- Cerberus version: 1.3.5

## References
- Repository: https://github.com/naccdata/nacc-form-validator
- File: `nacc_form_validator/nacc_validator.py`
- Method: `_validate_compatibility()` (lines 680-792)
- Specific issue: Lines 783-788

## Additional Context
We discovered this issue when analyzing QC validation output for patient NM0117's b8_neurological_examination_findings form. All 17 compatibility rule errors were logged under the variable `othersign`, but the error messages clearly referenced different failing variables. This made it difficult to diagnose which variables needed correction.

Our fix has been validated in production and correctly identifies all failing variables. We've also added a comprehensive test suite to detect this issue in future dependency updates.
