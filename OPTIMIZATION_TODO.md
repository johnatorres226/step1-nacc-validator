# Pipeline Optimization TODO

This document tracks the optimization and refactoring tasks to smoothen processes and reduce complexity in the pipeline while maintaining the per-record validation approach required for ETL modularity and nacc_form_validator compatibility.

## High Priority Items

### 1. **Deprecated Function Cleanup** 🔴
**Status**: Not Started  
**Target**: Next Major Version  
**Issue**: `helpers.py` contains deprecated functions maintained only for backward compatibility

#### Tasks:
- [x] **Phase 1**: Add removal timeline to deprecation warnings
- [ ] **Phase 2**: Identify all code/tests still using deprecated functions
  - [ ] `process_dynamic_validation()`
  - [ ] `_run_vectorized_simple_checks()`
- [ ] **Phase 3**: Update any remaining usage to new standardized approach
- [ ] **Phase 4**: Remove deprecated functions completely
- [ ] **Phase 5**: Update documentation and migration guides

**Files to Modify**: `src/pipeline/helpers.py`

---

### 2. **Dynamic Instrument Handling Consolidation** ✅
**Status**: Completed  
**Target**: Current Version  
**Issue**: Dynamic instrument processing scattered across multiple functions with redundant logic

#### Tasks:
- [x] **Create `DynamicInstrumentProcessor` class**
  ```python
  class DynamicInstrumentProcessor:
      def __init__(self, instrument_name: str):
          self.instrument_name = instrument_name
          self.discriminant_var = get_discriminant_variable(instrument_name)
          self.rule_mappings = get_rule_mappings(instrument_name)
          self._rule_cache = None
      
      def get_all_variables(self) -> List[str]:
          """Consolidate logic from multiple functions"""
      
      def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
          """Unified data preparation for dynamic instruments"""
      
      def get_rules_for_variant(self, variant: str) -> Dict[str, Any]:
          """Get rules for specific variant with caching"""
  ```
- [x] **Consolidate functions**:
  - [x] Merge logic from `process_dynamic_instrument_data()`
  - [x] Merge logic from `get_variables_for_instrument()` (dynamic part)
  - [x] Add rule caching to avoid repeated file loads
- [x] **Update calling code** to use new class
- [x] **Add unit tests** for new class
- [ ] **Remove redundant functions** after migration

**Files to Modify**: 
- `src/pipeline/helpers.py` (new class)
- `src/pipeline/report_pipeline.py` (update usage)

---

## Medium Priority Items

### 3. **Data Preparation Strategy Pattern** 🟡
**Status**: Not Started  
**Target**: Current Version  
**Issue**: `prepare_instrument_data_cache()` has complex branching logic

#### Tasks:
- [ ] **Create abstract base class**:
  ```python
  class InstrumentDataProcessor:
      @staticmethod
      def create_processor(instrument_name: str):
          if is_dynamic_rule_instrument(instrument_name):
              return DynamicInstrumentProcessor(instrument_name)
          else:
              return StandardInstrumentProcessor(instrument_name)
      
      def prepare_data(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
          pass  # Abstract method
  ```
