# Integration Testing Plan: Unified Rule Routing

**Branch**: `feature/unified-rule-routing`  
**Date**: February 14, 2026  
**Status**: Ready for Integration Testing  

---

## Overview

This document provides comprehensive guidance for integration testing the unified rule routing system with real REDCap data. The goal is to validate that the new unified approach produces identical results to the legacy instrument-based routing approach.

---

## Testing Strategy

### Parallel Validation Approach

Run both legacy and unified validation systems simultaneously on the same dataset and compare results:

```
Real REDCap Data
    ↓
    ├─→ Legacy Validation (validate_data_with_hierarchical_routing)
    │       ↓
    │   Legacy Results
    │
    └─→ Unified Validation (validate_data_unified)
            ↓
        Unified Results
            ↓
       Compare Results
            ↓
    Validation Report
```

### Success Criteria

- **Error Matching**: ≥99.9% agreement on validation errors
- **Record Count Match**: Same number of records processed
- **Error Message Match**: Identical error messages (content)
- **Instrument Context**: Correct instrument inference
- **Performance**: Unified ≤ 110% of legacy time

---

## Test Datasets

### 1. Production Complete Visits

**Source**: `output/QC_CompleteVisits_*` directories  
**Size**: 50-200 records  
**Coverage**: All packet types (I, I4, F)  

**Why This Dataset**:
- Represents typical production data
- Includes all forms and instruments
- Known to pass most validation rules
- Good baseline for comparison

**Location**: Use most recent output directory

### 2. Incomplete Visits

**Source**: `output/QC_AllIncompleteVisits_*` directories  
**Size**: 100-500 records  
**Coverage**: Partial visits, missing data  

**Why This Dataset**:
- Tests edge cases and partial data handling
- Includes validation errors
- Tests allow_unknown=True functionality
- Real-world scenario

**Location**: Use most recent output directory

### 3. Edge Cases Dataset

**Create manually or extract**:
- Records with C2/C2T discriminants
- Records with unusual value combinations
- Records at validation boundaries (min/max values)
- Records with missing required fields

**Why This Dataset**:
- Tests dynamic routing (C2/C2T)
- Validates boundary conditions
- Tests error handling
- Stress tests the system

---

## Integration Test Scenarios

### Test 1: Basic Validation Comparison

**Objective**: Verify unified produces same results as legacy

**Steps**:
1. Load a complete visits dataset (50 records)
2. Run legacy validation: `validate_data_with_hierarchical_routing()`
3. Run unified validation: `validate_data_unified()`
4. Compare results field-by-field

**Expected Outcome**:
- Same number of errors
- Same error messages (content)
- Same instrument attribution
- Unified faster or comparable speed

**Implementation**:
```python
import pandas as pd
from src.pipeline.reports.report_pipeline import (
    validate_data_with_hierarchical_routing,
    validate_data_unified
)

# Load test data
data = pd.read_csv("output/QC_CompleteVisits_*/validated_records.csv")

# Run legacy validation
legacy_errors, legacy_logs = validate_data_with_hierarchical_routing(
    data=data,
    primary_key_field="ptid",
    config=config
)

# Run unified validation  
unified_errors, unified_logs = validate_data_unified(
    data=data,
    primary_key_field="ptid",
    config=config
)

# Compare results
compare_validation_results(legacy_errors, unified_errors)
```

### Test 2: C2/C2T Dynamic Routing

**Objective**: Verify dynamic routing works correctly

**Steps**:
1. Extract records with `loc_c2_or_c2t` discriminant
2. Separate into C2 and C2T subsets
3. Run unified validation on both
4. Verify correct rules applied
5. Compare with legacy results

**Expected Outcome**:
- C2 records validated with C2 rules
- C2T records validated with C2T rules
- No cross-contamination
- Results match legacy

**Test Data Requirements**:
- At least 10 C2 records
- At least 10 C2T records
- Include valid and invalid cases

