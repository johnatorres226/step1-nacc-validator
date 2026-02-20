"""
Pipeline result objects and improved data models for the QC pipeline.

This module provides structured data models for pipeline stages, replacing loose
variables with proper result objects that encapsulate state and provide clear
interfaces between pipeline steps.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

# =============================================================================
# PIPELINE STAGE RESULT OBJECTS
# =============================================================================


@dataclass
class DataFetchResult:
    """Result object for data fetching stage."""

    data: pd.DataFrame
    records_processed: int
    execution_time: float
    source_info: dict[str, Any]
    fetch_timestamp: datetime
    success: bool = True
    error_message: str | None = None

    @property
    def is_empty(self) -> bool:
        """Check if fetched data is empty."""
        return self.data.empty




@dataclass
class RulesLoadingResult:
    """Result object for rules loading stage."""

    rules_cache: dict[str, dict[str, Any]]
    instruments_processed: list[str]
    loading_time: float
    variable_to_instrument_map: dict[str, str]
    instrument_to_variables_map: dict[str, list[str]]
    success: bool = True
    failed_instruments: list[str] = field(default_factory=list)
    error_messages: dict[str, str] = field(default_factory=dict)

    @property
    def loaded_instruments_count(self) -> int:
        """Number of instruments successfully loaded."""
        return len(self.instruments_processed) - len(self.failed_instruments)

    def get_rules_for_instrument(self, instrument: str) -> dict[str, Any]:
        """Get rules for a specific instrument."""
        return self.rules_cache.get(instrument, {})




@dataclass
class DataPreparationResult:
    """Result object for data preparation stage."""

    instrument_data_cache: dict[str, pd.DataFrame]
    complete_visits_data: Optional["CompleteVisitsResult"]
    preparation_time: float
    records_per_instrument: dict[str, int]
    success: bool = True
    error_message: str | None = None

    @property
    def total_records_prepared(self) -> int:
        """Total number of records across all instruments."""
        return sum(self.records_per_instrument.values())

    @property
    def instruments_with_data(self) -> list[str]:
        """List of instruments that have data after preparation."""
        return [inst for inst, count in self.records_per_instrument.items() if count > 0]

    def get_instrument_data(self, instrument: str) -> pd.DataFrame:
        """Get prepared data for a specific instrument."""
        return self.instrument_data_cache.get(instrument, pd.DataFrame())


@dataclass
class CompleteVisitsResult:
    """Result object for complete visits processing."""

    summary_dataframe: pd.DataFrame
    complete_visits_tuples: list[tuple]
    total_visits_processed: int
    complete_visits_count: int
    processing_time: float

    @property
    def completion_rate(self) -> float:
        """Calculate the completion rate as a percentage."""
        if self.total_visits_processed == 0:
            return 0.0
        return (self.complete_visits_count / self.total_visits_processed) * 100.0

    @property
    def has_complete_visits(self) -> bool:
        """Check if any complete visits were found."""
        return self.complete_visits_count > 0


@dataclass
class ValidationResult:
    """Result object for validation stage."""

    errors_df: pd.DataFrame
    logs_df: pd.DataFrame
    passed_df: pd.DataFrame
    validation_logs_df: pd.DataFrame
    all_records_df: pd.DataFrame
    validation_time: float
    instruments_processed: list[str]
    validation_summary: dict[str, Any]
    success: bool = True
    error_message: str | None = None

    @property
    def total_errors(self) -> int:
        """Total number of validation errors found."""
        return len(self.errors_df)

    @property
    def total_records_validated(self) -> int:
        """Total number of records validated."""
        return len(self.all_records_df)

    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage."""
        if self.total_records_validated == 0:
            return 0.0
        return (self.total_errors / self.total_records_validated) * 100.0

    def get_errors_for_instrument(self, instrument: str) -> pd.DataFrame:
        """Get errors for a specific instrument."""
        if self.errors_df.empty:
            return pd.DataFrame()
        return self.errors_df[self.errors_df.get("instrument_name", "") == instrument]


@dataclass
class ReportGenerationResult:
    """Result object for report generation stage."""

    generated_files: list[Path]
    export_time: float
    reports_created: dict[str, Path]
    success: bool = True
    failed_reports: list[str] = field(default_factory=list)
    error_messages: dict[str, str] = field(default_factory=dict)

    @property
    def total_files_created(self) -> int:
        """Total number of files created."""
        return len(self.generated_files)

    def get_report_path(self, report_type: str) -> Path | None:
        """Get path for a specific report type."""
        return self.reports_created.get(report_type)


@dataclass
class PipelineExecutionResult:
    """Complete pipeline execution result."""

    data_fetch: DataFetchResult
    rules_loading: RulesLoadingResult
    data_preparation: DataPreparationResult
    validation: ValidationResult
    report_generation: ReportGenerationResult
    total_execution_time: float
    output_directory: Path
    run_metadata: dict[str, Any]
    success: bool = True
    pipeline_error: str | None = None


