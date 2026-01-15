"""
Instrument processors for data preparation.

This module provides functions for preparing instrument data, handling both
standard instruments and dynamic rule instruments.
"""

from typing import Any

import pandas as pd

from pipeline.config.config_manager import (
    get_completion_columns,
    get_core_columns,
    get_discriminant_variable,
    get_rule_mappings,
    is_dynamic_rule_instrument,
)
from pipeline.io.rules import load_dynamic_rules_for_instrument
from pipeline.logging.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# DYNAMIC INSTRUMENT PROCESSOR
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
            _msg = "Instrument '%s' is not configured for dynamic rule selection"
            raise ValueError(_msg % instrument_name)

        self.instrument_name = instrument_name
        self.discriminant_var = get_discriminant_variable(instrument_name)
        self.rule_mappings = get_rule_mappings(instrument_name)
        self._rule_cache = None
        self._variables_cache = None

    def get_all_variables(self) -> list[str]:
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

    def get_rules_for_variant(self, variant: str) -> dict[str, Any]:
        """
        Get validation rules for a specific variant.

        Args:
            variant: The variant name (e.g., 'C2', 'C2T')

        Returns:
            Dictionary of validation rules for the variant
        """
        rule_map = self._get_rule_map()
        return rule_map.get(variant.upper(), {})

    def prepare_data(
        self, df: pd.DataFrame, primary_key_field: str
    ) -> tuple[pd.DataFrame, list[str]]:
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

        # Filter DataFrame
        instrument_df = pd.DataFrame()
        if relevant_cols:
            instrument_df = df[relevant_cols].copy()
            non_core_cols = [
                col
                for col in relevant_cols
                if col not in core_cols and not col.endswith("_complete")
            ]
            if non_core_cols:
                has_data_mask = instrument_df[non_core_cols].notna().any(axis=1)
                instrument_df = instrument_df[has_data_mask].reset_index(drop=True)

        return instrument_df, instrument_variables

    def get_variants_in_data(self, df: pd.DataFrame) -> list[str]:
        """
        Get list of variants actually present in the data.

        Args:
            df: DataFrame to analyze

        Returns:
            List of variant values found in the discriminant variable
        """
        if self.discriminant_var not in df.columns:
            logger.warning("Discriminant variable '%s' not found in data", self.discriminant_var)
            return []

        variants = df[self.discriminant_var].dropna().str.upper().unique().tolist()
        return [v for v in variants if v in self.rule_mappings]

    def _get_rule_map(self) -> dict[str, dict[str, Any]]:
        """Load and cache rule map for this instrument."""
        if self._rule_cache is None:
            self._rule_cache = load_dynamic_rules_for_instrument(self.instrument_name)
        return self._rule_cache


# =============================================================================
# SIMPLE INSTRUMENT DATA PREPARATION
# =============================================================================


def prepare_instrument_data(
    instrument: str,
    data_df: pd.DataFrame,
    rules_cache: dict[str, Any],
    primary_key_field: str,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Prepare data for any instrument (standard or dynamic).

    Args:
        instrument: Name of the instrument
        data_df: Source DataFrame containing all data
        rules_cache: Cache of loaded JSON rules
        primary_key_field: Name of the primary key field

    Returns:
        Tuple of (filtered DataFrame, list of instrument variables)
    """
    if is_dynamic_rule_instrument(instrument):
        # Dynamic instrument - use DynamicInstrumentProcessor
        processor = DynamicInstrumentProcessor(instrument)
        return processor.prepare_data(data_df, primary_key_field)
    
    # Standard instrument - simple preparation
    instrument_variables = list(rules_cache.get(instrument, {}).keys())
    
    if not instrument_variables:
        return pd.DataFrame(), []
    
    # Build column list
    core_cols = get_core_columns()
    relevant_cols = [col for col in core_cols if col in data_df.columns]
    
    # Add instrument variables
    for var in instrument_variables:
        if var in data_df.columns:
            relevant_cols.append(var)
    
    # Add completion columns
    completion_cols = [col for col in get_completion_columns() if col in data_df.columns]
    relevant_cols.extend(completion_cols)
    
    # Remove duplicates while preserving order
    relevant_cols = list(dict.fromkeys(relevant_cols))
    
    if not relevant_cols:
        return pd.DataFrame(), instrument_variables
    
    # Filter DataFrame to relevant columns
    instrument_df = data_df[relevant_cols].copy()
    
    # Filter to records with actual instrument data
    non_core_cols = [
        col for col in relevant_cols
        if col not in core_cols and not col.endswith("_complete")
    ]
    
    if non_core_cols:
        has_data_mask = instrument_df[non_core_cols].notna().any(axis=1)
        instrument_df = instrument_df[has_data_mask].reset_index(drop=True)
    
    return instrument_df, instrument_variables
