# Task 1: Function Analysis and Responsibility Breakdown

**Date:** August 26, 2025  
**Phase:** 5 - Helpers Refactoring  
**Task:** 1 - Analyze and Break Down Functions  

## Executive Summary

This document provides a detailed analysis of each function in `src/pipeline/helpers.py`, identifying multiple responsibilities and proposing how to break them down into smaller, single-purpose functions with proper error handling and clear data models.

## Current Function Analysis

### 1. `load_json_rules_for_instrument(instrument_name: str)`

**Current Responsibilities:**
- File path resolution 
- JSON file discovery from mapping
- File existence checking
- JSON parsing
- Error handling for JSON decode errors
- Data merging from multiple files
- Logging warnings and errors

**Problems:**
- Mixes file I/O, parsing, and business logic
- Handles multiple types of errors in one place
- Combines path resolution with data loading

**Proposed Breakdown:**
```python
# io/rules.py
def resolve_rule_file_paths(instrument_name: str) -> List[Path]:
    """Resolve file paths for an instrument's rule files."""

def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load and parse a single JSON file with proper error handling."""

def merge_rule_dictionaries(rule_dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple rule dictionaries into one."""

def load_json_rules_for_instrument(instrument_name: str) -> Dict[str, Any]:
    """Orchestrate loading of all rules for an instrument."""
```

### 2. `get_variables_for_instrument(instrument_name: str, rules_cache: Dict[str, Any])`

**Current Responsibilities:**
- Dynamic vs standard instrument detection
- Variable extraction from rules
- Dynamic instrument processor creation
- Cache access

**Problems:**
- Mixes detection logic with extraction logic
- Tight coupling to DynamicInstrumentProcessor

**Proposed Breakdown:**
```python
# core/instrument_detection.py
def is_dynamic_instrument(instrument_name: str) -> bool:
    """Determine if instrument uses dynamic rules."""

# core/variable_extraction.py
def extract_variables_from_rules(rules: Dict[str, Any]) -> List[str]:
    """Extract variable names from rule dictionary."""

def extract_variables_from_dynamic_instrument(instrument_name: str) -> List[str]:
    """Extract variables from dynamic instrument processor."""

def get_variables_for_instrument(instrument_name: str, rules_cache: Dict[str, Any]) -> List[str]:
    """Orchestrate variable extraction based on instrument type."""
```

### 3. `_preprocess_cast_types(df: pd.DataFrame, rules: Dict[str, Dict[str, Any]])`

**Current Responsibilities:**
- DataFrame copying
- Type detection from rules
- Pandas type casting for integers
- Pandas type casting for floats  
- Pandas type casting for dates/datetimes
- Error handling with coercion

**Problems:**
- Single function handles all data types
- Mixed concerns of type detection and casting
- No validation of casting success

**Proposed Breakdown:**
```python
# core/data_types.py
def detect_column_type(field_name: str, rules: Dict[str, Any]) -> Optional[str]:
    """Detect the expected type for a column from rules."""

def cast_to_integer_type(series: pd.Series) -> pd.Series:
    """Cast series to nullable integer type with error handling."""

def cast_to_float_type(series: pd.Series) -> pd.Series:
    """Cast series to float type with error handling."""

def cast_to_datetime_type(series: pd.Series) -> pd.Series:
    """Cast series to datetime type with error handling."""

def preprocess_cast_types(df: pd.DataFrame, rules: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    """Orchestrate type casting for all columns in dataframe."""
```

### 4. `process_dynamic_instrument_data(df, instrument, rules_cache, primary_key_field)`

**Current Responsibilities:**
- Dynamic instrument processor creation
- Data preparation orchestration
- Return tuple handling

**Problems:**
- Thin wrapper around DynamicInstrumentProcessor
- Unclear what "prepare_data" actually does
- Rules cache parameter is unused

**Proposed Breakdown:**
```python
# processors/dynamic_instruments.py
def create_dynamic_processor(instrument: str) -> DynamicInstrumentProcessor:
    """Factory function for creating dynamic instrument processors."""

def prepare_dynamic_instrument_data(
    df: pd.DataFrame, 
    instrument: str, 
    primary_key_field: str
) -> Tuple[pd.DataFrame, List[str]]:
    """Prepare data specifically for dynamic instruments."""
```

### 5. `load_rules_for_instruments(instrument_list: List[str])`

**Current Responsibilities:**
- Loop management over instruments
- Cache population
- Duplicate loading prevention
- Cache structure management

**Problems:**
- Simple iteration wrapped in function
- Cache management mixed with loading logic

