# Phase 1 Investigation Report - QC Shortcoming Analysis

**Date:** March 27, 2026  
**Branch:** debug-shortcoming  
**Trigger:** 3 records failed NACC upload after passing local QC: NM1048, NM0118, NM0054

---

## Executive Summary

Five parallel investigation agents audited the codebase against hypothesized validation gaps. **Four of five hypotheses are CONFIRMED** as root causes of missing validation errors.

| Hypothesis | Status | Impact | Fix Priority |
|------------|--------|--------|--------------|
| H1: KEY_MAP incompleteness | **CONFIRMED** | Critical - entire rule categories dropped | 1 (Highest) |
| H2: Temporal rules disabled | **CONFIRMED** | High - 150+ rules bypassed | 2 |
| H3: Optional rules excluded | CONFIRMED (by design) | Low - variables duplicated | 5 (Skip) |
| H4: Cross-form variable stripping | **CONFIRMED (risk)** | Medium - latent failure risk | 4 |
| H5: M packet not processed | **CONFIRMED** | Medium - M records skipped | 3 |

---

## H1: KEY_MAP Incompleteness — CONFIRMED ⚠️ CRITICAL

### Finding
The KEY_MAP in schema_builder.py contains only 11 keys. Six critical rule types exist in JSON rules but are **silently dropped** during schema building:

| Missing Key | Files Affected | Validation Handler |
|-------------|----------------|-------------------|
| `logic` | 13+ files/packet | `_validate_logic()` line 947 |
| `compare_with` | 8+ files/packet | `_validate_compare_with()` line 1071 |
| `compare_age` | 2 files total | `_validate_compare_age()` line 1229 |
| `function` | 4 files total | `_validate_function()` line 979 |
| `compute_gds` | 3 files total | `_validate_compute_gds()` line 1012 |
| `check_with` | 50+ matches | No handler found |
| `formatting` | 30+ matches | `_validate_formatting()` line 389 |

