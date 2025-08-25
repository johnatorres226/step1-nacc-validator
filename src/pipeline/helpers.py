"""
This module provides helper functions for the QC pipeline.

It includes utilities for:
- Loading and managing JSON validation rules.
- Mapping variables to instruments.
- Handling dynamic rule selection for complex instruments.
- Preprocessing data for validation.
- Generating detailed logs and reports.
"""
from typing import Tuple, List, Dict, Any, Optional
import pandas as pd
import numpy as np
import json
from pathlib import Path

from .config_manager import (
    get_config, instrument_json_mapping,
    is_dynamic_rule_instrument, get_discriminant_variable, get_rule_mappings,
    get_core_columns, get_completion_columns, get_special_columns
)
from .logging_config import get_logger
from .instrument_mapping import load_dynamic_rules_for_instrument
from abc import ABC, abstractmethod

logger = get_logger(__name__)


# =============================================================================
# VALIDATION CLASSES - MODULAR SYSTEM
# =============================================================================

class ValidationResult:
    """Container for validation results."""
    
    def __init__(self):
        self.errors: List[Dict[str, Any]] = []
        self.valid_mask: Optional[pd.Series] = None
        
    def add_error(self, ptid: str, event_name: str, instrument_name: str, 
                  variable: str, current_value: Any, expected_value: Any, error_msg: str):
        """Add a validation error to the results."""
        self.errors.append({
            "ptid": ptid,
            "redcap_event_name": event_name,
            "instrument_name": instrument_name,
            "variable": variable,
            "current_value": current_value,
            "expected_value": expected_value,
            "error": error_msg
        })
    
    def combine_with(self, other: 'ValidationResult'):
        """Combine this result with another validation result."""
        self.errors.extend(other.errors)
        if self.valid_mask is not None and other.valid_mask is not None:
            self.valid_mask &= other.valid_mask


class BaseValidator(ABC):
    """Abstract base class for all validators."""
    
    @abstractmethod
    def validate(self, df: pd.DataFrame, field: str, config: Dict[str, Any], 
                 instrument_name: str) -> ValidationResult:
        """Validate a field according to its configuration."""
        pass


class RangeValidator(BaseValidator):
    """Validates min/max range constraints."""
    
    def validate(self, df: pd.DataFrame, field: str, config: Dict[str, Any], 
                 instrument_name: str) -> ValidationResult:
        result = ValidationResult()
        result.valid_mask = pd.Series(True, index=df.index)
        
        if field not in df.columns:
            return result
            
        series = df[field]
        nullable = config.get("nullable", False)
        dtype = config.get("type")
        mn_raw, mx_raw = config.get("min"), config.get("max")
        
        if mn_raw is None and mx_raw is None:
            return result
            
        mask = pd.Series(True, index=df.index)
        
        if dtype in ("date", "datetime"):
            dt_series = pd.to_datetime(series, errors="coerce")
            mn_date = pd.to_datetime(mn_raw, errors="coerce") if mn_raw is not None else None
            mx_date = pd.to_datetime(mx_raw, errors="coerce") if mx_raw is not None else None
            
            if mn_date is not None:
                mask &= dt_series >= mn_date
            if mx_date is not None:
                mask &= dt_series <= mx_date
            if nullable:
                mask |= dt_series.isna()
        else:
            num = pd.to_numeric(series, errors="coerce")
            mn, mx = None, None
            try:
                mn = float(mn_raw) if mn_raw is not None else None
            except (TypeError, ValueError):
                pass
            try:
                mx = float(mx_raw) if mx_raw is not None else None
            except (TypeError, ValueError):
                pass
            
            if mn is not None:
                mask &= num >= mn
            if mx is not None:
                mask &= num <= mx
            if nullable:
                mask |= num.isna()
        
        # Add errors for invalid values
        bad_indices = df.index[~mask]
        for idx in bad_indices:
            row = df.loc[idx]
            result.add_error(
                ptid=row["ptid"],
                event_name=row["redcap_event_name"],
                instrument_name=instrument_name,
                variable=field,
                current_value=row[field],
                expected_value=f"[{mn_raw},{mx_raw}]",
                error_msg=f"Value {row[field]} outside [{mn_raw},{mx_raw}]"
            )
        
        result.valid_mask = mask
        return result