**Proposed Breakdown:**
```python
# io/rules.py
class RulesCache:
    """Manages caching of instrument rules."""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def get_rules(self, instrument: str) -> Dict[str, Any]:
        """Get rules for instrument, loading if not cached."""
    
    def load_multiple(self, instruments: List[str]) -> None:
        """Load rules for multiple instruments into cache."""

def load_rules_for_instruments(instrument_list: List[str]) -> Dict[str, Dict[str, Any]]:
    """Load rules for multiple instruments using cache."""
```

### 6. `build_variable_maps(instrument_list, rules_cache)`

**Current Responsibilities:**
- Variable to instrument mapping creation
- Instrument to variables mapping creation
- Dynamic instrument detection and handling
- Missing rules warning
- Debug logging

**Problems:**
- Creates two different types of mappings in one function
- Mixes mapping logic with dynamic instrument handling
- Handles both forward and reverse mappings

**Proposed Breakdown:**
```python
# core/variable_mapping.py
def create_variable_to_instrument_map(
    instrument_list: List[str], 
    rules_cache: Dict[str, Any]
) -> Dict[str, str]:
    """Create mapping from variables to their instruments."""

def create_instrument_to_variables_map(
    instrument_list: List[str], 
    rules_cache: Dict[str, Any]
) -> Dict[str, List[str]]:
    """Create mapping from instruments to their variables."""

def build_variable_maps(
    instrument_list: List[str],
    rules_cache: Dict[str, Any]
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """Build both variable mapping types."""
```

### 7. `prepare_instrument_data_cache(data_df, instrument_list, instrument_variable_map, rules_cache, primary_key_field)`

**Current Responsibilities:**
- Processing context creation
- Configuration loading
- InstrumentDataCache instantiation
- Cache preparation orchestration
- Import management (circular dependency avoidance)

**Problems:**
- Mixes context creation with cache operations
- Too many parameters for orchestration function
- Circular dependency management indicates poor architecture

**Proposed Breakdown:**
```python
# core/data_processing.py
def create_processing_context(
    data_df: pd.DataFrame,
    instrument_list: List[str],
    rules_cache: Dict[str, Any],
    primary_key_field: str
) -> ProcessingContext:
    """Create context object for data processing."""

def prepare_instrument_cache_strategy(context: ProcessingContext) -> InstrumentDataCache:
    """Create cache strategy using context."""

def prepare_instrument_data_cache(
    data_df: pd.DataFrame,
    instrument_list: List[str],
    instrument_variable_map: Dict[str, List[str]],
    rules_cache: Dict[str, Any],
    primary_key_field: str,
) -> Dict[str, pd.DataFrame]:
    """Prepare cached dataframes for all instruments."""
```

### 8. `build_complete_visits_df(data_df, instrument_list)`

**Current Responsibilities:**
- Empty dataframe validation
- Completion column name generation
- Missing column handling with defaults
- Type conversion to strings
- Configuration access for primary key
- Vectorized completion mask creation
- Visit-level completion aggregation
- Complete visits identification
- Summary dataframe creation
- Tuple list generation for downstream processing
- Performance logging

**Problems:**
- MASSIVE function with 10+ distinct responsibilities
- Mixes data validation, processing, and result formatting
- Complex vectorized operations mixed with simple data prep
- Both summary creation and filtering tuple generation

**Proposed Breakdown:**
```python
# core/visit_processing.py
def validate_dataframe_not_empty(df: pd.DataFrame) -> None:
    """Validate that dataframe is not empty for processing."""

def generate_completion_column_names(instrument_list: List[str]) -> List[str]:
    """Generate completion column names from instrument list."""

def ensure_completion_columns_exist(df: pd.DataFrame, completion_cols: List[str]) -> pd.DataFrame:
    """Ensure all completion columns exist with default values."""

def normalize_completion_column_types(df: pd.DataFrame, completion_cols: List[str]) -> pd.DataFrame:
    """Convert completion columns to string type for consistent comparison."""

def create_completion_mask(df: pd.DataFrame, completion_cols: List[str]) -> pd.Series:
    """Create boolean mask for records with all instruments complete."""

def identify_complete_visits(df: pd.DataFrame, primary_key_field: str) -> List[Tuple[str, str]]:
    """Identify visits where all records are complete."""

def create_complete_visits_summary(complete_visits: List[Tuple[str, str]], completion_cols: List[str]) -> pd.DataFrame:
    """Create summary dataframe of complete visits."""

def build_complete_visits_df(data_df: pd.DataFrame, instrument_list: List[str]) -> Tuple[pd.DataFrame, List[Tuple[str, str]]]:
    """Orchestrate building complete visits dataframe and tuple list."""
```

### 9. `build_detailed_validation_logs(df, instrument, primary_key_field)`

