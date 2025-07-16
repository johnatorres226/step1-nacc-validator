"""
This module handles fetching and transforming data from a REDCap project.

It provides a set of ETL (Extract, Transform, Load) functions designed to
efficiently retrieve data via the REDCap API, apply necessary transformations,
and prepare it for the quality control (QC) pipeline.

Key functionalities include:
- Fetching records for specific instruments and events.
- Applying various filtering logics to select relevant data subsets.
- Transforming data by nullifying fields of incomplete instruments.
- Handling different ETL modes (e.g., complete events, complete instruments).
- Saving intermediate ETL outputs for debugging and auditing.
"""

# fetcher.py

import requests
import pandas as pd
import time
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from abc import ABC, abstractmethod

# ETL-optimized imports
from pipeline.config_manager import (
    QCConfig,
    complete_event_filter_logic,
    qc_filterer_logic,
    complete_instruments_vars,
)
from pipeline.logging_config import get_logger
from pipeline.helpers import get_variables_for_instrument, load_rules_for_instruments

# Initialize logger
logger = get_logger(__name__)


# =============================================================================
# DATA CONTRACTS AND VALIDATION
# =============================================================================

class DataContract:
    """Defines the expected data structure and validation rules."""
    
    REQUIRED_FIELDS = ['ptid', 'redcap_event_name']
    
    @staticmethod
    def validate_required_fields(df: pd.DataFrame) -> List[str]:
        """Validate that required fields are present in the dataframe."""
        errors = []
        for field in DataContract.REQUIRED_FIELDS:
            if field not in df.columns:
                errors.append(f"Required field '{field}' is missing from data")
        return errors