- [ ] **Implement concrete classes**:
  - [ ] `StandardInstrumentProcessor`
  - [ ] `DynamicInstrumentProcessor` (from item #2)
- [ ] **Refactor `prepare_instrument_data_cache()`** to use strategy pattern
- [ ] **Update tests** to cover new classes

**Files to Modify**:
- `src/pipeline/helpers.py`
- `src/pipeline/instrument_processors.py` (new file)

---

### 4. **Function Parameter Reduction** 🟡
**Status**: Not Started  
**Target**: Current Version  
**Issue**: Many functions have excessive parameters making them hard to maintain

#### Tasks:
- [ ] **Create configuration dataclasses**:
  ```python
  @dataclass
  class ProcessingContext:
      data_df: pd.DataFrame
      instrument_list: List[str]
      rules_cache: Dict[str, Any]
      primary_key_field: str
      config: QCConfig

  @dataclass
  class ExportConfiguration:
      output_dir: Path
      date_tag: str
      time_tag: str
      include_logs: bool = True
      include_passed: bool = True
  ```
- [ ] **Refactor functions with 5+ parameters**:
  - [ ] `prepare_instrument_data_cache()` (5 params → context object)
  - [ ] `generate_tool_status_reports()` (8 params → context + export config)
  - [ ] `export_results_to_csv()` (8 params → context + export config)
  - [ ] `generate_aggregate_error_count_report()` (7 params → context + export config)
- [ ] **Update all calling code**
- [ ] **Update tests** with new parameter structure

**Files to Modify**:
- `src/pipeline/helpers.py`
- `src/pipeline/report_pipeline.py`
- `src/pipeline/context.py` (new file for dataclasses)

---

### 5. **Validation Logic Optimization** 🟢
**Status**: Updated Approach  
**Target**: Future Enhancement  
**Issue**: ~~Complex per-record processing~~ **UPDATED**: Maintain per-record approach but optimize supporting infrastructure

#### Updated Tasks:
- [ ] **Optimize schema selection caching**:
  - [ ] Cache schemas per instrument type to avoid repeated lookups
  - [ ] Pre-compute dynamic instrument variant schemas
- [ ] **Streamline error collection**:
  - [ ] Reduce object creation overhead in error logging
  - [ ] Optimize dictionary operations in `_log_validation_results()`
- [ ] **Improve rule loading efficiency**:
  - [ ] Add lazy loading for rule variants not used in current dataset
  - [ ] Cache rule mappings at class level rather than function level
- [ ] **Maintain per-record processing** (REQUIREMENT):
  - ✅ Keep per-record validation for ETL modularity
  - ✅ Maintain compatibility with nacc_form_validator engine
  - ✅ Preserve ability to filter to record subsets

**Files to Modify**:
- `src/pipeline/report_pipeline.py` (optimization only, not structure change)

---

## Low Priority Items

### 6. **Debug Information Simplification** 🟢
**Status**: Not Started  
**Target**: Future Enhancement  
**Issue**: `debug_variable_mapping()` is overly complex

#### Tasks:
- [ ] **Create `DataQualityAnalyzer` class**:
  ```python
  class DataQualityAnalyzer:
      def analyze_coverage(self, df: pd.DataFrame, instruments: List[str]) -> CoverageReport:
          """Simple coverage analysis"""
      
      def find_orphaned_columns(self, df: pd.DataFrame) -> List[str]:
          """Find columns not in any rules"""
      
      def generate_summary(self) -> Dict[str, Any]:
          """High-level summary only"""
  ```
- [ ] **Simplify debug output** to essential information only
- [ ] **Add configurable verbosity levels**
- [ ] **Move complex analysis to separate optional method**

**Files to Modify**:
- `src/pipeline/helpers.py`
- `src/pipeline/analytics.py` (new file)

---

### 7. **Report Generation Unification** 🟢
**Status**: Not Started  
**Target**: Future Enhancement  
**Issue**: Multiple similar report generation functions with redundant code

#### Tasks:
- [ ] **Create unified `ReportFactory` class**:
  ```python
  class ReportFactory:
      def __init__(self, context: ProcessingContext):
          self.context = context
      
      def generate_error_report(self) -> pd.DataFrame:
          """Generate error dataset"""
      
      def generate_status_report(self) -> pd.DataFrame:
          """Generate status report"""
      
      def generate_aggregate_report(self) -> pd.DataFrame:
          """Generate aggregate error counts"""
      
      def export_all(self, export_config: ExportConfiguration):
          """Export all reports with consistent naming"""
  ```
- [ ] **Consolidate report functions**:
  - [ ] `export_results_to_csv()`
  - [ ] `generate_aggregate_error_count_report()`
  - [ ] `generate_tool_status_reports()`
- [ ] **Standardize report formatting and naming**
- [ ] **Add report configuration options**

**Files to Modify**:
- `src/pipeline/report_pipeline.py`
- `src/pipeline/reports.py` (new file)

---

### 8. **Complete Visits Logic Optimization** 🟢
**Status**: Not Started  
**Target**: Future Enhancement  
**Issue**: Complex nested loops in `build_complete_visits_df()`

#### Tasks:
- [ ] **Implement vectorized approach**:
  ```python
  def build_complete_visits_df_optimized(
      data_df: pd.DataFrame, 
      instrument_list: List[str]
  ) -> Tuple[pd.DataFrame, List[Tuple[str, str]]]:
      """Optimized using vectorized operations"""
      completion_cols = [f"{inst}_complete" for inst in instrument_list 
                        if inst.lower() != "form_header"]
      
      # Vectorized approach instead of nested loops
      complete_mask = (data_df[completion_cols] == '2').all(axis=1)
      complete_visits = data_df[complete_mask][['ptid', 'redcap_event_name']].drop_duplicates()
      
      return complete_visits, list(complete_visits.itertuples(index=False, name=None))
  ```
- [ ] **Performance test** vectorized vs current implementation
- [ ] **Maintain backward compatibility** during transition
- [ ] **Update tests** with performance benchmarks

**Files to Modify**:
- `src/pipeline/helpers.py`

---

## Implementation Guidelines

### Priority Legend:
- 🔴 **High Priority**: Critical for code maintainability and cleanup
- 🟡 **Medium Priority**: Important for reducing complexity
- 🟢 **Low Priority**: Performance and convenience improvements

### Implementation Phases:

#### Phase 1: Foundation (High Priority Items 1-2)
1. Complete deprecated function cleanup
2. Implement dynamic instrument processor consolidation
3. Establish patterns for future improvements

#### Phase 2: Structure (Medium Priority Items 3-5)
1. Implement strategy patterns
2. Reduce function parameter complexity
3. Optimize validation infrastructure (without changing per-record approach)

#### Phase 3: Enhancement (Low Priority Items 6-8)
1. Improve debugging and analytics
2. Unify report generation
3. Performance optimizations

### Key Requirements to Maintain:
- ✅ **Per-record validation approach** (required for ETL modularity)
- ✅ **nacc_form_validator compatibility** (engine requirement)
- ✅ **Ability to filter to record subsets** (ETL requirement)
- ✅ **Backward compatibility** during transitions
- ✅ **Comprehensive test coverage** for all changes

---

## Progress Tracking

**Last Updated**: August 26, 2025  
**Overall Progress**: 2/8 items completed (25% complete)  

### Completed Items:

- **Item #2**: Dynamic Instrument Handling Consolidation ✅ (Complete)

### In Progress:

- **Item #1**: Deprecated Function Cleanup (25% complete - timeline added, next: identify usage)

### Next Up:

- Complete remaining phases of deprecated function cleanup
- Begin Phase 2: Structure improvements (Medium Priority Items)

---

## Notes

- All changes should maintain existing test compatibility
- Performance improvements should be measured and documented
- Breaking changes require major version bump and migration guide
- The per-record validation approach is a **firm requirement** and should not be changed
