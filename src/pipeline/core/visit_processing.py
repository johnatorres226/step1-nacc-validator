"""
Visit processing functions for the QC pipeline.

This module contains functions for processing complete visits, broken down from the
monolithic build_complete_visits_df function into smaller, testable components.
"""

import pandas as pd

from ..config.config_manager import get_config
from ..logging.logging_config import get_logger
from .data_processing import DataProcessingError

logger = get_logger(__name__)


# =============================================================================
# VISIT PROCESSING FUNCTIONS
# =============================================================================


def validate_dataframe_not_empty(df: pd.DataFrame) -> None:
    """
    Validate that dataframe is not empty for processing.

    Args:
        df: DataFrame to validate.

    Raises:
        DataProcessingError: If dataframe is empty.
    """
    if df.empty:
        raise DataProcessingError("Cannot build complete visits dataset from empty DataFrame.")


def generate_completion_column_names(instrument_list: list[str]) -> list[str]:
    """
    Generate completion column names from instrument list.

    Args:
        instrument_list: List of instrument names.

    Returns:
        List of completion column names, excluding form_header.
    """
    return [f"{inst}_complete" for inst in instrument_list if inst.lower() != "form_header"]


def ensure_completion_columns_exist(df: pd.DataFrame, completion_cols: list[str]) -> pd.DataFrame:
    """
    Ensure all completion columns exist with default values.

    Args:
        df: DataFrame to process.
        completion_cols: List of required completion column names.

    Returns:
        DataFrame with all completion columns present.
    """
    df_copy = df.copy()

    # Ensure packet column exists
    if "packet" not in df_copy.columns:
        df_copy["packet"] = "unknown"
        logger.debug("Added default 'packet' column with value 'unknown'")

    for col in completion_cols:
        if col not in df_copy.columns:
            logger.warning(
                f"Completion column '{col}' not found in data. "
                f"Assuming instrument is not complete for all records."
            )
            # Default to incomplete if the column is missing
            df_copy[col] = "0"

    return df_copy


def normalize_completion_column_types(df: pd.DataFrame, completion_cols: list[str]) -> pd.DataFrame:
    """
    Convert completion columns to string type for consistent comparison.

    Args:
        df: DataFrame to process.
        completion_cols: List of completion column names.

    Returns:
        DataFrame with completion columns normalized to string type.
    """
    df_copy = df.copy()

    # Convert all completion columns to string to handle mixed types (e.g.,
    # 2.0, '2', 2)
    for col in completion_cols:
        if col in df_copy.columns:
            df_copy[col] = df_copy[col].astype(str)

    return df_copy


def create_completion_mask(df: pd.DataFrame, completion_cols: list[str]) -> pd.Series:
    """
    Create boolean mask for records with all instruments complete.

    Args:
        df: DataFrame to process.
        completion_cols: List of completion column names.

    Returns:
        Boolean series indicating records with all instruments complete.
    """
    # Create a boolean mask for completion status (all completion columns must
    # be '2')
    completion_mask = (df[completion_cols] == "2").all(axis=1)
    return completion_mask


def identify_complete_visits(
    df: pd.DataFrame, primary_key_field: str
) -> list[tuple[str, str, str]]:
    """
    Identify visits where all records are complete.

    Args:
        df: DataFrame with completion mask already applied.
        primary_key_field: Name of the primary key field.

    Returns:
        List of tuples representing complete visits (primary_key, event_name, packet).
    """
    # For each visit, check if ALL records in that visit are complete
    # A visit is complete if all its records have all instruments complete
    visit_completion = df.groupby([primary_key_field, "redcap_event_name"])[
        "_temp_all_complete"
    ].all()

    # Get packet information for each visit (take the first packet value for
    # each visit)
    visit_packets = df.groupby([primary_key_field, "redcap_event_name"])["packet"].first()

    # Get complete visits (where the aggregated result is True)
    complete_visits_series = visit_completion[visit_completion]

    # Combine visit data with packet information
    complete_visits = []
    for pk, event in complete_visits_series.index:
        packet = visit_packets.get((pk, event), "unknown")
        complete_visits.append((pk, event, packet))

    return complete_visits


