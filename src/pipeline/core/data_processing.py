"""
Core data processing functions for the QC pipeline.

This module contains all data preparation, transformation, and processing functions
that were previously in helpers.py, but now broken down into smaller, single-purpose
functions following SOLID principles.
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from ..config.config_manager import get_config, is_dynamic_rule_instrument
from ..logging.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# CORE ERRORS
# =============================================================================


class DataProcessingError(Exception):
    """Error during data processing step."""


class ValidationError(Exception):
    """Error during validation step."""


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class CompleteVisitsData:
    """Data model for complete visits processing results."""

    summary_dataframe: pd.DataFrame
    complete_visits_tuples: list[tuple[str, str]]
    total_visits_processed: int
    complete_visits_count: int


@dataclass
class ValidationLogsData:
    """Data model for validation logs."""

    log_entries: list[dict[str, Any]]
    total_records_processed: int
    pass_count: int
    fail_count: int


# =============================================================================
# INSTRUMENT DETECTION AND VARIABLE EXTRACTION
# =============================================================================


def is_dynamic_instrument(instrument_name: str) -> bool:
    """
    Determine if instrument uses dynamic rules.

    Args:
        instrument_name: Name of the instrument to check.

    Returns:
        True if the instrument uses dynamic rules, False otherwise.
    """
    return is_dynamic_rule_instrument(instrument_name)


def extract_variables_from_rules(rules: dict[str, Any]) -> list[str]:
    """
    Extract variable names from rule dictionary.

    Args:
        rules: Dictionary of validation rules.

    Returns:
        List of variable names found in the rules.
    """
    return list(rules.keys())


def extract_variables_from_dynamic_instrument(instrument_name: str) -> list[str]:
    """
    Extract variables from dynamic instrument processor.

    Args:
        instrument_name: Name of the dynamic instrument.

    Returns:
        List of all variables for the dynamic instrument.
    """
    # Import here to avoid circular dependencies
    from ..processors.instrument_processors import DynamicInstrumentProcessor

    processor = DynamicInstrumentProcessor(instrument_name)
    return processor.get_all_variables()


def get_variables_for_instrument(instrument_name: str, rules_cache: dict[str, Any]) -> list[str]:
    """
    Orchestrate variable extraction based on instrument type.

    Args:
        instrument_name: The name of the instrument.
        rules_cache: A cache of loaded JSON rules for all instruments.

    Returns:
        A list of variable names associated with the instrument.
    """
    if is_dynamic_instrument(instrument_name):
        return extract_variables_from_dynamic_instrument(instrument_name)
    rules = rules_cache.get(instrument_name, {})
    return extract_variables_from_rules(rules)


# =============================================================================
# TYPE CASTING FUNCTIONS
# =============================================================================


def detect_column_type(field_name: str, rules: dict[str, Any]) -> str | None:
    """
    Detect the expected type for a column from rules.

    Args:
        field_name: Name of the field/column.
        rules: Validation rules dictionary.

    Returns:
        The detected type string, or None if not found.
    """
    field_config = rules.get(field_name, {})
    return field_config.get("type")


def preprocess_cast_types(df: pd.DataFrame, rules: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """
    Cast dataframe columns according to schema types.

    Bulk-cast columns according to schema types:
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
        if field not in out.columns:
            continue

        dtype = detect_column_type(field, {field: cfg})

        try:
            if dtype == "integer":
                out[field] = pd.to_numeric(out[field], errors="coerce").astype("Int64")
            elif dtype == "float":
                out[field] = pd.to_numeric(out[field], errors="coerce")
            elif dtype in ("date", "datetime"):
                out[field] = pd.to_datetime(out[field], errors="coerce")
        except Exception as e:
            logger.warning(f"Failed to cast field '{field}' to {dtype}: {e}")

    return out


# =============================================================================
# VARIABLE MAPPING FUNCTIONS
# =============================================================================


def create_variable_to_instrument_map(
    instrument_list: list[str], rules_cache: dict[str, Any]
) -> dict[str, str]:
    """
    Create mapping from variables to their instruments.

    Args:
        instrument_list: List of instrument names.
        rules_cache: Cache of loaded JSON rules.

    Returns:
        Dictionary mapping variable names to instrument names.
    """
    variable_to_instrument_map = {}

    for instrument in instrument_list:
        variables = get_variables_for_instrument(instrument, rules_cache)
        for var in variables:
            variable_to_instrument_map[var] = instrument

    return variable_to_instrument_map


def create_instrument_to_variables_map(
    instrument_list: list[str], rules_cache: dict[str, Any]
) -> dict[str, list[str]]:
    """
    Create mapping from instruments to their variables.

    Args:
        instrument_list: List of instrument names.
        rules_cache: Cache of loaded JSON rules.

    Returns:
        Dictionary mapping instrument names to their variable lists.
    """
    instrument_variable_map = {}

    for instrument in instrument_list:
        variables = get_variables_for_instrument(instrument, rules_cache)
        instrument_variable_map[instrument] = variables

        if variables:
            logger.debug(f"Mapped {len(variables)} variables to instrument '{instrument}'.")
        else:
            logger.warning(f"No variables found for instrument '{instrument}'.")

    return instrument_variable_map


def build_variable_maps(
    instrument_list: list[str], rules_cache: dict[str, Any]
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """
    Build both variable mapping types.

    Args:
        instrument_list: A list of instrument names.
        rules_cache: A cache of loaded JSON rules.

    Returns:
        A tuple of two dictionaries:
        - variable_to_instrument_map: Maps each variable to its instrument name.
        - instrument_variable_map: Maps each instrument to a list of its variables.
    """
    try:
        variable_to_instrument_map = create_variable_to_instrument_map(instrument_list, rules_cache)
        instrument_variable_map = create_instrument_to_variables_map(instrument_list, rules_cache)

        return variable_to_instrument_map, instrument_variable_map

    except Exception as e:
        logger.error(f"Failed to build variable maps: {e}")
        raise DataProcessingError(f"Variable mapping failed: {e}") from e


# =============================================================================
# CONTEXT CREATION AND CACHE MANAGEMENT
# =============================================================================


def prepare_instrument_data_cache(
    data_df: pd.DataFrame,
    instrument_list: list[str],
    instrument_variable_map: dict[str, list[str]],
    rules_cache: dict[str, Any],
    primary_key_field: str,
) -> dict[str, pd.DataFrame]:
    """
    Prepare cached dataframes for all instruments.

    Args:
        data_df: The main DataFrame containing all data.
        instrument_list: The list of instruments to process.
        instrument_variable_map: A map of instruments to their variables (not used).
        rules_cache: A cache of loaded JSON rules.
        primary_key_field: The name of the primary key field.

    Returns:
        A dictionary mapping each instrument name to its filtered DataFrame.
    """
    from ..processors.instrument_processors import prepare_instrument_data

    try:
        instrument_cache = {}
        
        for instrument in instrument_list:
            instrument_df, variables = prepare_instrument_data(
                instrument, data_df, rules_cache, primary_key_field
            )
            instrument_cache[instrument] = instrument_df
            
            logger.debug(
                "Prepared %d records for instrument '%s' with %d columns",
                len(instrument_df),
                instrument,
                len(instrument_df.columns) if not instrument_df.empty else 0,
            )
        
        return instrument_cache

    except Exception as e:
        logger.error(f"Failed to prepare instrument data cache: {e}")
        raise DataProcessingError(f"Instrument cache preparation failed: {e}") from e



