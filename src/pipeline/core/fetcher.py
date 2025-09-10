"""
Modern REDCap ETL Pipeline Module

This module provides a clean, object-oriented ETL pipeline for fetching and processing
REDCap data. It follows a linear pipeline: fetch → validate → transform → save.

Main Entry Point:
    RedcapETLPipeline.run() - Use this for all ETL operations
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from ..config.config_manager import (
    QCConfig,
    complete_events_with_incomplete_qc_filter_logic,
    qc_filterer_logic,
)
from ..io.rules import load_rules_for_instruments
from ..logging.logging_config import get_logger
from .data_processing import get_variables_for_instrument

logger = get_logger(__name__)

# =============================================================================
# CONTEXT AND DATA STRUCTURES
# =============================================================================


@dataclass
class ETLContext:
    """Encapsulates ETL execution context with timestamps and configuration."""
    config: QCConfig
    run_date: str
    time_stamp: str
    output_path: Path | None = None

    @classmethod
    def create(cls,
               config: QCConfig,
               output_path: str | Path | None = None,
               date_tag: str | None = None,
               time_tag: str | None = None) -> "ETLContext":
        """Create an ETL context with proper timestamp handling."""
        if date_tag and time_tag:
            run_date, time_stamp = date_tag, time_tag
        else:
            current_datetime = datetime.now()
            run_date = current_datetime.strftime("%d%b%Y").upper()
            time_stamp = current_datetime.strftime("%H%M%S")

        output = Path(output_path) if output_path else (
            Path(config.output_path) if config.output_path else Path.cwd())
        return cls(config, run_date, time_stamp, output)


@dataclass
class ETLResult:
    """Encapsulates ETL execution results."""
    data: pd.DataFrame
    records_processed: int
    execution_time: float
    saved_files: list[Path]

    @property
    def is_empty(self) -> bool:
        return self.data.empty or self.records_processed == 0


# =============================================================================
# DATA CONTRACTS AND VALIDATION
# =============================================================================

class DataContract:
    """Defines the expected data structure and validation rules."""

    REQUIRED_FIELDS = ["ptid", "redcap_event_name"]

    @staticmethod
    def validate_required_fields(df: pd.DataFrame) -> list[str]:
        """Validate that required fields are present in the dataframe."""
        errors = []
        for field in DataContract.REQUIRED_FIELDS:
            if field not in df.columns:
                errors.append(f"Required field '{field}' is missing from data")
        return errors


# =============================================================================
# CORE ETL COMPONENTS
# =============================================================================

class RedcapApiClient:
    """Handles REDCap API communication with proper error handling."""

    def __init__(self, config: QCConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        })

    def fetch_data(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch data from REDCap API with robust error handling."""
        if not self.config.api_url:
            raise ValueError("REDCap API URL is not configured")

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
            error_msg = f"API request timed out after {
                self.config.timeout} seconds"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except requests.exceptions.RequestException as e:
            # If the response object is available, include its text for
            # clearer diagnostics (tests mock a 403 with text="Forbidden").
            resp_text = None
            try:
                resp = getattr(e, "response", None)
                if resp is not None:
                    resp_text = getattr(resp, "text", None)
            except Exception:
                resp_text = None

            if resp_text:
                error_msg = f"REDCap API request failed: {resp_text}"
            else:
                error_msg = f"REDCap API request failed: {e!s}"

            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except (ValueError, json.JSONDecodeError) as e:
            error_msg = f"Failed to parse JSON response: {e!s}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)


class DataValidator:
    """Handles data validation and quality checks."""

    @staticmethod
    def validate_and_process(raw_data: list[dict[str, Any]]) -> pd.DataFrame:
        """Validate and process raw REDCap data into structured DataFrame."""
        if not raw_data:
            logger.warning("No data to process")
            return pd.DataFrame()

        df = pd.DataFrame(raw_data)

        # Handle column mapping
        df = DataValidator._handle_column_mapping(df)

        # Validate required fields
        validation_errors = DataContract.validate_required_fields(df)
        if validation_errors:
            error_msg = "Data validation failed: " + \
                "; ".join(validation_errors)
            logger.error(error_msg)
            raise ValueError(error_msg)

        return df

    @staticmethod
    def _handle_column_mapping(df: pd.DataFrame) -> pd.DataFrame:
        """Handle column mapping and required field creation."""
        # Map record_id to ptid if needed
        if "record_id" in df.columns and "ptid" not in df.columns:
            df = df.rename(columns={"record_id": "ptid"})
            logger.debug("Mapped 'record_id' to 'ptid' column")

        # Handle missing ptid - this is now an error condition
        if "ptid" not in df.columns:
            raise ValueError(
                "Critical error: 'ptid' column missing from REDCap data")

        # Handle missing redcap_event_name
        if "redcap_event_name" not in df.columns and not df.empty:
            raise ValueError(
                "Critical error: 'redcap_event_name' column missing from REDCap data")

        return df