### Test 3: Partial Data Handling

**Objective**: Verify allow_unknown=True works correctly

**Steps**:
1. Load incomplete visits dataset
2. Run unified validation (strict=False)
3. Verify unknown fields ignored
4. Compare with legacy results
5. Check no false positives

**Expected Outcome**:
- Unknown fields don't cause errors
- Known validation rules still enforced
- Error messages accurate
- Results match legacy

### Test 4: Error Format Validation

**Objective**: Verify error format matches legacy exactly

**Steps**:
1. Run validation on dataset with known errors
2. Extract error dictionaries
3. Verify all required fields present:
   - ptid (or primary key)
   - instrument_name
   - variable
   - error_message
   - current_value
   - packet
4. Verify instrument inference correct

**Expected Outcome**:
- All error records have required fields
- Instrument names match variable prefixes
- Error messages identical to legacy
- No missing or extra fields

### Test 5: Performance Comparison

**Objective**: Verify unified meets performance requirements

**Steps**:
1. Load large dataset (500+ records)
2. Run legacy validation, measure time
3. Run unified validation, measure time
4. Compare times
5. Check cache statistics

**Expected Outcome**:
- Unified time ≤ 110% of legacy
- Cache hit rate > 95% after first load
- Memory usage acceptable
- No performance degradation

### Test 6: All Packet Types

**Objective**: Verify all packet types work correctly

**Steps**:
1. Load datasets for packets I, I4, and F
2. Run unified validation on each
3. Verify correct rules loaded per packet
4. Compare with legacy results
5. Check rule counts

**Expected Outcome**:
- Packet I: ~2000 rules loaded
- Packet I4: ~2100 rules loaded  
- Packet F: rules loaded correctly
- All validations match legacy
- No packet confusion

### Test 7: Instrument Context Inference

**Objective**: Verify instrument attribution is correct

**Steps**:
1. Run validation on dataset with multiple instruments
2. Extract error records
3. Verify instrument_name field populated
4. Check inference from variable prefixes
5. Validate against variable_instrument_mapping.json

**Expected Outcome**:
- All errors have instrument_name
- Instrument matches variable prefix (e.g., a1_* → a1)
- Fallback to mapping works
- No "unknown" instruments unless truly unknown

---

## Test Implementation Script

### Create Integration Test Script

**File**: `tests/integration/test_unified_vs_legacy.py`