**Current Responsibilities:**
- Record iteration
- Primary key extraction
- Event name extraction  
- Completion column name generation
- Completion status checking
- Pass/fail determination
- Error message generation
- Log entry dictionary creation
- List accumulation

**Problems:**
- Row-by-row processing instead of vectorized operations
- Mixes data extraction with business logic
- Single function handles multiple data transformations

**Proposed Breakdown:**
```python
# core/validation_logging.py
def extract_record_identifiers(record: pd.Series, primary_key_field: str) -> Tuple[str, str]:
    """Extract primary key and event name from record."""

def determine_completion_status(record: pd.Series, instrument: str) -> Tuple[str, str, str]:
    """Determine completion status, target variable, and status description."""

def create_validation_log_entry(
    primary_key: str,
    event: str,
    instrument: str,
    target_variable: str,
    completion_status: str,
    pass_status: str,
    error_msg: str
) -> Dict[str, Any]:
    """Create single validation log entry."""

def build_detailed_validation_logs(df: pd.DataFrame, instrument: str, primary_key_field: str) -> List[Dict[str, Any]]:
    """Build detailed validation logs for instrument records."""
```

## Data Models for Pipeline Steps

### Current Problems:
- Data passed as loose variables and basic types
- Unclear what each pipeline step expects and produces
- No validation of data between steps

### Proposed Data Models:

```python
# models/pipeline_data.py
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any
import pandas as pd

@dataclass
class RulesData:
    """Data model for loaded validation rules."""
    rules_cache: Dict[str, Dict[str, Any]]
    variable_to_instrument_map: Dict[str, str]
    instrument_to_variables_map: Dict[str, List[str]]

@dataclass 
class InstrumentCacheData:
    """Data model for prepared instrument cache."""
    instrument_dataframes: Dict[str, pd.DataFrame]
    processing_stats: Dict[str, int]
    
@dataclass
class CompleteVisitsData:
    """Data model for complete visits processing results."""
    summary_dataframe: pd.DataFrame
    complete_visits_tuples: List[Tuple[str, str]]
    total_visits_processed: int
    complete_visits_count: int

@dataclass
class ValidationLogsData:
    """Data model for validation logs."""
    log_entries: List[Dict[str, Any]]
    total_records_processed: int
    pass_count: int
    fail_count: int

@dataclass
class PipelineState:
    """Complete pipeline state at any point."""
    rules_data: RulesData
    instrument_cache: InstrumentCacheData
    complete_visits: CompleteVisitsData
    validation_logs: ValidationLogsData
    processing_metadata: Dict[str, Any]
```

## Error Handling Strategy

### Current Problems:
- Inconsistent error handling across functions
- Some functions suppress errors, others crash
- No error recovery or graceful degradation
- Error context often lost

### Proposed Error Handling:

```python
# core/errors.py
class PipelineError(Exception):
    """Base exception for pipeline errors."""
    pass

class RulesLoadingError(PipelineError):
    """Error loading validation rules."""
    pass

class DataProcessingError(PipelineError):
    """Error during data processing step."""
    pass

class ValidationError(PipelineError):
    """Error during validation step."""
    pass

# Example improved error handling:
def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load and parse a single JSON file with proper error handling."""
    try:
        if not file_path.exists():
            raise RulesLoadingError(f"Rule file not found: {file_path}")
            
        with open(file_path, 'r') as f:
            return json.load(f)
            
    except json.JSONDecodeError as e:
        raise RulesLoadingError(f"Invalid JSON in {file_path}: {e}") from e
    except IOError as e:
        raise RulesLoadingError(f"Cannot read file {file_path}: {e}") from e
```

## Implementation Priority

### High Priority (Week 1):
1. **`build_complete_visits_df`** - Most complex, highest impact
2. **`prepare_instrument_data_cache`** - Central to pipeline
3. **`build_variable_maps`** - Creates key data structures

### Medium Priority (Week 2):
4. **`load_json_rules_for_instrument`** - Foundational I/O
5. **`build_detailed_validation_logs`** - Important for reporting
6. **`_preprocess_cast_types`** - Data quality impact

### Lower Priority (Week 2):
7. **`get_variables_for_instrument`** - Simpler logic
8. **`process_dynamic_instrument_data`** - Thin wrapper
9. **`load_rules_for_instruments`** - Simple iteration

## Success Criteria for Task 1

- [ ] Each function identified has clear single responsibility
- [ ] Data models defined for all pipeline step inputs/outputs  
- [ ] Error handling strategy documented for each function type
- [ ] Breakdown plan created showing specific smaller functions
- [ ] Implementation priority established based on complexity and impact

---

**Next Steps:** Move to Task 2 - Begin implementing the broken-down functions with proper error handling and data models.