class DataTransformer:
    """Handles data transformation operations."""

    def __init__(self, context: ETLContext):
        self.context = context

    def apply_instrument_subset_transformation(
            self,
            data: pd.DataFrame,
            instrument_list: list[str]) -> pd.DataFrame:
        """Transform data by nullifying fields of incomplete instruments."""
        if data.empty:
            logger.warning("Empty DataFrame provided for transformation")
            return data

        transformed_df = data.copy()

        # Apply PTID filtering if specified
        if self.context.config.ptid_list:
            transformed_df = self._apply_ptid_filter(transformed_df)

        # Load rules and apply instrument-based transformation
        rules_cache = load_rules_for_instruments(instrument_list)
        instrument_to_vars_map = {
            instrument: get_variables_for_instrument(instrument, rules_cache)
            for instrument in instrument_list
        }

        # Apply transformation logic
        for index, row in transformed_df.iterrows():
            for instrument in instrument_list:
                completion_var = f"{instrument}_complete"

                if (completion_var in row and
                    pd.notna(row[completion_var]) and
                        str(row[completion_var]) != "2"):

                    # Nullify all variables for incomplete instruments
                    instrument_vars = instrument_to_vars_map.get(
                        instrument, [])
                    for var in instrument_vars:
                        if var in transformed_df.columns:
                            transformed_df.at[index, var] = pd.NA

                logger.debug(
                    f"Nullified data for incomplete instrument '{instrument}' "
                    f"in record PTID {row.get('ptid', 'N/A')}"
                )

        logger.info("Instrument subset transformation complete")
        return transformed_df

    def apply_basic_filtering(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply basic PTID filtering for non-instrument modes."""
        if self.context.config.ptid_list:
            return self._apply_ptid_filter(data)
        return data

    def _apply_ptid_filter(self, data: pd.DataFrame) -> pd.DataFrame:
        """Apply PTID filtering to the data."""
        if "ptid" not in data.columns:
            logger.warning(
                "'ptid' column not found, ignoring ptid_list filter")
            return data

        if not self.context.config.ptid_list:
            return data

        initial_count = len(data)
        ptid_list_str = [str(p) for p in self.context.config.ptid_list]
        filtered_data = data[data["ptid"].isin(
            ptid_list_str)].reset_index(drop=True)

        logger.info(
            f"Applied PTID filtering: {initial_count} → {
                len(filtered_data)} records " f"(filtered for {
                len(ptid_list_str)} PTIDs)")
        return filtered_data


class DataSaver:
    """Handles saving ETL outputs with consistent naming."""

    def __init__(self, context: ETLContext):
        self.context = context
        self.saved_files: list[Path] = []

    def save_etl_output(
            self,
            df: pd.DataFrame,
            filename_prefix: str) -> Path | None:
        """Save ETL output with consistent naming."""
        if df.empty:
            logger.warning(
                f"Empty DataFrame, skipping save for {filename_prefix}")
            return None

        if not self.context.output_path:
            logger.warning("No output path configured, skipping save")
            return None

        # Create Data_Fetched subdirectory
        etl_dir = (self.context.output_path /
                   "Data_Fetched")
        etl_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{filename_prefix}_{
            self.context.run_date}_{
            self.context.time_stamp}.csv"
        file_path = etl_dir / filename

        df.to_csv(file_path, index=False)
        self.saved_files.append(file_path)

        logger.debug(f"Saved ETL output: {file_path} ({len(df)} records)")
        return file_path


# =============================================================================
# FILTER LOGIC MANAGER
# =============================================================================

class FilterLogicManager:
    """Manages REDCap filter logic based on configuration."""

    @staticmethod
    def get_filter_logic(config: QCConfig) -> str | None:
        """Determine appropriate REDCap filter logic based on config mode."""
        mode_filters = {
            "complete_events": complete_events_with_incomplete_qc_filter_logic,
            "complete_visits": complete_events_with_incomplete_qc_filter_logic,
            "complete_instruments": qc_filterer_logic,
            "none": None
        }

        if config.mode in mode_filters:
            filter_logic = mode_filters[config.mode]
            if filter_logic:
                logger.info(f"Using '{config.mode}' filter logic")
            else:
                logger.warning("No filtering enabled. Fetching all records")
            return filter_logic

        logger.info("Defaulting to QC status check filter logic")
        return qc_filterer_logic


# =============================================================================
# MAIN ETL PIPELINE
# =============================================================================

class RedcapETLPipeline:
    """
    Main ETL Pipeline for REDCap data processing.

    This is the primary entry point for all ETL operations.
    Follows a clean linear pipeline: fetch → validate → transform → save.
    """

    def __init__(self, config: QCConfig):
        self.config = config
        # Components will be initialized in run()
        self.context = None
        self.api_client = None
        self.transformer = None
        self.saver = None

    def run(self,
            output_path: str | Path | None = None,
            date_tag: str | None = None,
            time_tag: str | None = None) -> ETLResult:
        """
        Execute the complete ETL pipeline.

        Args:
            output_path: Optional output directory path
            date_tag: Optional date tag for consistent naming
            time_tag: Optional time tag for consistent naming

        Returns:
            ETLResult containing processed data and execution metadata
        """
        start_time = time.time()

        try:
            # Initialize context and components
            self._initialize_components(output_path, date_tag, time_tag)

            logger.info(f"Starting ETL pipeline in '{self.config.mode}' mode")

            # Step 1: Fetch data
            raw_data = self._fetch_data()

            # Step 2: Validate data
            validated_data = self._validate_data(raw_data)

            # Step 3: Transform data
            transformed_data = self._transform_data(validated_data)

            # Step 4: Save data
            saved_files = self._save_data(transformed_data)

            execution_time = time.time() - start_time

            result = ETLResult(
                data=transformed_data,
                records_processed=len(transformed_data),
                execution_time=execution_time,
                saved_files=saved_files
            )

            logger.info(
                f"ETL pipeline completed: {
                    result.records_processed} records " f"processed in {
                    execution_time:.2f} seconds")

            return result

        except Exception as e:
            logger.error(f"ETL pipeline failed: {e!s}")
            raise

    def _initialize_components(self,
                               output_path: str | Path | None,
                               date_tag: str | None,
                               time_tag: str | None) -> None:
        """Initialize ETL components with proper context."""
        self.context = ETLContext.create(
            self.config, output_path, date_tag, time_tag)
        self.api_client = RedcapApiClient(self.config)
        self.transformer = DataTransformer(self.context)
        self.saver = DataSaver(self.context)

    def _fetch_data(self) -> list[dict[str, Any]]:
        """Fetch data from REDCap API."""
        # Determine filter logic
        filter_logic = FilterLogicManager.get_filter_logic(self.config)

        # Prepare instruments list
        fetch_instruments = self.config.instruments.copy()
        if filter_logic and "quality_control_check" not in fetch_instruments:
            fetch_instruments.append("quality_control_check")
            logger.info("Added 'quality_control_check' form for filtering")

        # Build API payload
        payload = self._build_api_payload(fetch_instruments, filter_logic)

        # Fetch data with fallback handling
        try:
            # Ensure components are initialized
            assert self.api_client is not None, "API client not initialized"

            raw_data = self.api_client.fetch_data(payload)
            if not raw_data:
                logger.warning("Initial fetch returned no data")
                # Attempt fallback without filtering if original had filters
                if filter_logic:
                    logger.info("Attempting fallback fetch without filters")
                    fallback_payload = self._build_api_payload(
                        [inst for inst in fetch_instruments if inst != "quality_control_check"],
                        None
                    )
                    raw_data = self.api_client.fetch_data(fallback_payload)
                    if raw_data:
                        logger.info("Fallback fetch successful")

            return raw_data

        except Exception as e:
            logger.error(f"Data fetch failed: {e!s}")
            raise

    def _build_api_payload(self,
                           instruments: list[str],
                           filter_logic: str | None) -> dict[str,
                                                                Any]:
        """Build REDCap API payload."""
        payload = {
            "token": self.config.api_token,
            "content": "record",
            "format": "json",
            "type": "flat",
            "rawOrLabel": "raw",
            "rawOrLabelHeaders": "raw",
            "exportCheckboxLabel": "false",
            "exportSurveyFields": "false",
            "exportDataAccessGroups": "false",
            "returnFormat": "json",
        }

        if instruments:
            payload["forms"] = ",".join(instruments)
        if self.config.events:
            payload["events"] = ",".join(self.config.events)
        if filter_logic:
            payload["filterLogic"] = filter_logic
            logger.info(
                "Applying filter logic (see complete_events_with_incomplete_qc_filter_logic "
                "in config_manager.py)")

        return payload

    def _validate_data(self, raw_data: list[dict[str, Any]]) -> pd.DataFrame:
        """Validate and process raw data."""
        return DataValidator.validate_and_process(raw_data)

    def _transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data based on configuration mode."""
        if data.empty:
            logger.warning("No data to transform")
            return data

        # Ensure transformer is initialized
        assert self.transformer is not None, "Transformer not initialized"

        if self.config.mode == "complete_instruments":
            logger.info("Applying instrument subset transformation")
            return self.transformer.apply_instrument_subset_transformation(
                data, self.config.instruments
            )
        logger.info("Applying basic filtering")
        return self.transformer.apply_basic_filtering(data)

    def _save_data(self, data: pd.DataFrame) -> list[Path]:
        """Save processed data."""
        saved_files = []

        # Ensure context and saver are initialized
        assert self.context is not None, "Context not initialized"
        assert self.saver is not None, "Saver not initialized"

        if not data.empty and self.context.output_path:
            file_path = self.saver.save_etl_output(data, "ETL_ProcessedData")
            if file_path:
                saved_files.append(file_path)

        return saved_files
