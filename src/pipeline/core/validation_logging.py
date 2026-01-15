"""
Validation logging functions for the QC pipeline.

This module contains functions for building detailed validation logs, broken down from the
monolithic build_detailed_validation_logs function into smaller, testable components.
"""

from typing import Any

import numpy as np
import pandas as pd

from ..logging.logging_config import get_logger
from .data_processing import DataProcessingError, ValidationLogsData

logger = get_logger(__name__)


# =============================================================================
# VALIDATION LOGGING FUNCTIONS
# =============================================================================


def extract_record_identifiers(record: pd.Series, primary_key_field: str) -> tuple[str, str]:
    """
    Extract primary key and event name from record.

    Args:
        record: Pandas series representing a single record.
        primary_key_field: Name of the primary key field.

    Returns:
        Tuple containing (primary_key_value, event_name).
    """
    pk_val = record.get(primary_key_field, "N/A")
    event = record.get("redcap_event_name", "N/A")
    return str(pk_val), str(event)


def determine_completion_status(record: pd.Series, instrument: str) -> tuple[str, str, str]:
    """
    Determine completion status, target variable, and status description.

    Args:
        record: Pandas series representing a single record.
        instrument: Name of the instrument being processed.

    Returns:
        Tuple containing (target_variable, completeness_status, pass_status).
    """
    instrument_complete_col = f"{instrument}_complete"

    if instrument_complete_col in record:
        # Check if the instrument is marked as complete ('2')
        completion_value = record.get(instrument_complete_col)
        is_complete = str(completion_value) == "2"

        target_variable = instrument_complete_col
        completeness_status = "Complete" if is_complete else "Incomplete"
        pass_status = "Pass" if is_complete else "Fail"

        return target_variable, completeness_status, pass_status
    # If no completeness variable exists for this instrument
    return "N/A", "No completeness field", "Fail"


def generate_error_message(
    record: pd.Series, instrument: str, completeness_status: str, pass_status: str
) -> Any:
    """
    Generate appropriate error message based on completion status.

    Args:
        record: Pandas series representing a single record.
        instrument: Name of the instrument being processed.
        completeness_status: The determined completion status.
        pass_status: The determined pass/fail status.

    Returns:
        Error message string or np.nan if no error.
    """
    if pass_status == "Pass":
        return np.nan

    instrument_complete_col = f"{instrument}_complete"

    if completeness_status == "No completeness field":
        return "Instrument completeness variable not found in data."
    completion_value = record.get(instrument_complete_col)
    return f"Instrument not marked as complete. Value is '{completion_value}'."


def create_validation_log_entry(
    primary_key: str,
    event: str,
    instrument: str,
    target_variable: str,
    completeness_status: str,
    pass_status: str,
    error_msg: Any,
    primary_key_field: str,
) -> dict[str, Any]:
    """
    Create single validation log entry.

    Args:
        primary_key: Primary key value for the record.
        event: Event name for the record.
        instrument: Name of the instrument.
        target_variable: Target variable being validated.
        completeness_status: Completion status description.
        pass_status: Pass/fail status.
        error_msg: Error message or np.nan.
        primary_key_field: Name of the primary key field.

    Returns:
        Dictionary representing a single log entry.
    """
    return {
        primary_key_field: primary_key,
        "redcap_event_name": event,
        "instrument_name": instrument,
        "target_variable": target_variable,
        "completeness_status": completeness_status,
        "processing_status": "Processed",
        "pass_fail": pass_status,
        "error": error_msg,
    }


def process_single_record_log(
    record: pd.Series, instrument: str, primary_key_field: str
) -> dict[str, Any]:
    """
    Process a single record to create validation log entry.

    Args:
        record: Pandas series representing a single record.
        instrument: Name of the instrument being processed.
        primary_key_field: Name of the primary key field.

    Returns:
        Dictionary representing the log entry for this record.
    """
    # Extract record identifiers
    primary_key, event = extract_record_identifiers(record, primary_key_field)

    # Determine completion status
    target_variable, completeness_status, pass_status = determine_completion_status(
        record, instrument
    )

    # Generate error message if needed
    error_msg = generate_error_message(record, instrument, completeness_status, pass_status)

    # Create log entry
    return create_validation_log_entry(
        primary_key,
        event,
        instrument,
        target_variable,
        completeness_status,
        pass_status,
        error_msg,
        primary_key_field,
    )


def build_detailed_validation_logs(
    df: pd.DataFrame, instrument: str, primary_key_field: str
) -> list[dict[str, Any]]:
    """
    Build detailed validation logs for instrument records.

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
    try:
        if df.empty:
            logger.warning(f"No records to process for instrument: {instrument}")
            return []

        logs = []
        for _, record_row in df.iterrows():
            log_entry = process_single_record_log(record_row, instrument, primary_key_field)
            logs.append(log_entry)

        logger.debug(f"Generated {len(logs)} validation log entries for instrument '{instrument}'.")
        return logs

    except Exception as e:
        logger.error(f"Failed to build validation logs for instrument {instrument}: {e}")
        raise DataProcessingError(f"Validation logging failed for {instrument}: {e}") from e


def build_validation_logs_summary(logs: list[dict[str, Any]]) -> ValidationLogsData:
    """
    Build summary statistics for validation logs.

    Args:
        logs: List of validation log entries.

    Returns:
        ValidationLogsData object with summary statistics.
    """
    total_records = len(logs)
    pass_count = sum(1 for log in logs if log.get("pass_fail") == "Pass")
    fail_count = total_records - pass_count

    return ValidationLogsData(
        log_entries=logs,
        total_records_processed=total_records,
        pass_count=pass_count,
        fail_count=fail_count,
    )



