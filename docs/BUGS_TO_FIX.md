# BUGS TO FIX - Critical Reporting Issues

## Investigation Summary
Date: August 28, 2025  
Report Run: QC_CompleteVisits_28AUG2025_122309  
User: JT  

## Critical Issues Identified

### 🚨 **BUG #1: Missing Packet Column in CompletedVisits Report**
**File:** `PTID_CompletedVisits_28AUG2025_122315.csv`  
**Issue:** The CompletedVisits CSV lacks the `packet` column entirely  
**Current Columns:** `ptid,redcap_event_name,complete_instruments_count,completion_status`  
**Expected Columns:** `ptid,redcap_event_name,packet,complete_instruments_count,completion_status`  

**Root Cause Analysis:**
- The `create_complete_visits_summary()` function creates a DataFrame with packet information but may not be properly preserving it in the final output
- The packet column gets created but might be dropped during report generation
- Investigation needed in: `src/pipeline/core/visit_processing.py` lines 160-180

**Severity:** HIGH - Missing critical packet information for complete visits analysis

---

### 🚨 **BUG #2: "Unknown" Packet Values in Error Dataset**
**File:** `Final_Error_Dataset_28AUG2025_122315.csv`  
**Issue:** All error records show `packet` value as "unknown" instead of actual packet values (I, I4, F)  
**Evidence:** Sample error shows `packet,redcap_event_name` with values `unknown,udsv4_ivp_1_arm_1`  

**Root Cause Analysis:**
- The validation functions are not properly accessing or preserving packet information from source data
- Error record creation is defaulting to "unknown" packet values
- The packet information exists in PassedValidations (shows "I4") but not flowing to error records
- Investigation needed in: `src/pipeline/report_pipeline.py` validation functions

**Severity:** HIGH - Critical for packet-based error analysis and routing verification

---

### 🚨 **BUG #3: Missing json_rule_path in RulesValidation Log**
**File:** `Log_RulesValidation_28AUG2025_122315.csv`  
**Issue:** The RulesValidation log does not include the `json_rule_path` column  
**Current Columns:** `ptid,variable,json_rule,rule_file,redcap_event_name,instrument_name`  
**Expected Columns:** `ptid,variable,json_rule,rule_file,json_rule_path,redcap_event_name,instrument_name`  

**Root Cause Analysis:**
- The build_detailed_validation_logs function was not updated to include json_rule_path
- This was specifically requested but not implemented in the validation logging functions
- Investigation needed in: `src/pipeline/report_pipeline.py` logging functions

**Severity:** MEDIUM - Missing path information for rule traceability

---

### 🚨 **BUG #4: Duplicative and Inconsistent Packet Values in EventCompletenessScreening**
**File:** `Log_EventCompletenessScreening_28AUG2025_122315.csv`  
**Issue:** The log shows inconsistent packet values - some records have actual packet values (I, I4) while others show "unknown"  
**Evidence:** 
- Beginning of file: Correct packet values (`I4`, `I`)
- End of file: "unknown" packet values for c2c2t_neuropsychological_battery_scores
- Total lines: 343 (indicating potential duplicates for 18 records × 19 instruments = 342 expected)

**Root Cause Analysis:**
- EventCompletenessScreening generation is processing records multiple times
- Different validation stages may be using different packet source data
- Later validation stages losing packet information
- Investigation needed in: Event completeness logging functions

**Severity:** MEDIUM - Data quality issue affecting completeness analysis

## Investigation Plan

### 🔍 **Phase 1: Data Flow Analysis**
1. **Trace packet information flow** from source data through all processing stages
2. **Identify where packet values are lost** in the validation pipeline
3. **Check data preparation stages** for packet column handling

### 🔍 **Phase 2: Function-Specific Investigation**
1. **CompletedVisits Generation** (`src/pipeline/core/visit_processing.py`)
   - Check `create_complete_visits_summary()` function output
   - Verify packet column preservation in report generation
   
2. **Error Record Creation** (`src/pipeline/report_pipeline.py`)
   - Examine error record construction in validation functions
   - Ensure packet information is captured from source record
   
3. **RulesValidation Logging** (`src/pipeline/report_pipeline.py`)
   - Update `build_detailed_validation_logs()` to include json_rule_path
   - Add json_rule_path tracking to all validation functions

4. **EventCompletenessScreening** (Investigation needed)
   - Identify source of duplicate processing
   - Fix packet value inconsistency

### 🔍 **Phase 3: Source Data Verification**
1. **Check source data packet availability** in fetched REDCap data
2. **Verify packet column exists** in all processing stages
3. **Confirm packet values are properly propagated**

## Priority Fix Order

### **Priority 1 (Critical - Fix Immediately)**
1. **BUG #2** - Fix "unknown" packet values in error dataset
2. **BUG #1** - Add missing packet column to CompletedVisits

### **Priority 2 (High - Fix Soon)**
3. **BUG #3** - Add json_rule_path to RulesValidation log
4. **BUG #4** - Fix EventCompletenessScreening duplicates and packet inconsistency

## Expected Outcomes

### **After Fixes:**
1. **CompletedVisits** will include packet information for proper visit analysis
2. **Error Dataset** will show actual packet values (I, I4, F) for targeted error analysis
3. **RulesValidation** will include full rule path information for traceability
4. **EventCompletenessScreening** will have consistent packet values without duplicates

## Verification Strategy

### **Test Cases:**
1. Run complete_visits mode with JT initials again
2. Verify all reports contain proper packet information
3. Confirm no "unknown" packet values (except for truly missing data)
4. Validate report row counts match expected values
5. Check that all columns are present in expected formats

---

**Status:** INVESTIGATION COMPLETE - READY FOR IMPLEMENTATION  
**Next Step:** Begin Priority 1 fixes with packet value propagation analysis
