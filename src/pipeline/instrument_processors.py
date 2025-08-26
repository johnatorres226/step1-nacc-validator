"""
Instrument processors implementing the strategy pattern for data preparation.

This module provides a unified interface for processing different types of instruments
(standard and dynamic) through a strategy pattern, eliminating complex branching logic.
"""
from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any, Optional
import pandas as pd

from .context import ProcessingContext
from .config_manager import (
    is_dynamic_rule_instrument, get_core_columns, get_completion_columns
)
# Import DynamicInstrumentProcessor here to avoid circular imports
from .helpers import DynamicInstrumentProcessor


class InstrumentDataProcessor(ABC):
    """
    Abstract base class for instrument data processors.
    
    This implements the strategy pattern to handle different types of instruments
    with a unified interface, eliminating complex branching logic.
    """
    
    def __init__(self, instrument_name: str):
        """
        Initialize the processor for a specific instrument.
        
        Args:
            instrument_name: Name of the instrument to process
        """
        self.instrument_name = instrument_name
    
    @staticmethod
    def create_processor(instrument_name: str) -> 'InstrumentDataProcessor':
        """
        Factory method to create appropriate processor for an instrument.
        
        Args:
            instrument_name: Name of the instrument
            
        Returns:
            Appropriate processor instance (Dynamic or Standard)
        """
        if is_dynamic_rule_instrument(instrument_name):
            return DynamicInstrumentDataProcessor(instrument_name)
        else:
            return StandardInstrumentDataProcessor(instrument_name)
    
    @abstractmethod
    def prepare_data(
        self, 
        context: ProcessingContext
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Prepare data for the instrument.
        
        Args:
            context: Processing context containing data and configuration
            
        Returns:
            Tuple of (filtered DataFrame, list of instrument variables)
        """
        pass
    
    @abstractmethod
    def get_variables(self, context: ProcessingContext) -> List[str]:
        """
        Get all variables for this instrument.
        
        Args:
            context: Processing context containing rules cache
            
        Returns:
            List of variable names for this instrument
        """
        pass
    
    def _get_relevant_columns(
        self, 
        df: pd.DataFrame, 
        instrument_variables: List[str]
    ) -> List[str]:
        """
        Get columns relevant to this instrument.
        
        Args:
            df: Source DataFrame
            instrument_variables: Variables specific to this instrument
            
        Returns:
            List of relevant column names
        """
        # Start with core columns
        core_cols = get_core_columns()
        relevant_cols = [col for col in core_cols if col in df.columns]
        
        # Add instrument variables
        for var in instrument_variables:
            if var in df.columns:
                relevant_cols.append(var)
        
        # Add completion columns
        completion_cols = get_completion_columns()
        for col in completion_cols:
            if col in df.columns:
                relevant_cols.append(col)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(relevant_cols))
    
    def _filter_records_with_data(
        self, 
        df: pd.DataFrame, 
        relevant_cols: List[str]
    ) -> pd.DataFrame:
        """
        Filter DataFrame to only include records with actual data.
        
        Args:
            df: DataFrame to filter
            relevant_cols: All relevant columns for the instrument
            
        Returns:
            Filtered DataFrame with only records containing data
        """
        if df.empty or not relevant_cols:
            return pd.DataFrame()
        
        # Identify non-core columns (actual instrument data)
        core_cols = get_core_columns()
        non_core_cols = [
            col for col in relevant_cols 
            if col not in core_cols and not col.endswith('_complete')
        ]
        
        if non_core_cols:
            # Filter to records that have data in at least one instrument variable
            has_data_mask = df[non_core_cols].notna().any(axis=1)
            return df[has_data_mask].reset_index(drop=True)
        
        return df


class StandardInstrumentDataProcessor(InstrumentDataProcessor):
    """
    Processor for standard (non-dynamic) instruments.
    
    This handles instruments with fixed validation rules.
    """
    
    def get_variables(self, context: ProcessingContext) -> List[str]:
        """Get variables for standard instrument from rules cache."""
        return list(context.rules_cache.get(self.instrument_name, {}).keys())
    
    def prepare_data(
        self, 
        context: ProcessingContext
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Prepare data for standard instrument.
        
        Args:
            context: Processing context with data and configuration
            
        Returns:
            Tuple of (filtered DataFrame, list of instrument variables)
        """
        instrument_variables = self.get_variables(context)
        
        if not instrument_variables:
            return pd.DataFrame(), []
        
        # Get relevant columns
        relevant_cols = self._get_relevant_columns(
            context.data_df, instrument_variables
        )
        
        if not relevant_cols:
            return pd.DataFrame(), instrument_variables
        
        # Filter DataFrame and records
        instrument_df = context.data_df[relevant_cols].copy()
        instrument_df = self._filter_records_with_data(
            instrument_df, relevant_cols
        )
        
        return instrument_df, instrument_variables


class DynamicInstrumentDataProcessor(InstrumentDataProcessor):
    """
    Processor for dynamic rule instruments.
    
    This handles instruments with variable-based rule selection using
    the consolidated DynamicInstrumentProcessor.
    """
    
    def __init__(self, instrument_name: str):
        """Initialize with dynamic instrument processor."""
        super().__init__(instrument_name)
        self._processor = DynamicInstrumentProcessor(instrument_name)
    
    def get_variables(self, context: ProcessingContext) -> List[str]:
        """Get all possible variables across rule variants."""
        return self._processor.get_all_variables()
    
    def prepare_data(
        self, 
        context: ProcessingContext
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Prepare data for dynamic instrument using consolidated processor.
        
        Args:
            context: Processing context with data and configuration
            
        Returns:
            Tuple of (filtered DataFrame, list of instrument variables)
        """
        return self._processor.prepare_data(
            context.data_df, context.primary_key_field
        )
    
    def get_variants_in_data(self, df: pd.DataFrame) -> List[str]:
        """Get variants present in the data."""
        return self._processor.get_variants_in_data(df)
    
    def get_rules_for_variant(self, variant: str) -> Dict[str, Any]:
        """Get rules for specific variant."""
        return self._processor.get_rules_for_variant(variant)


class InstrumentDataCache:
    """
    Manages cached DataFrames for multiple instruments using the strategy pattern.
    
    This replaces the complex prepare_instrument_data_cache function with
    a more maintainable object-oriented approach.
    """
    
    def __init__(self, context: ProcessingContext):
        """
        Initialize cache with processing context.
        
        Args:
            context: Processing context containing data and configuration
        """
        self.context = context
        self._cache: Dict[str, pd.DataFrame] = {}
        self._processors: Dict[str, InstrumentDataProcessor] = {}
        self._variables_map: Dict[str, List[str]] = {}
    
    def prepare_all(self) -> Dict[str, pd.DataFrame]:
        """
        Prepare data for all instruments in the context.
        
        Returns:
            Dictionary mapping instrument names to their prepared DataFrames
        """
        for instrument in self.context.instrument_list:
            self.prepare_instrument(instrument)
        
        return self._cache
    
    def prepare_instrument(self, instrument: str) -> pd.DataFrame:
        """
        Prepare data for a specific instrument.
        
        Args:
            instrument: Name of the instrument to prepare
            
        Returns:
            Prepared DataFrame for the instrument
        """
        if instrument in self._cache:
            return self._cache[instrument]
        
        # Create appropriate processor
        processor = InstrumentDataProcessor.create_processor(instrument)
        self._processors[instrument] = processor
        
        # Prepare data
        instrument_df, variables = processor.prepare_data(self.context)
        
        # Cache results
        self._cache[instrument] = instrument_df
        self._variables_map[instrument] = variables
        
        # Log results
        from .logging_config import get_logger
        logger = get_logger(__name__)
        logger.debug(
            f"Prepared {len(instrument_df)} records for instrument '{instrument}' "
            f"with {len(instrument_df.columns) if not instrument_df.empty else 0} columns"
        )
        logger.debug(
            f"Variables for {instrument}: "
            f"{variables[:10]}{'...' if len(variables) > 10 else ''}"
        )
        
        return instrument_df
    
    def get_instrument_data(self, instrument: str) -> pd.DataFrame:
        """Get cached data for an instrument."""
        return self._cache.get(instrument, pd.DataFrame())
    
    def get_instrument_variables(self, instrument: str) -> List[str]:
        """Get variables for an instrument."""
        return self._variables_map.get(instrument, [])
    
    def get_processor(self, instrument: str) -> Optional[InstrumentDataProcessor]:
        """Get processor for an instrument."""
        return self._processors.get(instrument)
    
    @property
    def instrument_count(self) -> int:
        """Get number of prepared instruments."""
        return len(self._cache)
    
    @property
    def total_records(self) -> int:
        """Get total number of records across all instruments."""
        return sum(len(df) for df in self._cache.values())