class RegexValidator(BaseValidator):
    """Validates regex/pattern constraints."""
    
    def validate(self, df: pd.DataFrame, field: str, config: Dict[str, Any], 
                 instrument_name: str) -> ValidationResult:
        result = ValidationResult()
        result.valid_mask = pd.Series(True, index=df.index)
        
        if field not in df.columns:
            return result
            
        pattern = config.get("regex")
        if not pattern:
            return result
            
        series = df[field]
        nullable = config.get("nullable", False)
        
        mask = series.astype(str).str.match(pattern)
        if nullable:
            mask |= series.isna() | (series == "")
        
        # Add errors for invalid values
        bad_indices = df.index[~mask]
        for idx in bad_indices:
            row = df.loc[idx]
            result.add_error(
                ptid=row["ptid"],
                event_name=row["redcap_event_name"],
                instrument_name=instrument_name,
                variable=field,
                current_value=row[field],
                expected_value=pattern,
                error_msg=f"'{row[field]}' does not match /{pattern}/"
            )
        
        result.valid_mask = mask
        return result


class AllowedValuesValidator(BaseValidator):
    """Validates allowed values constraints."""
    
    def validate(self, df: pd.DataFrame, field: str, config: Dict[str, Any], 
                 instrument_name: str) -> ValidationResult:
        result = ValidationResult()
        result.valid_mask = pd.Series(True, index=df.index)
        
        if field not in df.columns:
            return result
            
        allowed = config.get("allowed")
        if allowed is None:
            return result
            
        series = df[field]
        nullable = config.get("nullable", False)
        dtype = config.get("type")
        
        # Handle numeric vs string comparison
        if dtype in ("integer", "float") and all(isinstance(x, (int, float)) for x in allowed):
            comp = pd.to_numeric(series, errors="coerce")
        else:
            comp = series
            
        mask = comp.isin(allowed)
        if nullable:
            mask |= series.isna() | (series == "")
        
        # Add errors for invalid values
        bad_indices = df.index[~mask]
        for idx in bad_indices:
            row = df.loc[idx]
            result.add_error(
                ptid=row["ptid"],
                event_name=row["redcap_event_name"],
                instrument_name=instrument_name,
                variable=field,
                current_value=row[field],
                expected_value=allowed,
                error_msg=f"'{row[field]}' not in {allowed}"
            )
        
        result.valid_mask = mask
        return result


class SimpleChecksValidator:
    """Orchestrates multiple simple validation checks."""
    
    def __init__(self):
        self.validators = [
            RangeValidator(),
            RegexValidator(),
            AllowedValuesValidator()
        ]
    
    def validate(self, df: pd.DataFrame, rules: Dict[str, Dict[str, Any]], 
                 instrument_name: str) -> Tuple[List[Dict[str, Any]], pd.DataFrame]:
        """
        Perform bulk vectorized checks for simple validation rules.
        
        This function handles type, min/max, regex, and allowed value checks
        in a vectorized manner for performance. It skips fields that require
        more complex logic (like 'compatibility' or 'temporalrules').
        
        Args:
            df: The DataFrame to validate.
            rules: The validation rules for the instrument.
            instrument_name: The name of the instrument being validated.
            
        Returns:
            A tuple containing a list of error dictionaries and a DataFrame
            with rows that passed the simple checks.
        """
        overall_result = ValidationResult()
        overall_result.valid_mask = pd.Series(True, index=df.index)
        
        for field, config in rules.items():
            # Skip dynamic fields altogether here
            if 'compatibility' in config or 'temporalrules' in config:
                continue
            if field not in df.columns:
                continue
            
            # Run all validators for this field
            field_result = ValidationResult()
            field_result.valid_mask = pd.Series(True, index=df.index)
            
            for validator in self.validators:
                validator_result = validator.validate(df, field, config, instrument_name)
                field_result.combine_with(validator_result)
            
            # Combine field results with overall results
            overall_result.combine_with(field_result)
        
        # Return errors and valid rows
        return overall_result.errors, df.loc[overall_result.valid_mask].reset_index(drop=True)