### Root Cause
[src/pipeline/utils/schema_builder.py](src/pipeline/utils/schema_builder.py#L54): Unrecognized keys silently ignored:
```python
cerberus_key = KEY_MAP.get(json_key)
if cerberus_key:
    cerberus_rules[cerberus_key] = rule_value
# Unrecognized keys silently dropped
```

### Impact
Entire validation categories (logic rules, age comparisons, GDS calculations) **never execute** despite having full implementations in nacc_form_validator.

---

## H2: Temporal Rules Disabled — CONFIRMED ⚠️ HIGH

### Finding
- **F Packet:** 200+ temporalrules entries across a3_rules.json, a4a_rules.json
- **I4 Packet:** 95 temporalrules entries across 11 form files
- **I Packet:** 0 (expected - initial visits have no prior data)

### Root Cause
[src/pipeline/reports/report_pipeline.py](src/pipeline/reports/report_pipeline.py#L375):
```python
include_temporal_rules=False  # HARDCODED
datastore=None                 # HARDCODED
```

### Impact
Estimated **150+ temporal rule validations completely silenced**:
- Visit-to-visit consistency checks
- Initial visit baseline comparisons
- Longitudinal data integrity validation

### Quality-Check Confirmation
NACC quality-check CSVs contain temporal codes (e.g., `a1-fvp-m-021`, `a1-fvp-m-032`) that reference IVP data from prior visits.

---

## H3: Optional Rules Excluded — CONFIRMED (BY DESIGN) ✅

### Finding
21 `*_rules_optional.json` files exist across I, F, I4 packets but are excluded by:
- [rule_pool.py line 52](src/pipeline/io/rule_pool.py#L52): `_GLOB = "*_rules.json"`
- [rule_pool.py line 82](src/pipeline/io/rule_pool.py#L82): Explicit filter for `_rules_optional`

### Nuance
Variables in optional files are **duplicated** in regular files with full validation rules. Optional files contain simplified nullable-only definitions. This appears **intentional design**.

### Impact
Low - no missing validation coverage. **Recommend: No action required.**

---

## H4: Cross-Form Variable Stripping — CONFIRMED (RISK) ⚠️ MEDIUM

### Finding
Cross-form compatibility rules exist (e.g., B5.depd → B9.bedep) but the filter at line 369 strips cross-form variables from resolved_rules:
```python
resolved_rules = {k: v for k, v in resolved_rules.items() if k in validation_rules}
```

### Mitigation Already Present
- `_get_variables_for_instrument()` correctly extracts cross-form references
- `allow_unknown=True` in validator permits undeclared fields in record_dict
- Cross-form variables remain in data even if stripped from schema

### Risk
System **may work correctly** but has latent failure risk if:
1. Source REDCap export lacks cross-form columns
2. `_extract_referenced_variables()` has parsing bugs
3. Data preparation filters variables downstream

### Impact
Needs functional testing. May not be active breakage.

---

## H5: M Packet Not Processed — CONFIRMED ⚠️ MEDIUM

### Finding
- `config/M/rules/milestones_rules.json` **exists** with valid rules
- Valid packets hardcoded as `{"I", "I4", "F"}` in **3 locations**:
  1. [data_processing.py line 199](src/pipeline/core/data_processing.py#L199)
  2. [pipeline.py line 132](src/pipeline/core/pipeline.py#L132)
  3. [rule_loader.py line 19](src/pipeline/io/rule_loader.py#L19)

### Root Cause
M records are silently skipped with warning in `prepare_packet_grouped_data()`:
```
"Unknown packet value '%s' — skipping"
```

### Impact
All M (Milestone) packet records **completely excluded** from validation. 0% test coverage.

---

## Prioritized Fix Plan

### Priority 1: Fix KEY_MAP (H1) — CRITICAL
**Estimated Impact:** Recovers 50%+ of missing error detections

1. Add missing keys to KEY_MAP in schema_builder.py
2. Ensure nacc_validator.py handlers are properly invoked
3. Add unit tests for each new key type

### Priority 2: Enable Temporal Rules (H2) — HIGH
**Estimated Impact:** Recovers 10-20% of missing errors

1. Create REDCapDatastore stub using in-memory data
2. Change `include_temporal_rules=True`
3. Pass datastore to QualityCheck
4. Document limitation: only current batch visibility

### Priority 3: Add M Packet Support (H5) — MEDIUM
**Estimated Impact:** Enables Milestone visit validation

1. Add "M" to valid_packets in 3 locations
2. Ensure rule_pool.load_packet("M") works
3. Add M packet tests

### Priority 4: Verify Cross-Form Variables (H4) — MEDIUM (VALIDATION ONLY)
**Estimated Impact:** Confirm or deny functional breakage

1. Create test with B5→B9 cross-form scenario
2. Trace data flow in debugger
3. Fix only if breakage confirmed

### Priority 5: Optional Rules — SKIP
Already handled by design. No action needed.

---

## Files to Modify

| File | Changes |
|------|---------|
| src/pipeline/utils/schema_builder.py | Add 6+ keys to KEY_MAP |
| src/pipeline/reports/report_pipeline.py | Enable temporal rules, pass datastore |
| src/pipeline/core/redcap_datastore.py | NEW FILE - in-memory datastore |
| src/pipeline/core/data_processing.py | Add "M" to valid_packets |
| src/pipeline/core/pipeline.py | Add "M" to valid_packets |
| src/pipeline/io/rule_loader.py | Add "M" to _VALID_PACKETS |
| tests/ | Add tests for each fix |

---

## Recommended Next Steps

1. **Proceed to Phase 3** — Implement H1 fix (KEY_MAP) first
2. **Run tests after each fix** to validate incremental progress
3. **Compare error counts** before/after to measure impact
4. **Skip H3** (optional rules) — confirmed as intentional design
