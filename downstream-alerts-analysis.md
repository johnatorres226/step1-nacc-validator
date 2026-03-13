# Downstream Alerts System Analysis

## Repository Analyzed
**Source**: [naccdata/flywheel-gear-extensions](https://github.com/naccdata/flywheel-gear-extensions)

## Executive Summary

The downstream mono-repo uses the same `nacc-form-validator` library but has an **enhanced error classification system** that distinguishes between:
- **Errors**: Critical validation failures that block data submission
- **Alerts**: Issues that should be reviewed but don't necessarily block submission
- **Warnings**: Minor issues for informational purposes

**Key Finding**: The current repo only captures "errors" while the downstream system has a REDCap-based metadata system that classifies each NACC QC check code as an error, alert, or warning. This classification is what generates the "alerts" you see after upload.

---

## Architecture Comparison

### Current Repo (udsv4-redcap-qc-validator)
```
User Input → nacc_form_validator → QC Errors → CSV Report
                                    (all classified as "errors")
```

### Downstream Repo (flywheel-gear-extensions)
```
User Input → form_qc_checker gear
          → nacc_form_validator 
          → Error Code Mapping
          → REDCap QC Checks Database (lookup error_type)
          → Classified Output (errors + alerts + warnings)
          → Flywheel Issue Manager UI
```

---

## Core Differences

### 1. Error Type Classification

**Downstream's Error Model** (`nacc_common/error_models.py`):
```python
class FileError(BaseModel):
    error_type: Literal["alert", "error", "warning"] = Field(alias="type")
    error_code: str = Field(alias="code")
    message: str
    # ... other fields
```

**Current Repo's Error Model** (`nacc_form_validator/errors.py`):
- Only supports generic "errors"
- No distinction between severity levels
- Missing alert classification capability

### 2. QC Checks Database

**Downstream System**:
- Maintains a **REDCap project** that stores metadata for each NACC QC check code
- Database schema includes:
  ```python
  class ErrorDescription(BaseModel):
      error_code: str        # e.g., "W0001", "E0042"
      error_type: str        # "alert", "error", or "warning"
      var_name: str          # Variable name
      form_name: str         # Form name
      check_type: str        # Type of validation
      short_desc: str        # Short description
      full_desc: str         # Full description
  ```

**Current Repo**:
- No centralized metadata database
- Error severity determined only by validation library rules
- No lookup mechanism for error classifications

### 3. Error Composition Process

**Downstream** (`form_qc_app/error_info.py`):
```python
def __write_qc_error(self, *, error_desc: ErrorDescription, ...):
    """Write QC error metadata when NACC QC check info available."""
    qc_error = self.__get_qc_error_object(
        error_type=error_desc.error_type,  # <-- From database!
        error_code=error_codes,
        error_msg=error_desc.full_desc,
        ...
    )
```

**Current Repo**:
- Hardcodes error_type as "error"
- No database lookup for severity classification
- Missing the alert generation logic

---

## Gap Analysis: Missing Alert Coverage

### What's Missing in Current Repo

1. **REDCap QC Checks Database Integration**
   - No connection to centralized error metadata
   - Can't distinguish between blocking errors and advisory alerts
   
2. **Error Type Classification System**
   - All validation failures treated uniformly as "errors"
   - No severity-based filtering or reporting
   
3. **Alert-Specific Rules**
   - Some NACC checks should generate alerts (non-blocking)
   - Current system can't express "this should warn but not fail"

4. **Error Code Mapping**
   - Downstream maps each validation rule to NACC error codes
   - These codes then lookup severity from database
   - Current repo has basic error code mapping but no severity lookup

---

## How Alerts are Generated Downstream

### Step-by-Step Process

1. **Data Validation**
   - Form data validated using `nacc-form-validator` library (same as current repo)
   - Validation errors collected

2. **Error Code Mapping** 
   - Each validation error mapped to NACC QC check code
   - Schema defines: `rule_name → NACC_code` mapping
   - Example: `{"required": {"code": "E0001"}, "temporal": {"code": "W0042"}}`

3. **Database Lookup**
   - Query REDCap project with error codes
   - Retrieve `ErrorDescription` objects containing:
     - Full error message
     - Variable name
     - **error_type** (alert/error/warning)

4. **Error Type Assignment**
   ```python
   qc_error = FileError(
       error_type=error_desc.error_type,  # "alert" or "error"
       error_code=error_desc.error_code,
       message=error_desc.full_desc,
       ...
   )
   ```

5. **Conditional Processing**
   - Errors: Block data submission
   - Alerts: Allow submission but flag for review
   - Warnings: Informational only

---

## Coverage Opportunities

### Where Current Repo Can Capture Alerts

To match downstream functionality, you need to:

1. **Create Alert Classification System**
   - Define which NACC error codes should be alerts vs errors
   - Options:
     a. Create local configuration file (JSON/YAML)
     b. Connect to REDCap QC checks database (if accessible)
     c. Implement rule-based classification logic

2. **Enhance Error Model**
   ```python
   # Add to nacc_form_validator/errors.py
   class ValidationError:
       error_type: Literal["alert", "error", "warning"]  # Add this
       error_code: str
       message: str
       # ... existing fields
   ```

3. **Update Quality Check Logic**
   - Modify `quality_check.py` to accept error_type parameter
   - Pass severity classification through validation chain

4. **Separate Reporting**
   - Generate separate sections for errors vs alerts
   - Add summary: "X errors, Y alerts found"
   - Consider separate CSV outputs

### Example Implementation Path

```python
# 1. Create alert classification config
ALERT_CODES = {
    "temporal": ["W0042", "W0043"],  # Temporal checks are warnings
    "logic": ["A0010", "A0011"],     # Logic issues are alerts
    "required": ["E0001", "E0002"],  # Required fields are errors
}

# 2. Classify during validation
def classify_error_type(error_code: str) -> str:
    if error_code.startswith("E"):
        return "error"
    elif error_code.startswith("W"):
        return "warning"
    elif error_code.startswith("A"):
        return "alert"
    return "error"  # default

# 3. Update error reporting
def generate_report(validation_results):
    errors = [e for e in validation_results if e.error_type == "error"]
    alerts = [e for e in validation_results if e.error_type == "alert"]
    warnings = [e for e in validation_results if e.error_type == "warning"]
    
    # Write separate sections
    write_errors_section(errors)
    write_alerts_section(alerts)
    write_warnings_section(warnings)
```

---

## Key Files to Review in Downstream Repo

### Core Alert Logic
- [`gear/form_qc_checker/src/python/form_qc_app/error_info.py`](https://github.com/naccdata/flywheel-gear-extensions/blob/main/gear/form_qc_checker/src/python/form_qc_app/error_info.py)
  - `ErrorDescription` class with `error_type` field
  - `REDCapErrorStore` for database queries
  - `ErrorComposer` for generating classified errors

### Error Models
- [`nacc-common/src/python/nacc_common/error_models.py`](https://github.com/naccdata/flywheel-gear-extensions/blob/main/nacc-common/src/python/nacc_common/error_models.py)
  - `FileError` with `error_type: Literal["alert", "error", "warning"]`
  - `ClearedAlertModel` for alert management
  - `ValidationModel` with cleared alerts tracking

### Main Validation Flow
- [`gear/form_qc_checker/src/python/form_qc_app/main.py`](https://github.com/naccdata/flywheel-gear-extensions/blob/main/gear/form_qc_checker/src/python/form_qc_app/main.py)
  - Complete end-to-end validation process
  - Integration with REDCap error store
  - Error metadata composition

---

## REDCap QC Checks Database Schema

The downstream system uses a REDCap project with this structure:

| Field | Type | Description |
|-------|------|-------------|
| `error_code` | Record ID | Unique NACC error code (e.g., "E0001") |
| `error_type` | Text | "error", "alert", or "warning" |
| `var_name` | Text | Variable name (e.g., "birthmo") |
| `form_name` | Text | Form name (e.g., "A1") |
| `check_type` | Text | Validation type (e.g., "required", "logic") |
| `short_desc` | Text | Brief description |
| `full_desc` | Text | Full error message |

**Access**: You would need credentials to the NACC QC checks REDCap project to query this database.

---

## Recommendations

### Immediate Actions

1. **Map Error Codes to Severity**
   - Review the current QC validation rules
   - Classify each rule as error/alert/warning
   - Create configuration file with mappings

2. **Enhance Error Model**
   - Add `error_type` field to error classes
   - Update CSV output to include severity column
   - Modify reporting logic to handle classifications

3. **Request REDCap Access** (Optional)
   - Contact NACC data team for QC checks database access
   - Sync error classifications with official definitions
   - Implement REDCapErrorStore equivalent

### Long-term Strategy

1. **Align with Upstream**
   - Ensure your classifications match what downstream generates
   - Test data that passes your QC should not generate alerts downstream
   - Consider contributing alert logic back to `nacc-form-validator` library

2. **User Experience**
   - Show alerts separately from errors
   - Allow data submission with alerts (if appropriate)
   - Provide clear guidance on error vs alert resolution

3. **Validation Coverage**
   - Monitor which alerts are generated post-upload
   - Add those checks to your pre-upload validation
   - Continuously sync with downstream rule updates

---

## Questions to Investigate Further

1. **What specific NACC error codes are classified as alerts vs errors?**
   - Need access to REDCap QC checks database
   - Or review downstream validation rule definitions

2. **Are there additional validation rules in downstream not present in your repo?**
   - Compare rule definitions files
   - Look for S3 bucket rules ("nacc-qc-rules" bucket)

3. **Do alerts have different resolution workflows?**
   - Some alerts might be informational only
   - Others might require acknowledgment/clearance
   - Check `ClearedAlertModel` usage for workflow details

4. **What is the complete set of NACC error code prefixes?**
   - E#### = Errors (blocking)
   - W#### = Warnings (informational)
   - A#### = Alerts (review required)
   - Need confirmation from NACC standards

---

## Next Steps

1. ✅ **Complete** - Analyzed downstream alert system architecture
2. **TODO** - Request access to NACC QC checks REDCap database
3. **TODO** - Map current validation rules to error/alert/warning categories
4. **TODO** - Implement error type classification in current repo
5. **TODO** - Test with real data to compare pre/post-upload issues
6. **TODO** - Document alert resolution procedures

---

## Contact Points

- **Downstream Repo**: https://github.com/naccdata/flywheel-gear-extensions
- **NACC Form Validator**: https://github.com/naccdata/nacc-form-validator
- **Documentation**: https://naccdata.github.io/flywheel-gear-extensions/

For REDCap database access or NACC error code classifications, contact the NACC data team or repository maintainers.
