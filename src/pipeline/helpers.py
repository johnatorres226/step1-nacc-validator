"""
This module provides helper functions for the QC pipeline.

It includes utilities for:
- Loading and managing JSON validation rules.
- Mapping variables to instruments.
- Handling dynamic rule selection for complex instruments.
- Preprocessing data for validation.
- Generating detailed logs and reports.

REFACTORING NOTE: As of the validation standardization refactor, the simple checks
validation system has been completely removed. The following functions are deprecated:
- process_dynamic_validation(): Use the unified validation in report_pipeline.validate_data()
- _run_vectorized_simple_checks(): Use the standardized per-record validation approach

The validation classes (ValidationResult, BaseValidator, RangeValidator, etc.) have 
been removed as part of the cleanup. All validation now uses the unified approach
through QualityCheck.validate_record().

These deprecated functions are maintained for backward compatibility but will be 
removed in a future version.
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

logger = get_logger(__name__)


# =============================================================================
# DYNAMIC INSTRUMENT PROCESSOR (NEW CONSOLIDATED APPROACH)
# =============================================================================

class DynamicInstrumentProcessor:
    """
    Consolidated processor for dynamic rule instruments.
    
    This class centralizes all dynamic instrument processing logic that was
    previously scattered across multiple functions, providing a unified
    interface for handling instruments with variable-based rule selection.
    """
    
    def __init__(self, instrument_name: str):
        """
        Initialize processor for a dynamic instrument.
        
        Args:
            instrument_name: Name of the dynamic instrument to process
            
        Raises:
            ValueError: If instrument is not configured for dynamic rule selection
        """
        if not is_dynamic_rule_instrument(instrument_name):
            raise ValueError(
                f"Instrument '{instrument_name}' is not configured for dynamic rule selection"
            )
        
        self.instrument_name = instrument_name
        self.discriminant_var = get_discriminant_variable(instrument_name)
        self.rule_mappings = get_rule_mappings(instrument_name)
        self._rule_cache = None
        self._variables_cache = None
    
    def get_all_variables(self) -> List[str]:
        """
        Get all possible variables across all rule variants for this instrument.
        
        Returns:
            List of all variable names from all rule variants
        """
        if self._variables_cache is None:
            rule_map = self._get_rule_map()
            all_variables = set()
            for variant_rules in rule_map.values():
                all_variables.update(variant_rules.keys())
            self._variables_cache = list(all_variables)
        
        return self._variables_cache
    
    def get_rules_for_variant(self, variant: str) -> Dict[str, Any]:
        """
        Get validation rules for a specific variant.
        
        Args:
            variant: The variant name (e.g., 'C2', 'C2T')
            
        Returns:
            Dictionary of validation rules for the variant
        """
        rule_map = self._get_rule_map()
        return rule_map.get(variant.upper(), {})
    
    def prepare_data(self, df: pd.DataFrame, primary_key_field: str) -> Tuple[pd.DataFrame, List[str]]:
        """
        Prepare data for dynamic instrument processing.
        
        This method extracts relevant columns and rows for the dynamic instrument,
        considering all possible variables from different rule variants.
        
        Args:
            df: Source DataFrame containing the data
            primary_key_field: Name of the primary key field
            
        Returns:
            Tuple of (filtered DataFrame, list of all instrument variables)
        """
        # Get all variables from all rule variants
        instrument_variables = self.get_all_variables()
        
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
        if self.discriminant_var in df.columns:
            relevant_cols.append(self.discriminant_var)
        
        # Remove duplicates and ensure columns exist
        relevant_cols = list(set([col for col in relevant_cols if col in df.columns]))
        
        # Filter DataFrame
        instrument_df = pd.DataFrame()
        if relevant_cols:
            instrument_df = df[relevant_cols].copy()
            non_core_cols = [col for col in relevant_cols 
                           if col not in core_cols and not col.endswith('_complete')]
            if non_core_cols:
                has_data_mask = instrument_df[non_core_cols].notna().any(axis=1)
                instrument_df = instrument_df[has_data_mask].reset_index(drop=True)
        
        return instrument_df, instrument_variables
    
    def get_variants_in_data(self, df: pd.DataFrame) -> List[str]:
        """
        Get list of variants actually present in the data.
        
        Args:
            df: DataFrame to analyze
            
        Returns:
            List of variant values found in the discriminant variable
        """
        if self.discriminant_var not in df.columns:
            logger.warning(f"Discriminant variable '{self.discriminant_var}' not found in data")
            return []
        
        variants = df[self.discriminant_var].dropna().str.upper().unique().tolist()
        return [v for v in variants if v in self.rule_mappings]
    
    def _get_rule_map(self) -> Dict[str, Dict[str, Any]]:
        """Load and cache rule map for this instrument."""
        if self._rule_cache is None:
            self._rule_cache = load_dynamic_rules_for_instrument(self.instrument_name)
        return self._rule_cache


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
        # Use the new consolidated processor for dynamic instruments
        processor = DynamicInstrumentProcessor(instrument_name)
        return processor.get_all_variables()
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
            # Use the new consolidated processor for dynamic instruments
            processor = DynamicInstrumentProcessor(instrument)
            rule_vars = set(processor.get_all_variables())
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
    DEPRECATED: Legacy wrapper for backward compatibility.
    
    This function is deprecated as of the validation standardization refactor.
    The validation process now uses a unified per-record approach through
    QualityCheck.validate_record() instead of separate vectorized checks.
    
    Warning:
        This function will be removed in version 2.0.0 (target: Q1 2026).
        Use the standardized validation process in report_pipeline.validate_data() instead.
        
    Note:
        This function now returns empty results as the simple checks validation
        system has been removed in favor of the unified validation approach.
    """
    import warnings
    warnings.warn(
        "_run_vectorized_simple_checks is deprecated and will be removed in "
        "version 2.0.0 (target: Q1 2026). Use the standardized validation "
        "process in report_pipeline.validate_data() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Return empty results as this function is fully deprecated
    return [], df.copy()

# ─── Validation Helper ──────────────────────────────────────────────────

def process_dynamic_validation(
    df: pd.DataFrame,
    instrument_name: str
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    DEPRECATED: Handles dynamic rule selection for instruments with variable-based rules.

    This function is deprecated as of the validation standardization refactor.
    The validation process now uses a unified per-record approach that handles
    both dynamic and standard instruments consistently through the same pathway.

    This function identified the correct set of validation rules to apply
    based on a 'discriminant variable' in the data, then ran simple
    vectorized checks for each rule variant.

    Warning:
        This function will be removed in version 2.0.0 (target: Q1 2026).
        The new standardized validation process in report_pipeline.validate_data() 
        handles dynamic instruments automatically through _get_schema_and_rules_for_record().

    Args:
        df: DataFrame containing the data to validate.
        instrument_name: Name of the dynamic-rule instrument.

    Returns:
        A tuple containing the filtered DataFrame (for complex checks) and
        a list of errors found during simple checks.
    """
    import warnings
    warnings.warn(
        "process_dynamic_validation is deprecated and will be removed in "
        "version 2.0.0 (target: Q1 2026). The new standardized validation "
        "process handles dynamic instruments automatically.",
        DeprecationWarning,
        stacklevel=2
    )
    
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
    
    # Process each variant separately - but skip validation since it's deprecated
    variant_dataframes = []
    for variant in rule_mappings.keys():
        variant_df = df[df[discriminant_var].str.upper() == variant.upper()]
        if len(variant_df) > 0:
            # No longer perform simple checks - just collect the data
            variant_dataframes.append(variant_df)
    
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

    This function now uses the consolidated DynamicInstrumentProcessor for
    improved maintainability and consistency.

    Args:
        df: The source DataFrame.
        instrument: The name of the dynamic instrument.
        rules_cache: A cache of loaded JSON rules (not used for dynamic instruments).
        primary_key_field: The name of the primary key field.

    Returns:
        A tuple containing:
        - A filtered DataFrame with only relevant data for the instrument.
        - A list of all variables associated with the instrument.
    """
    # Use the new consolidated processor
    processor = DynamicInstrumentProcessor(instrument)
    return processor.prepare_data(df, primary_key_field)

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
            # Use the new consolidated processor for dynamic instruments
            processor = DynamicInstrumentProcessor(instrument)
            instrument_variables = processor.get_all_variables()
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

    This function now uses the strategy pattern through InstrumentDataCache
    for improved maintainability and reduced complexity.

    Args:
        data_df: The main DataFrame containing all data.
        instrument_list: The list of instruments to process.
        instrument_variable_map: A map of instruments to their variables (legacy parameter).
        rules_cache: A cache of loaded JSON rules.
        primary_key_field: The name of the primary key field.

    Returns:
        A dictionary mapping each instrument name to its filtered DataFrame.
    """
    # Import here to avoid circular dependencies
    from .context import ProcessingContext
    from .instrument_processors import InstrumentDataCache
    from .config_manager import get_config
    
    # Create processing context
    context = ProcessingContext(
        data_df=data_df,
        instrument_list=instrument_list,
        rules_cache=rules_cache,
        primary_key_field=primary_key_field,
        config=get_config()
    )
    
    # Use strategy pattern through InstrumentDataCache
    cache = InstrumentDataCache(context)
    return cache.prepare_all()

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