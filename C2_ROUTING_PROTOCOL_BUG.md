# C2 Routing Protocol Bug Investigation Report

**Date:** August 28, 2025  
**Investigator:** JT  
**System:** UDSv4 REDCap QC Validator  

## Executive Summary

The C2/C2T routing protocol is failing due to missing rule files in the packet-based directory structure. The system is correctly detecting that C2/C2T forms require dynamic routing based on the `loc_c2_or_c2t` discriminatory variable, but the corresponding rule files are missing from specific packet directories, causing validation errors.

## Problem Description

### Observed Error
```
System validation error: Schema Error: {'C2': [{'animals': ['unknown rule'], 'cerad1int': ['unknown rule'], ...}], 'C2T': [{'animals': ['unknown rule'], 'cerad1int': ['unknown rule'], ...}]}
```

### Root Cause Analysis

#### 1. **Missing C2 Rule File in I Packet Directory**
- **Expected:** `config/I/rules/c2_rules.json`
- **Status:** ❌ **MISSING**
- **Impact:** Records with `packet=I` and `loc_c2_or_c2t=C2` cannot be validated

#### 2. **Missing F Packet Directory Structure**
- **Expected:** `config/F/rules/` directory with both `c2_rules.json` and `c2t_rules.json`
- **Status:** ❌ **ENTIRELY MISSING**
- **Impact:** Records with `packet=F` cannot be processed at all

#### 3. **Incomplete Rule Coverage**
- **Working:** I4 packet has both `c2_rules.json` and `c2t_rules.json` ✅
- **Partial:** I packet has `c2t_rules.json` but missing `c2_rules.json` ⚠️
- **Broken:** F packet directory doesn't exist ❌

## Current System State

### Packet Directory Structure Analysis
```
config/
├── I/
│   └── rules/
│       ├── c2t_rules.json ✅
│       └── c2_rules.json ❌ MISSING
├── I4/
│   └── rules/
│       ├── c2_rules.json ✅
│       └── c2t_rules.json ✅
└── F/ ❌ ENTIRE DIRECTORY MISSING
```

### Configuration Mapping
The system correctly defines the rule mappings in `config_manager.py`:
```python
DYNAMIC_RULE_INSTRUMENTS = {
    "c2c2t_neuropsychological_battery_scores": {
        "discriminant_variable": "loc_c2_or_c2t",
        "rule_mappings": {
            "C2": "c2_rules.json",
            "C2T": "c2t_rules.json"
        }
    }
}
```

## Technical Flow Analysis

### Expected Routing Process
1. **Extract packet type** from record (I, I4, F)
2. **Get packet-specific base rules** from `config/{packet}/rules/`
3. **Check for dynamic instrument** (`c2c2t_neuropsychological_battery_scores`)
4. **Extract discriminant value** (`loc_c2_or_c2t` = C2 or C2T)
5. **Apply variant-specific rules** using the discriminant value as key

### Actual Behavior (Broken)
1. ✅ Extract packet type correctly
2. ❌ **FAIL:** Missing rule files cause schema building to fail
3. ❌ **FAIL:** Schema errors propagate to validation engine
4. ❌ **RESULT:** All variables show as "unknown rule"

### Log Evidence
```
13:07:46 | WARNING | pipeline.pipeline.io.packet_router | Rule file not found: C:\Users\johtorres\Documents\Github_Repos\final-projects\(Step 1) udsv4-redcap-qc-validator\config\I\rules\c2_rules.json
13:07:46 | WARNING | pipeline.pipeline.io.hierarchical_router | No rules found for loc_c2_or_c2t=C2 in packet I for c2c2t_neuropsychological_battery_scores, using base rules
```

## Impact Assessment

### Records Affected
- **I packet + C2 variant:** Cannot validate (falls back to base rules, but schema still fails)
- **F packet + any variant:** Cannot process at all
- **I4 packet:** ✅ Working correctly
- **I packet + C2T variant:** ✅ Working correctly

### Data Processing Impact
- **18 records processed** in latest run
- **56 validation errors** (many due to this bug)
- **Error rate: 16.37%** (likely inflated due to missing rules)

## Immediate Action Required

### Critical Fixes Needed

#### 1. **Create Missing C2 Rule File for I Packet**
- **File:** `config/I/rules/c2_rules.json`
- **Source:** Copy and adapt from `config/I4/rules/c2_rules.json`
- **Priority:** HIGH

#### 2. **Create Complete F Packet Directory Structure**
- **Directory:** `config/F/rules/`
- **Files needed:**
  - `c2_rules.json`
  - `c2t_rules.json`
  - All other instrument rule files
- **Priority:** HIGH

#### 3. **Validate Rule File Consistency**
- Ensure all three packet types (I, I4, F) have complete rule coverage
- Verify C2/C2T specific rules are properly differentiated by packet type
- **Priority:** MEDIUM

## Recommended Solution Steps

### Step 1: Emergency Fix
1. Copy `config/I4/rules/c2_rules.json` to `config/I/rules/c2_rules.json`
2. Test I packet + C2 routing immediately

### Step 2: Complete F Packet Support
1. Create `config/F/rules/` directory
2. Copy all rule files from I or I4 packet as base
3. Adapt rules for F packet specifics if needed

### Step 3: Validation and Testing
1. Run test suite to verify all packet + variant combinations work
2. Test with sample data from each packet type
3. Verify error rates drop to expected levels

### Step 4: Long-term Maintenance
1. Add validation checks for complete rule file coverage
2. Create deployment checklist for new packet types
3. Implement automated testing for all packet + variant combinations

## System Architecture Notes

### Routing Logic (Working Correctly)
The hierarchical routing system is functioning properly:
- ✅ `HierarchicalRuleResolver` correctly combines packet + dynamic routing
- ✅ Cache optimization working
- ✅ Fallback behavior triggers appropriately
- ✅ Error logging provides clear diagnostics

### Missing Components
- ❌ Complete rule file coverage across all packet types
- ❌ Validation for rule file existence during startup
- ❌ Clear documentation of required file structure

## Conclusion

The C2 routing protocol architecture is sound, but the implementation is incomplete due to missing rule files. This is a **configuration/deployment issue**, not a code logic problem. The fix requires creating the missing rule files and ensuring complete packet coverage.

**Estimated Fix Time:** 1-2 hours  
**Risk Level:** Medium (affects data validation accuracy)  
**Priority:** High (blocking correct C2/F packet validation)

---
*Report generated during C2 routing protocol debugging session*
*Next Steps: Implement emergency fix for I packet, then complete F packet structure*