# =============================================================================
# EXISTING HELPER FUNCTIONS
# =============================================================================

def load_json_rules_for_instrument(instrument_name: str) -> Dict[str, Any]:
    """
    Loads all JSON validation rules for a given instrument.

    It looks up the required JSON files from the `instrument_json_mapping`
    in the configuration and merges them into a single dictionary.

    Args:
        instrument_name: The name of the instrument.

    Returns:
        A dictionary containing the combined validation rules.
    """
    config = get_config()
    json_rules_path = Path(config.json_rules_path)
    
    # Get the list of JSON files for the instrument
    rule_files = instrument_json_mapping.get(instrument_name, [])
    if not rule_files:
        logger.warning(f"No JSON rule files found for instrument: {instrument_name}")
        return {}

    # Load and merge all rules from the files
    combined_rules = {}
    for file_name in rule_files:
        file_path = json_rules_path / file_name
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    rules = json.load(f)
                    combined_rules.update(rules)
            except json.JSONDecodeError:
                logger.error(f"Could not decode JSON from {file_path}", exc_info=True)
            except Exception as e:
                logger.error(f"Error reading rule file {file_path}: {e}", exc_info=True)
        else:
            logger.warning(f"JSON rule file not found: {file_path}")

    return combined_rules


def get_variables_for_instrument(instrument_name: str, rules_cache: Dict[str, Any]) -> List[str]:
    """
    Retrieves the list of variables for a given instrument from the rules cache.

    This function handles both standard instruments and those with dynamic rule
    selection by consolidating variables from all possible rule variants.

    Args:
        instrument_name: The name of the instrument.
        rules_cache: A cache of loaded JSON rules for all instruments.

    Returns:
        A list of variable names associated with the instrument.
    """
    if is_dynamic_rule_instrument(instrument_name):
        # For dynamic rule instruments, combine variables from all rule variants
        rule_map = load_dynamic_rules_for_instrument(instrument_name)
        all_variables = set()
        for variant_rules in rule_map.values():
            all_variables.update(variant_rules.keys())
        return list(all_variables)
    else:
        # For standard instruments, get variables from the cached rules
        return list(rules_cache.get(instrument_name, {}).keys())