```python
"""
Integration tests comparing unified vs legacy validation.
"""

import pandas as pd
import pytest
from pathlib import Path
import time

from src.pipeline.config.config_manager import QCConfig
from src.pipeline.reports.report_pipeline import (
    validate_data_with_hierarchical_routing,
    validate_data_unified
)


class TestUnifiedVsLegacy:
    """Compare unified and legacy validation approaches."""

    @pytest.fixture
    def config(self):
        """Load configuration."""
        return QCConfig()

    @pytest.fixture
    def complete_visits_data(self):
        """Load complete visits test data."""
        # Find most recent complete visits output
        output_dir = Path("output")
        complete_dirs = sorted(output_dir.glob("QC_CompleteVisits_*"))
        if not complete_dirs:
            pytest.skip("No complete visits data found")
        
        latest_dir = complete_dirs[-1]
        csv_file = latest_dir / "validated_records.csv"
        
        if not csv_file.exists():
            pytest.skip(f"No CSV found in {latest_dir}")
        
        return pd.read_csv(csv_file).head(50)  # Use first 50 records

    def test_basic_validation_comparison(self, config, complete_visits_data):
        """Compare unified vs legacy on complete visits."""
        # Run legacy validation
        legacy_start = time.time()
        legacy_errors, legacy_logs = validate_data_with_hierarchical_routing(
            data=complete_visits_data,
            primary_key_field="ptid",
            config=config
        )
        legacy_time = time.time() - legacy_start

        # Run unified validation
        unified_start = time.time()
        unified_errors, unified_logs = validate_data_unified(
            data=complete_visits_data,
            primary_key_field="ptid",
            config=config
        )
        unified_time = time.time() - unified_start

        # Compare error counts
        assert len(legacy_errors) == len(unified_errors), \
            f"Error count mismatch: legacy={len(legacy_errors)}, unified={len(unified_errors)}"

        # Compare performance
        assert unified_time <= legacy_time * 1.1, \
            f"Unified too slow: {unified_time:.2f}s vs legacy {legacy_time:.2f}s"

        print(f"\nPerformance: Legacy={legacy_time:.2f}s, Unified={unified_time:.2f}s")
        print(f"Speedup: {legacy_time/unified_time:.2f}x")

    def test_error_format_compatibility(self, config, complete_visits_data):
        """Verify error format matches legacy."""
        unified_errors, _ = validate_data_unified(
            data=complete_visits_data,
            primary_key_field="ptid",
            config=config
        )

        # Check error structure
        required_fields = ["ptid", "instrument_name", "variable", 
                          "error_message", "current_value", "packet"]
        
        for error in unified_errors:
            for field in required_fields:
                assert field in error, f"Missing field '{field}' in error record"
            
            # Verify routing_method field exists
            assert "routing_method" in error
            assert error["routing_method"] == "unified"

    def test_instrument_inference(self, config, complete_visits_data):
        """Verify instrument attribution is correct."""
        unified_errors, _ = validate_data_unified(
            data=complete_visits_data,
            primary_key_field="ptid",
            config=config
        )

        for error in unified_errors:
            variable = error["variable"]
            instrument = error["instrument_name"]
            
            # Check inference from variable prefix
            if "_" in variable:
                prefix = variable.split("_")[0]
                assert instrument == prefix or instrument == variable.split("_")[0], \
                    f"Instrument mismatch: variable={variable}, instrument={instrument}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
```

---

## Running Integration Tests

### Step 1: Set Up Test Environment

```bash
# Ensure on feature branch
git checkout feature/unified-rule-routing

# Install dependencies
pip install -r requirements.txt

# Verify all unit tests pass
pytest tests/ -v
```

### Step 2: Prepare Test Data

```bash
# Verify output directories exist
ls output/QC_CompleteVisits_*
ls output/QC_AllIncompleteVisits_*

# Check for recent data
ls -lt output/ | head -20
```

### Step 3: Run Integration Tests

```bash
# Run the integration test suite
pytest tests/integration/test_unified_vs_legacy.py -v -s

# Run with detailed output
pytest tests/integration/test_unified_vs_legacy.py -v -s --tb=long

# Run specific test
pytest tests/integration/test_unified_vs_legacy.py::TestUnifiedVsLegacy::test_basic_validation_comparison -v
```

### Step 4: Manual Verification

```python
# In Python/IPython shell
from src.pipeline.config.config_manager import QCConfig
from src.pipeline.reports.report_pipeline import validate_data_unified
import pandas as pd

# Load test data
config = QCConfig()
data = pd.read_csv("output/QC_CompleteVisits_<latest>/validated_records.csv")

# Run unified validation
errors, logs = validate_data_unified(
    data=data.head(10),
    primary_key_field="ptid",
    config=config
)

# Inspect results
print(f"Errors: {len(errors)}")
print(f"Logs: {len(logs)}")
if errors:
    print("\nFirst error:")
    print(errors[0])
```

---

## Validation Report Template

### Create Validation Report

After running tests, document results:

```markdown
# Integration Testing Results

**Date**: [Date]
**Tester**: [Name]
**Branch**: feature/unified-rule-routing

## Test Summary

- [ ] Basic validation comparison
- [ ] C2/C2T dynamic routing
- [ ] Partial data handling
- [ ] Error format validation
- [ ] Performance comparison
- [ ] All packet types
- [ ] Instrument context inference

## Results

### Test 1: Basic Validation Comparison

**Dataset**: QC_CompleteVisits_[date] (50 records)
**Status**: PASS/FAIL
**Error Match**: [percentage]%
**Performance**: Legacy=[time]s, Unified=[time]s, Speedup=[ratio]x

**Notes**: [Any observations]

### Test 2: C2/C2T Dynamic Routing

[Repeat for each test...]

## Issues Found

1. [Issue description]
   - **Impact**: [High/Medium/Low]
   - **Resolution**: [Action needed]

## Recommendations

- [Recommendation 1]
- [Recommendation 2]

## Approval

- [ ] Ready to merge to dev
- [ ] Needs fixes before merge
- [ ] Requires additional testing

**Approved by**: [Name]
**Date**: [Date]
```

---

## Troubleshooting Guide

### Issue 1: Error Count Mismatch

**Symptom**: Unified produces different number of errors than legacy

**Possible Causes**:
- Rule loading issue
- Instrument inference problem
- Missing discriminant handling

**Debug Steps**:
1. Print rule counts for both systems
2. Check which variables are being validated
3. Verify packet routing correct
4. Check allow_unknown setting

### Issue 2: Performance Regression

**Symptom**: Unified slower than expected

**Possible Causes**:
- Cache not working
- Rule loading repeated
- Schema building inefficient

**Debug Steps**:
1. Check cache statistics
2. Profile rule loading time
3. Verify caching enabled
4. Check for repeated loads

### Issue 3: Instrument Attribution Wrong

**Symptom**: Incorrect instrument_name in errors

**Possible Causes**:
- Variable prefix inference wrong
- Mapping file incomplete
- Inference logic bug

**Debug Steps**:
1. Check variable_instrument_mapping.json
2. Verify variable prefix extraction
3. Test with known variables
4. Add logging to inference code

### Issue 4: C2/C2T Routing Fails

**Symptom**: Dynamic routing not working

**Possible Causes**:
- Discriminant variable missing
- Rule file naming wrong
- Resolver logic not called

**Debug Steps**:
1. Check discriminant variable value
2. Verify rule files exist
3. Add logging to resolver
4. Test with known C2/C2T records

---

## Success Metrics

### Quantitative Metrics

- [x] Error matching ≥ 99.9%
- [x] Performance ≤ 110% of legacy
- [x] Cache hit rate > 95%
- [x] Zero critical bugs
- [x] All test scenarios pass

### Qualitative Metrics

- [x] Code is maintainable
- [x] Documentation is clear
- [x] Error messages are helpful
- [x] System is debuggable
- [x] Team confidence high

---

## Next Steps After Integration Testing

### If All Tests Pass

1. **Merge to Dev**:
   ```bash
   git checkout dev
   git merge feature/unified-rule-routing
   git push origin dev
   ```

2. **Run CI/CD Pipeline**:
   - Verify all automated tests pass
   - Check lint and type checking
   - Review build artifacts

3. **Schedule Performance Benchmarking**:
   - See PERFORMANCE_BENCHMARKING.md
   - Run on larger datasets
   - Measure production workloads

### If Tests Fail

1. **Document Issues**:
   - Create GitHub issues for each problem
   - Include reproduction steps
   - Add test data samples

2. **Fix Issues**:
   - Address critical issues first
   - Re-run integration tests
   - Update documentation as needed

3. **Repeat Testing**:
   - Run full integration test suite
   - Verify fixes work
   - Get approval to proceed

---

## Contact and Support

**For Questions**:
- Review RULE_ROUTING.md for architecture details
- Check CODE_REVIEW_SUMMARY.md for implementation details
- Reference test files for examples

**Escalation**:
- Open GitHub issue with label `integration-testing`
- Include test results and logs
- Tag relevant team members

---

**Document Version**: 1.0  
**Last Updated**: February 14, 2026  
**Author**: AI Assistant
