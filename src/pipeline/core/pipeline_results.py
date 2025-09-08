"""
Pipeline result objects and improved data models for the QC pipeline.

This module provides structured data models for pipeline stages, replacing loose
variables with proper result objects that encapsulate state and provide clear
interfaces between pipeline steps.
"""
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    source_info: Dict[str, Any]
    fetch_timestamp: datetime
    success: bool = True
    error_message: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        """Check if fetched data is empty."""
        return self.data.empty

    def validate(self) -> None:
        """Validate the fetch result."""
        if not self.success and self.error_message is None:
            raise ValueError("Failed fetch result must have error message")
        if self.success and self.data.empty:
            import logging
            logging.getLogger(__name__).warning("Successful fetch but no data returned")


@dataclass
class RulesLoadingResult:
    """Result object for rules loading stage."""
    rules_cache: Dict[str, Dict[str, Any]]
    instruments_processed: List[str]
    loading_time: float
    variable_to_instrument_map: Dict[str, str]
    instrument_to_variables_map: Dict[str, List[str]]
    success: bool = True
    failed_instruments: List[str] = field(default_factory=list)
    error_messages: Dict[str, str] = field(default_factory=dict)

    @property
    def loaded_instruments_count(self) -> int:
        """Number of instruments successfully loaded."""
        return len(self.instruments_processed) - len(self.failed_instruments)

    def get_rules_for_instrument(self, instrument: str) -> Dict[str, Any]:
        """Get rules for a specific instrument."""
        return self.rules_cache.get(instrument, {})

    def validate(self) -> None:
        """Validate the rules loading result."""
        if not self.success and not self.failed_instruments:
            raise ValueError("Failed rules loading must specify failed instruments")


@dataclass
class DataPreparationResult:
    """Result object for data preparation stage."""
    instrument_data_cache: Dict[str, pd.DataFrame]
    complete_visits_data: Optional['CompleteVisitsResult']
    preparation_time: float
    records_per_instrument: Dict[str, int]
    success: bool = True
    error_message: Optional[str] = None

    @property
    def total_records_prepared(self) -> int:
        """Total number of records across all instruments."""
        return sum(self.records_per_instrument.values())

    @property
    def instruments_with_data(self) -> List[str]:
        """List of instruments that have data after preparation."""
        return [inst for inst, count in self.records_per_instrument.items()
                if count > 0]

    def get_instrument_data(self, instrument: str) -> pd.DataFrame:
        """Get prepared data for a specific instrument."""
        return self.instrument_data_cache.get(instrument, pd.DataFrame())


@dataclass
class CompleteVisitsResult:
    """Result object for complete visits processing."""
    summary_dataframe: pd.DataFrame
    complete_visits_tuples: List[tuple]
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
    instruments_processed: List[str]
    validation_summary: Dict[str, Any]
    success: bool = True
    error_message: Optional[str] = None

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
        return self.errors_df[self.errors_df.get('instrument_name', '') == instrument]


@dataclass
class ReportGenerationResult:
    """Result object for report generation stage."""
    generated_files: List[Path]
    export_time: float
    reports_created: Dict[str, Path]
    success: bool = True
    failed_reports: List[str] = field(default_factory=list)
    error_messages: Dict[str, str] = field(default_factory=dict)

    @property
    def total_files_created(self) -> int:
        """Total number of files created."""
        return len(self.generated_files)

    def get_report_path(self, report_type: str) -> Optional[Path]:
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
    run_metadata: Dict[str, Any]
    success: bool = True
    pipeline_error: Optional[str] = None

    @property
    def pipeline_summary(self) -> Dict[str, Any]:
        """Generate a summary of the entire pipeline execution."""
        return {
            "success": self.success,
            "total_execution_time": self.total_execution_time,
            "records_processed": self.data_fetch.records_processed,
            "instruments_processed": len(self.rules_loading.instruments_processed),
            "total_errors": self.validation.total_errors,
            "error_rate": self.validation.error_rate,
            "reports_generated": self.report_generation.total_files_created,
            "output_directory": str(self.output_directory),
            "pipeline_stages": {
                "data_fetch": {
                    "success": self.data_fetch.success,
                    "execution_time": self.data_fetch.execution_time,
                    "records": self.data_fetch.records_processed
                },
                "rules_loading": {
                    "success": self.rules_loading.success,
                    "execution_time": self.rules_loading.loading_time,
                    "instruments_loaded": self.rules_loading.loaded_instruments_count
                },
                "data_preparation": {
                    "success": self.data_preparation.success,
                    "execution_time": self.data_preparation.preparation_time,
                    "records_prepared": self.data_preparation.total_records_prepared
                },
                "validation": {
                    "success": self.validation.success,
                    "execution_time": self.validation.validation_time,
                    "errors_found": self.validation.total_errors
                },
                "report_generation": {
                    "success": self.report_generation.success,
                    "execution_time": self.report_generation.export_time,
                    "files_created": self.report_generation.total_files_created
                }
            }
        }

    def validate(self) -> None:
        """Validate the complete pipeline result."""
        if not self.success and self.pipeline_error is None:
            raise ValueError("Failed pipeline execution must have error message")

        # Validate individual stages
        try:
            self.data_fetch.validate()
            self.rules_loading.validate()
        except Exception as e:
            raise ValueError(f"Pipeline result validation failed: {e}") from e


# =============================================================================
# PIPELINE STAGE ERROR CLASSES
# =============================================================================

class PipelineStageError(Exception):
    """Base exception for pipeline stage errors."""

    def __init__(
            self,
            stage: str,
            message: str,
            original_error: Optional[Exception] = None):
        self.stage = stage
        self.original_error = original_error
        super().__init__(f"Pipeline stage '{stage}' failed: {message}")


class DataFetchError(PipelineStageError):
    """Error during data fetching stage."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__("data_fetch", message, original_error)


class RulesLoadingError(PipelineStageError):
    """Error during rules loading stage."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__("rules_loading", message, original_error)


class DataPreparationError(PipelineStageError):
    """Error during data preparation stage."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__("data_preparation", message, original_error)


class ValidationError(PipelineStageError):
    """Error during validation stage."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__("validation", message, original_error)


class ReportGenerationError(PipelineStageError):
    """Error during report generation stage."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__("report_generation", message, original_error)