def create_complete_visits_summary(
    complete_visits: list[tuple[str, str, str]], completion_cols: list[str], primary_key_field: str
) -> pd.DataFrame:
    """
    Create summary dataframe of complete visits.

    Args:
        complete_visits: List of complete visit tuples (pk, event, packet).
        completion_cols: List of completion column names.
        primary_key_field: Name of the primary key field.

    Returns:
        DataFrame summarizing complete visits with packet information.
    """
    if not complete_visits:
        logger.debug("ETL identified 0 truly complete visits.")
        return pd.DataFrame()

    # Create the summary DataFrame with packet information
    complete_visits_summary = pd.DataFrame(
        complete_visits, columns=[primary_key_field, "redcap_event_name", "packet"]
    )

    # Create the final report DataFrame
    report_df = complete_visits_summary.copy()
    report_df["complete_instruments_count"] = len(completion_cols)
    report_df["completion_status"] = "All Complete"

    logger.debug(f"ETL identified {len(report_df)} truly complete visits (optimized).")

    return report_df


def extract_complete_visits_tuples(
    summary_df: pd.DataFrame, primary_key_field: str
) -> list[tuple[str, str]]:
    """
    Extract list of complete visit tuples from summary dataframe.

    Note: This function maintains backward compatibility by returning only (pk, event) tuples,
    but the summary dataframe now includes packet information.

    Args:
        summary_df: Summary dataframe of complete visits.
        primary_key_field: Name of the primary key field.

    Returns:
        List of tuples for downstream filtering.
    """
    if summary_df.empty:
        return []

    # Return only pk and event for backward compatibility with existing code
    return list(
        summary_df[[primary_key_field, "redcap_event_name"]].itertuples(index=False, name=None)
    )


def build_complete_visits_df(
    data_df: pd.DataFrame, instrument_list: list[str]
) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    """
    Orchestrate building complete visits dataframe and tuple list.

    Identifies and creates a DataFrame of truly complete visits.
    A visit (a unique primary_key-event combination) is considered complete if all
    expected instruments for that visit are present and marked as complete ('2').

    **PERFORMANCE OPTIMIZED**: Uses vectorized operations instead of nested loops
    for significantly better performance on large datasets.

    Args:
        data_df: The DataFrame containing all data.
        instrument_list: The list of all instruments to check for completion.

    Returns:
        A tuple containing:
        - A DataFrame summarizing the complete visits.
        - A list of tuples, each with (primary_key, redcap_event_name) for a complete visit.
    """
    try:
        # Step 1: Validate input
        validate_dataframe_not_empty(data_df)

        # Step 2: Generate completion column names
        completion_cols = generate_completion_column_names(instrument_list)

        # Step 3: Ensure completion columns exist
        df_with_cols = ensure_completion_columns_exist(data_df, completion_cols)

        # Step 4: Normalize column types
        df_normalized = normalize_completion_column_types(df_with_cols, completion_cols)

        # Step 5: Create completion mask
        primary_key_field = get_config().primary_key_field
        completion_mask = create_completion_mask(df_normalized, completion_cols)

        # Add the completion mask as a temporary column for groupby operations
        df_normalized["_temp_all_complete"] = completion_mask

        # Step 6: Identify complete visits
        complete_visits = identify_complete_visits(df_normalized, primary_key_field)

        # Clean up temporary column
        df_normalized.drop("_temp_all_complete", axis=1, inplace=True)

        # Step 7: Create summary dataframe
        summary_df = create_complete_visits_summary(
            complete_visits, completion_cols, primary_key_field
        )

        # Step 8: Extract tuples for downstream processing
        complete_visits_tuples = extract_complete_visits_tuples(summary_df, primary_key_field)

        return summary_df, complete_visits_tuples

    except DataProcessingError:
        # Re-raise data processing errors
        raise
    except Exception as e:
        logger.error(f"Failed to build complete visits dataframe: {e}")
        raise DataProcessingError(f"Complete visits processing failed: {e}") from e


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================


def build_complete_visits_df_legacy(
    data_df: pd.DataFrame, instrument_list: list[str]
) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    """
    DEPRECATED: Use build_complete_visits_df() instead.

    Legacy function maintained for backward compatibility during refactoring.
    """
    import warnings

    warnings.warn(
        "build_complete_visits_df_legacy is deprecated. Use build_complete_visits_df() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return build_complete_visits_df(data_df, instrument_list)