def debug_variable_mapping(
    data_df: pd.DataFrame,
    instrument_list: List[str],
    rules_cache: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Debug helper to analyze variable mapping between data and JSON rules.

    This function compares the columns in the DataFrame with the variables
    defined in the JSON rules for a list of instruments. It helps identify
    missing variables and columns that are present in the data but not
    defined in any rule.

    Args:
        data_df: The DataFrame containing the data to analyze.
        instrument_list: A list of instrument names to check.
        rules_cache: A cache of loaded JSON rules.

    Returns:
        A dictionary with detailed diagnostic information.
    """
    debug_info = {
        'data_columns': list(data_df.columns),
        'instruments': {},
        'missing_variables': {},
        'orphaned_columns': [],
        'mapping_summary': {}
    }
    
    # Analyze each instrument
    all_rule_variables = set()
    for instrument in instrument_list:
        rules = rules_cache.get(instrument, {})
        
        if is_dynamic_rule_instrument(instrument):
            # Special handling for dynamic rule instruments
            dynamic_rules = load_dynamic_rules_for_instrument(instrument)
            rule_vars = set()
            for variant_rules in dynamic_rules.values():
                rule_vars.update(variant_rules.keys())
        else:
            rule_vars = set(rules.keys())
        
        all_rule_variables.update(rule_vars)
        
        # Check which rule variables are present in data
        data_vars = [var for var in rule_vars if var in data_df.columns]
        missing_vars = [var for var in rule_vars if var not in data_df.columns]
        
        debug_info['instruments'][instrument] = {
            'rule_variables': list(rule_vars),
            'data_variables': data_vars,
            'missing_variables': missing_vars,
            'coverage_percentage': len(data_vars) / len(rule_vars) * 100 if rule_vars else 0
        }
        debug_info['missing_variables'][instrument] = missing_vars
    
    # Find orphaned columns (in data but not in any rules)
    data_cols = set(data_df.columns)
    core_cols = set(get_core_columns())
    completion_cols = set(get_completion_columns())
    special_cols = set(get_special_columns())
    
    expected_cols = all_rule_variables | core_cols | completion_cols | special_cols
    debug_info['orphaned_columns'] = list(data_cols - expected_cols)
    
    # Summary statistics
    debug_info['mapping_summary'] = {
        'total_data_columns': len(data_df.columns),
        'total_rule_variables': len(all_rule_variables),
        'matched_variables': len(all_rule_variables & data_cols),
        'orphaned_columns_count': len(debug_info['orphaned_columns']),
        'overall_coverage': len(all_rule_variables & data_cols) / len(all_rule_variables) * 100 if all_rule_variables else 0
    }
    
    return debug_info

# ─── Helpers ───────────────────────────────────────────────────────────────────

def _preprocess_cast_types(
    df: pd.DataFrame,
    rules: Dict[str, Dict[str, Any]]
) -> pd.DataFrame:
    """
    Bulk-cast columns according to schema types.

    - integer → pandas Int64 (nullable int)
    - float   → float64
    - date/datetime → datetime64[ns]

    Args:
        df: The input DataFrame.
        rules: The validation rules dictionary for the instrument.

    Returns:
        A new DataFrame with columns cast to their specified types.
    """
    out = df.copy()
    for field, cfg in rules.items():
        dtype = cfg.get("type")
        if dtype == "integer" and field in out:
            out[field] = pd.to_numeric(out[field], errors="coerce").astype("Int64")
        elif dtype == "float" and field in out:
            out[field] = pd.to_numeric(out[field], errors="coerce")
        elif dtype in ("date", "datetime") and field in out:
            out[field] = pd.to_datetime(out[field], errors="coerce")
    return out

def _run_vectorized_simple_checks(
    df: pd.DataFrame,
    rules: Dict[str, Dict[str, Any]],
    instrument_name: str
) -> Tuple[List[Dict[str, Any]], pd.DataFrame]:
    """
    Legacy wrapper for backward compatibility.
    
    This function now uses the new SimpleChecksValidator class internally.
    """
    validator = SimpleChecksValidator()
    return validator.validate(df, rules, instrument_name)

# ─── Validation Helper ──────────────────────────────────────────────────

def process_dynamic_validation(
    df: pd.DataFrame,
    instrument_name: str
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Handles dynamic rule selection for instruments with variable-based rules.

    This function identifies the correct set of validation rules to apply
    based on a 'discriminant variable' in the data. It then runs simple
    vectorized checks for each rule variant.

    Args:
        df: DataFrame containing the data to validate.
        instrument_name: Name of the dynamic-rule instrument.

    Returns:
        A tuple containing the filtered DataFrame (for complex checks) and
        a list of errors found during simple checks.
    """
    if not is_dynamic_rule_instrument(instrument_name):
        raise ValueError(f"Instrument '{instrument_name}' is not configured for dynamic rule selection")
    
    errors = []
    discriminant_var = get_discriminant_variable(instrument_name)
    rule_mappings = get_rule_mappings(instrument_name)
    
    # Check if discriminant variable exists in the DataFrame
    if discriminant_var not in df.columns:
        logger.warning(f"Discriminant variable '{discriminant_var}' not found for instrument {instrument_name}.")
        # If the discriminant is missing, we cannot proceed with validation for this instrument.
        # Return the original DataFrame and no errors, assuming it will be handled downstream.
        return df, []

    # Load all rule variants for this instrument
    rule_map = load_dynamic_rules_for_instrument(instrument_name)
    
    # Process each variant separately
    variant_dataframes = []
    for variant in rule_mappings.keys():
        variant_df = df[df[discriminant_var].str.upper() == variant.upper()]
        if len(variant_df) > 0:
            variant_errors, processed_df = _run_vectorized_simple_checks(
                variant_df, rule_map[variant], instrument_name
            )
            errors.extend(variant_errors)
            variant_dataframes.append(processed_df)
    
    # Combine all variant dataframes
    if variant_dataframes:
        df_combined = pd.concat(variant_dataframes, ignore_index=True)
    else:
        df_combined = pd.DataFrame()
    
    return df_combined, errors


# ─── ETL-Optimized Processing ──────────────────────────────────────────────────


def process_dynamic_instrument_data(
    df: pd.DataFrame,
    instrument: str,
    rules_cache: Dict[str, Any],
    primary_key_field: str,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Helper to process data for a dynamic rule instrument in the ETL pipeline.

    This function extracts the relevant columns and rows for a dynamic instrument,
    considering all possible variables from its different rule variants.

    Args:
        df: The source DataFrame.
        instrument: The name of the dynamic instrument.
        rules_cache: A cache of loaded JSON rules.
        primary_key_field: The name of the primary key field.

    Returns:
        A tuple containing:
        - A filtered DataFrame with only relevant data for the instrument.
        - A list of all variables associated with the instrument.
    """
    if not is_dynamic_rule_instrument(instrument):
        raise ValueError(
            f"Instrument '{instrument}' is not configured for dynamic rule selection"
        )

    # Load all rule variants for this instrument
    rule_map = load_dynamic_rules_for_instrument(instrument)
    discriminant_var = get_discriminant_variable(instrument)

    # Get all variables from all rule variants
    all_variables = set()
    for variant_rules in rule_map.values():
        all_variables.update(variant_rules.keys())
    instrument_variables = list(all_variables)

    # Build column list
    core_cols = get_core_columns()
    relevant_cols = [col for col in core_cols if col in df.columns]

    # Add instrument variables
    for var in instrument_variables:
        if var in df.columns:
            relevant_cols.append(var)
    
    # Add completion columns
    completion_cols = [col for col in get_completion_columns() if col in df.columns]
    relevant_cols.extend(completion_cols)
    
    # Add discriminant variable
    if discriminant_var in df.columns:
        relevant_cols.append(discriminant_var)
    
    # Remove duplicates and ensure columns exist
    relevant_cols = list(set([col for col in relevant_cols if col in df.columns]))
    
    # Filter DataFrame
    instrument_df = pd.DataFrame()
    if relevant_cols:
        instrument_df = df[relevant_cols].copy()
        non_core_cols = [col for col in relevant_cols if col not in core_cols and not col.endswith('_complete')]
        if non_core_cols:
            has_data_mask = instrument_df[non_core_cols].notna().any(axis=1)
            instrument_df = instrument_df[has_data_mask].reset_index(drop=True)
    
    return instrument_df, instrument_variables

# ─── ETL Helper Functions ──────────────────────────────────────────────────────

def load_rules_for_instruments(instrument_list: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Loads JSON rules for a list of instruments into a cache.

    Args:
        instrument_list: A list of instrument names.

    Returns:
        A dictionary (cache) mapping instrument names to their validation rules.
    """
    rules_cache = {}
    for instrument in instrument_list:
        if instrument not in rules_cache:
            rules_cache[instrument] = load_json_rules_for_instrument(instrument)
    return rules_cache

def build_variable_maps(
    instrument_list: List[str],
    rules_cache: Dict[str, Any]
) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Builds mappings between variables and instruments.

    Args:
        instrument_list: A list of instrument names.
        rules_cache: A cache of loaded JSON rules.

    Returns:
        A tuple of two dictionaries:
        - variable_to_instrument_map: Maps each variable to its instrument name.
        - instrument_variable_map: Maps each instrument to a list of its variables.
    """
    variable_to_instrument_map = {}
    instrument_variable_map = {}
    for instrument in instrument_list:
        rules = rules_cache.get(instrument, {})
        if not rules:
            logger.warning(f"No rules found for instrument '{instrument}' in cache. Skipping variable mapping.")
            instrument_variable_map[instrument] = []
            continue

        if is_dynamic_rule_instrument(instrument):
            # For dynamic instruments, get all possible variables
            dynamic_rule_map = load_dynamic_rules_for_instrument(instrument)
            all_dynamic_vars = set()
            for variant_rules in dynamic_rule_map.values():
                all_dynamic_vars.update(variant_rules.keys())
            instrument_variables = list(all_dynamic_vars)
        else:
            instrument_variables = list(rules.keys())

        for var in instrument_variables:
            variable_to_instrument_map[var] = instrument
        instrument_variable_map[instrument] = instrument_variables
        logger.debug(f"Mapped {len(instrument_variables)} variables to instrument '{instrument}'.")

    return variable_to_instrument_map, instrument_variable_map


def prepare_instrument_data_cache(
    data_df: pd.DataFrame,
    instrument_list: List[str],
    instrument_variable_map: Dict[str, List[str]],
    rules_cache: Dict[str, Any],
    primary_key_field: str,
) -> Dict[str, pd.DataFrame]:
    """
    Prepares a cache of DataFrames, one for each instrument.

    Each DataFrame is filtered to contain only the columns relevant to that
    instrument, improving memory usage and processing speed.

    Args:
        data_df: The main DataFrame containing all data.
        instrument_list: The list of instruments to process.
        instrument_variable_map: A map of instruments to their variables.
        rules_cache: A cache of loaded JSON rules (for dynamic instruments).
        primary_key_field: The name of the primary key field.

    Returns:
        A dictionary mapping each instrument name to its filtered DataFrame.
    """
    instrument_data_cache = {}
    core_cols = get_core_columns()
    for instrument in instrument_list:
        if is_dynamic_rule_instrument(instrument):
            instrument_df, _ = process_dynamic_instrument_data(
                data_df, instrument, rules_cache, primary_key_field
            )
            instrument_data_cache[instrument] = instrument_df
            logger.debug(
                f"Prepared {len(instrument_df)} records for instrument '{instrument}' with {len(instrument_df.columns) if not instrument_df.empty else 0} columns"
            )
            logger.debug(
                f"Variables for {instrument}: {instrument_variable_map[instrument][:10]}{'...' if len(instrument_variable_map[instrument]) > 10 else ''}"
            )
            continue
        relevant_cols = [col for col in core_cols if col in data_df.columns]
        instrument_vars = instrument_variable_map.get(instrument, [])
        for var in instrument_vars:
            if var in data_df.columns:
                relevant_cols.append(var)
        completion_cols = [col for col in get_completion_columns() if col in data_df.columns]
        relevant_cols.extend(completion_cols)
        relevant_cols = list(set([col for col in relevant_cols if col in data_df.columns]))
        if relevant_cols:
            instrument_df = data_df[relevant_cols].copy()
            non_core_cols = [col for col in relevant_cols if col not in core_cols and not col.endswith('_complete')]
            if non_core_cols:
                has_data_mask = instrument_df[non_core_cols].notna().any(axis=1)
                instrument_df = instrument_df[has_data_mask].reset_index(drop=True)
            instrument_data_cache[instrument] = instrument_df
            logger.debug(f"Prepared {len(instrument_df)} records for instrument '{instrument}' with {len(relevant_cols)} columns")
            logger.debug(f"Variables for {instrument}: {instrument_vars[:10]}{'...' if len(instrument_vars) > 10 else ''}")
        else:
            logger.warning(f"No relevant columns found for instrument '{instrument}'")
            instrument_data_cache[instrument] = pd.DataFrame()
    return instrument_data_cache

def build_complete_visits_df(
    data_df: pd.DataFrame,
    instrument_list: List[str]
) -> Tuple[pd.DataFrame, List[Tuple[str, str]]]:
    """
    Identifies and creates a DataFrame of truly complete visits.

    A visit (a unique primary_key-event combination) is considered complete if all
    expected instruments for that visit are present and marked as complete ('2').

    Args:
        data_df: The DataFrame containing all data.
        instrument_list: The list of all instruments to check for completion.

    Returns:
        A tuple containing:
        - A DataFrame summarizing the complete visits.
        - A list of tuples, each with (primary_key, redcap_event_name) for a complete visit.
    """
    if data_df.empty:
        logger.warning("Cannot build complete visits dataset from empty DataFrame.")
        return pd.DataFrame(), []

    # List of completion columns to check, excluding form_header as it's not a clinical instrument
    completion_cols = [f"{inst}_complete" for inst in instrument_list if inst.lower() != "form_header"]
    
    # Ensure all required completion columns exist in the DataFrame for the check
    df_copy = data_df.copy()
    for col in completion_cols:
        if col not in df_copy.columns:
            logger.warning(f"Completion column '{col}' not found in data. Assuming instrument is not complete for all records.")
            df_copy[col] = '0'  # Default to incomplete if the column is missing

    # Convert all completion columns to string to handle mixed types (e.g., 2.0, '2', 2)
    for col in completion_cols:
        df_copy[col] = df_copy[col].astype(str)

    # For each visit (primary_key + event), check if ALL records have ALL instruments marked as complete
    # This means every single row for a visit must have all completion columns equal to '2'
    complete_visits = []
    primary_key_field = get_config().primary_key_field
    
    for (ptid, event), group in df_copy.groupby([primary_key_field, 'redcap_event_name']):
        # Check if ALL rows in this group have ALL completion columns equal to '2'
        all_records_complete = True
        for _, row in group.iterrows():
            for col in completion_cols:
                if str(row[col]) != '2':
                    all_records_complete = False
                    break
            if not all_records_complete:
                break
        
        if all_records_complete:
            complete_visits.append((ptid, event))

    if not complete_visits:
        logger.debug("ETL identified 0 truly complete visits.")
        return pd.DataFrame(), []

    # Create the summary DataFrame
    complete_visits_summary = pd.DataFrame(complete_visits, columns=[primary_key_field, 'redcap_event_name'])
    
    # Create the final report DataFrame
    report_df = complete_visits_summary.copy()
    report_df['complete_instruments_count'] = len(completion_cols)
    report_df['completion_status'] = 'All Complete'

    # Get the list of (primary_key, event) tuples for downstream filtering
    complete_visits_tuples = list(complete_visits_summary[[primary_key_field, 'redcap_event_name']].itertuples(index=False, name=None))

    logger.debug(f"ETL identified {len(report_df)} truly complete visits.")
    
    return report_df, complete_visits_tuples


def build_detailed_validation_logs(
    df: pd.DataFrame, instrument: str, primary_key_field: str
) -> List[Dict[str, Any]]:
    """
    Builds detailed logs for each record of an instrument based on completeness.

    This function captures the completeness status of the specific instrument
    being processed for each record and determines a Pass/Fail status based on it.

    Args:
        df: The DataFrame for a specific instrument.
        instrument: The name of the instrument.
        primary_key_field: The name of the primary key field.

    Returns:
        A list of dictionaries, each representing a log entry for a record.
    """
    logs = []
    instrument_complete_col = f"{instrument}_complete"

    for _, record_row in df.iterrows():
        pk_val = record_row.get(primary_key_field, "N/A")
        event = record_row.get("redcap_event_name", "N/A")
        
        pass_status = "Pass"
        error_msg = np.nan
        
        if instrument_complete_col in record_row:
            # Check if the instrument is marked as complete ('2')
            is_complete = str(record_row.get(instrument_complete_col)) == "2"
            completeness_status = "Complete" if is_complete else "Incomplete"
            target_variable = instrument_complete_col
            if not is_complete:
                pass_status = "Fail"
                error_msg = f"Instrument not marked as complete. Value is '{record_row.get(instrument_complete_col)}'."
        else:
            # If no completeness variable exists for this instrument
            completeness_status = "No completeness field"
            target_variable = "N/A"
            pass_status = "Fail"
            error_msg = "Instrument completeness variable not found in data."

        logs.append(
            {
                primary_key_field: pk_val,
                "redcap_event_name": event,
                "instrument_name": instrument,
                "target_variable": target_variable,
                "completeness_status": completeness_status,
                "processing_status": "Processed",
                "pass_fail": pass_status,
                "error": error_msg,
            }
        )

    return logs