class RedcapApiClient:
    """Handles REDCap API communication with proper error handling."""
    
    def __init__(self, config: QCConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        })
    
    def fetch_data(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch data from REDCap API with robust error handling."""
        try:
            response = self.session.post(
                self.config.api_url,
                data=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            if not data:
                logger.warning("REDCap API returned empty response")
                return []
            
            return data
            
        except requests.exceptions.Timeout:
            error_msg = f"API request timed out after {self.config.timeout} seconds"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"REDCap API request failed: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except (ValueError, json.JSONDecodeError) as e:
            error_msg = f"Failed to parse JSON response: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)


class DataProcessor:
    """Handles data processing and transformation."""
    
    def __init__(self, config: QCConfig):
        self.config = config
    
    def process_raw_data(self, raw_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Process raw REDCap data into structured DataFrame."""
        if not raw_data:
            logger.warning("No data to process")
            return pd.DataFrame()
        
        df = pd.DataFrame(raw_data)
        
        # Handle column mapping
        df = self._handle_column_mapping(df)
        
        # Validate required fields
        validation_errors = DataContract.validate_required_fields(df)
        if validation_errors:
            error_msg = "Data validation failed: " + "; ".join(validation_errors)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        return df
    
    def _handle_column_mapping(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle column mapping and required field creation."""
        # Map record_id to ptid if needed
        if 'record_id' in df.columns and 'ptid' not in df.columns:
            df = df.rename(columns={'record_id': 'ptid'})
            logger.debug("Mapped 'record_id' to 'ptid' column")
        
        # Handle missing ptid - this is now an error condition
        if 'ptid' not in df.columns:
            raise ValueError("Critical error: 'ptid' column missing from REDCap data. This indicates a data integrity issue.")
        
        # Handle missing redcap_event_name
        if 'redcap_event_name' not in df.columns and not df.empty:
            raise ValueError("Critical error: 'redcap_event_name' column missing from REDCap data. Check event configuration.")
        
        return df


class RedcapDataFetcher:
    """Main class for fetching and processing REDCap data."""
    
    def __init__(self):
        self.config = QCConfig()
        self.api_client = RedcapApiClient(self.config)
        self.processor = DataProcessor(self.config)
    
    def fetch(self, form_names: List[str], event_names: List[str], 
              filter_logic: Optional[str] = None, output_dir: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch REDCap data with comprehensive error handling and validation.
        
        Args:
            form_names: List of REDCap instrument names
            event_names: List of REDCap event names
            filter_logic: Optional REDCap filter logic string
            output_dir: Directory to save the raw fetched data
            
        Returns:
            A DataFrame containing the fetched and processed REDCap data
            
        Raises:
            ValueError: If configuration is invalid or data validation fails
            RuntimeError: If API request fails or returns invalid data
        """
        try:
            logger.info(f"Fetching data for {len(form_names)} forms and {len(event_names)} events")
            start_time = time.time()
            
            # Prepare API payload
            payload = self._build_payload(form_names, event_names, filter_logic)
            
            # Fetch raw data
            raw_data = self._fetch_raw_data(payload)
            
            # Process data
            processed_data = self._process_data(raw_data)
            
            # Save data if requested
            if output_dir:
                self._save_data(processed_data, output_dir)
            
            fetch_time = time.time() - start_time
            logger.info(f"Successfully fetched {len(processed_data)} records in {fetch_time:.2f} seconds")
            
            return processed_data
            
        except Exception as e:
            self._handle_fetch_error(e)
            raise
    
    def _build_payload(self, form_names: List[str], event_names: List[str], 
                      filter_logic: Optional[str] = None) -> Dict[str, Any]:
        """Build the REDCap API payload."""
        payload = {
            'token': self.config.api_token,
            'content': 'record',
            'format': 'json',
            'type': 'flat',
            'rawOrLabel': 'raw',
            'rawOrLabelHeaders': 'raw',
            'exportCheckboxLabel': 'false',
            'exportSurveyFields': 'false',
            'exportDataAccessGroups': 'false',
            'returnFormat': 'json',
        }
        
        if form_names:
            payload['forms'] = ','.join(form_names)
        if event_names:
            payload['events'] = ','.join(event_names)
        if filter_logic:
            payload['filterLogic'] = filter_logic
            logger.info(f"Applying filter logic: {filter_logic}")
        
        return payload
    
    def _fetch_raw_data(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch raw data from REDCap API."""
        return self.api_client.fetch_data(payload)
    
    def _process_data(self, raw_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Process raw data into structured DataFrame."""
        return self.processor.process_raw_data(raw_data)
    
    def _save_data(self, data: pd.DataFrame, output_dir: str) -> None:
        """Save processed data to output directory."""
        if not data.empty:
            _save_etl_output(data, output_dir, "ETL_Fetcher_Raw_Output")
    
    def _handle_fetch_error(self, error: Exception) -> None:
        """Handle fetch errors with proper logging."""
        error_msg = f"Data fetching failed: {str(error)}"
        logger.error(error_msg)
        # Additional error handling can be added here (e.g., notifications, cleanup)


# =============================================================================
# LEGACY FUNCTION WRAPPER
# =============================================================================

def fetch_redcap_data_etl(
    form_names: List[str],
    event_names: List[str],
    filter_logic: Optional[str] = None,
    output_dir: Optional[str] = None
) -> pd.DataFrame:
    """
    Legacy wrapper function for backward compatibility.
    
    This function now uses the new RedcapDataFetcher class internally.
    """
    fetcher = RedcapDataFetcher()
    return fetcher.fetch(form_names, event_names, filter_logic, output_dir)


# =============================================================================
# EXISTING UTILITY FUNCTIONS
# =============================================================================

def instrument_subset_transformer(
    data: pd.DataFrame,
    instrument_list: List[str],
    rules_cache: Dict[str, Any],
    ptid_list: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
) -> pd.DataFrame:
    """
    Transforms data by nullifying fields of incomplete instruments.

    This preserves the record's integrity while ensuring that downstream
    validation only considers data from instruments marked as complete ('2').

    Args:
        data: DataFrame from REDCap fetcher.
        instrument_list: The list of instruments being processed.
        rules_cache: A cache of the JSON validation rules for all instruments.
        ptid_list: Optional record ID(s) to filter by.
        output_dir: Directory to save individual record subset files.

    Returns:
        A DataFrame with data from incomplete instruments nullified.
    """
    if data.empty:
        logger.warning("Empty DataFrame provided to instrument_subset_transformer")
        return data

    # Create a copy to avoid modifying the original DataFrame
    transformed_df = data.copy()

    # Filter by ptid_list if provided
    if ptid_list:
        if 'ptid' in transformed_df.columns:
            # Ensure ptid_list contains strings for comparison
            ptid_list_str = [str(p) for p in ptid_list]
            transformed_df = transformed_df[transformed_df['ptid'].isin(ptid_list_str)].reset_index(drop=True)
            logger.info(f"Filtered for {len(ptid_list_str)} specified PTIDs, resulting in {len(transformed_df)} records.")
        else:
            logger.warning("'ptid' column not found, ignoring ptid_list filter.")

    # Get a map of instruments to their variables from the provided rules cache
    instrument_to_vars_map = {
        instrument: get_variables_for_instrument(instrument, rules_cache)
        for instrument in instrument_list
    }

    # Iterate over each record to apply transformation
    for index, row in transformed_df.iterrows():
        for instrument in instrument_list:
            completion_var = f"{instrument}_complete"

            # Check if the instrument is incomplete (value is not '2')
            if completion_var in row and pd.notna(row[completion_var]) and str(row[completion_var]) != '2':
                # If incomplete, nullify all variables associated with this instrument
                instrument_vars = instrument_to_vars_map.get(instrument, [])
                for var in instrument_vars:
                    if var in transformed_df.columns:
                        transformed_df.at[index, var] = pd.NA

                logger.debug(f"Nullified data for incomplete instrument '{instrument}' in record PTID {row.get('ptid', 'N/A')}")

    logger.info("Instrument subset transformation complete.")

    if output_dir:
        _save_etl_output(transformed_df, output_dir, "ETL_Transformed_Instrument_Subset")

    return transformed_df


def _save_etl_output(df: pd.DataFrame, output_dir: str, filename_prefix: str) -> str:
    """
    Save ETL output to a designated directory with a timestamp.

    Args:
        df: DataFrame to save.
        output_dir: Base output directory.
        filename_prefix: Prefix for the filename.

    Returns:
        The full path of the saved file as a string.
    """
    run_date = datetime.now().strftime("%d%b%Y")
    # Create ETL_Data subdirectory within the run-specific directory
    etl_dir = Path(output_dir) / f"ETL_Data_{run_date}"
    etl_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{filename_prefix}_{run_date}.csv"
    file_path = etl_dir / filename

    df.to_csv(file_path, index=False)
    print("")
    print(f"Saved ETL output: {file_path} ({len(df)} records)")

    return str(file_path)


def _get_filter_logic(config: QCConfig) -> Optional[str]:
    """Determines the appropriate REDCap filter logic based on the config."""
    if config.mode == 'complete_events':
        logger.info("Using 'complete events only' filter logic.")
        return complete_event_filter_logic
    elif config.mode == 'complete_instruments':
        logger.info("Using 'QC status check' filter logic for 'complete instruments' mode.")
        return qc_filterer_logic
    elif config.mode == 'custom':
        if config.include_qced:
            logger.info("Custom mode: Including already QCed data - no API-level filtering.")
            return None
        else:
            logger.info("Custom mode: Using 'QC status check' filter logic.")
            return qc_filterer_logic
    elif config.mode == 'none':
        logger.warning("No filtering enabled. Fetching all records for the specified instruments/events.")
        return None
    else: # Default behavior if mode is not set or unrecognized
        logger.info("Defaulting to 'QC status check' filter logic.")
        return qc_filterer_logic


def _fetch_with_fallback(
    fetch_instruments: List[str],
    events: List[str],
    filter_logic: Optional[str],
    output_dir: Optional[Union[str, Path]]
) -> pd.DataFrame:
    """Fetches data, with a fallback to no-filter if the initial fetch is too restrictive."""
    output_dir_str = str(output_dir) if output_dir else None
    data = fetch_redcap_data_etl(
        form_names=fetch_instruments,
        event_names=events,
        filter_logic=filter_logic,
        output_dir=output_dir_str
    )

    if data.empty:
        logger.warning("Initial fetch returned no data. The filter might be too restrictive.")
        return data

    # Check if we got meaningful participant data, not just QC form data
    qc_cols = {
        'qc_status_complete', 'qc_run_by', 'qc_last_run', 'qc_visit_date',
        'qc_status_test', 'qc_status', 'qc_results',
        'quality_control_check_complete'
    }
    core_cols = {'ptid', 'redcap_event_name'}
    participant_cols = set(data.columns) - qc_cols - core_cols

    if not participant_cols:
        logger.warning("Only QC-related columns found. This suggests the filter excluded all participant data.")
        logger.info("Attempting to fetch data again without any filter logic as a fallback...")
        try:
            # Fallback: Fetch original instruments without the QC form and without filters
            original_instruments = [inst for inst in fetch_instruments if inst != "quality_control_check"]
            fallback_data = fetch_redcap_data_etl(
                form_names=original_instruments,
                event_names=events,
                filter_logic=None,  # No filtering
                output_dir=output_dir_str
            )
            if not fallback_data.empty:
                logger.info("Fallback fetch successful. Using unfiltered data.")
                return fallback_data
            else:
                logger.warning("Fallback fetch also returned no data. Continuing with the original empty dataset.")
        except Exception as e:
            logger.error(f"Fallback fetch failed: {e}", exc_info=True)
            logger.warning("Continuing with the original (likely empty) filtered data.")

    return data


def fetch_etl_data(config: QCConfig, output_path: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """
    Main ETL function that orchestrates data fetching and transformation.

    This is the primary entry point for the ETL system, combining fetching
    and transformation in an optimized workflow based on the provided configuration.

    Args:
        config: A QCConfig object containing all run parameters.
        output_path: Optional path to use for ETL output. If None, uses config.output_path.

    Returns:
        A processed DataFrame ready for the QC pipeline.
    """
    logger.info(f"Starting ETL data fetch in '{config.mode}' mode.")

    # Use provided output_path or fall back to config.output_path
    etl_output_path = output_path if output_path is not None else config.output_path

    # Determine the appropriate filter logic from the config
    filter_logic = _get_filter_logic(config)

    # The 'quality_control_check' instrument is needed for any filtering
    fetch_instruments = config.instruments.copy()
    if filter_logic and "quality_control_check" not in fetch_instruments:
        fetch_instruments.append("quality_control_check")
        logger.info("Added 'quality_control_check' form to fetch list for filtering.")

    # Step 1: Fetch data, with fallback logic if filtering is too restrictive
    data = _fetch_with_fallback(
        fetch_instruments=fetch_instruments,
        events=config.events or [],
        filter_logic=filter_logic,
        output_dir=etl_output_path
    )

    if data.empty:
        logger.warning("No data returned from REDCap API after all fetch attempts. Exiting ETL process.")
        return data

    # Step 2: Apply instrument-level transformation if in 'complete_instruments' mode
    if config.mode == 'complete_instruments':
        logger.info("Applying instrument subset transformation.")

        # Load the necessary rules for the transformation
        rules_cache = load_rules_for_instruments(fetch_instruments)

        data = instrument_subset_transformer(
            data=data,
            instrument_list=fetch_instruments,
            rules_cache=rules_cache,
            ptid_list=config.ptid_list,
            output_dir=str(etl_output_path) if etl_output_path else None
        )

    logger.info(f"ETL process completed: {len(data)} records are ready for the QC pipeline.")
    return data