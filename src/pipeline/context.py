"""
Configuration dataclasses for pipeline processing.

This module provides structured configuration objects to reduce function parameter
complexity and improve maintainability across the pipeline.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd

from .config_manager import QCConfig


@dataclass
class ProcessingContext:
    """
    Context object containing all data and configuration needed for processing.
    
    This replaces passing multiple parameters to processing functions,
    improving maintainability and reducing parameter complexity.
    """
    data_df: pd.DataFrame
    instrument_list: List[str]
    rules_cache: Dict[str, Any]
    primary_key_field: str
    config: QCConfig
    
    @property
    def is_empty(self) -> bool:
        """Check if the data DataFrame is empty."""
        return self.data_df.empty
    
    def get_instrument_variables(self, instrument: str) -> List[str]:
        """Get variables for a specific instrument from the rules cache."""
        return list(self.rules_cache.get(instrument, {}).keys())
    
    def filter_to_instruments(self, instruments: List[str]) -> 'ProcessingContext':
        """Create a new context filtered to specific instruments."""
        return ProcessingContext(
            data_df=self.data_df,
            instrument_list=[inst for inst in instruments if inst in self.instrument_list],
            rules_cache={inst: rules for inst, rules in self.rules_cache.items() if inst in instruments},
            primary_key_field=self.primary_key_field,
            config=self.config
        )


@dataclass
class ExportConfiguration:
    """
    Configuration for exporting results and reports.
    
    This standardizes export parameters across different report generation functions.
    """
    output_dir: Path
    date_tag: str
    time_tag: str
    include_logs: bool = True
    include_passed: bool = True
    include_detailed_logs: bool = True
    file_prefix: str = "QC"
    
    @property
    def file_suffix(self) -> str:
        """Generate consistent file suffix from date and time tags."""
        return f"{self.date_tag}_{self.time_tag}"
    
    def get_validation_logs_dir(self) -> Path:
        """Get the validation logs subdirectory."""
        logs_dir = self.output_dir / "Validation_Logs"
        logs_dir.mkdir(exist_ok=True)
        return logs_dir
    
    def get_report_filename(self, report_type: str) -> str:
        """Generate standardized report filename."""
        return f"{self.file_prefix}_{report_type}_{self.file_suffix}.csv"


@dataclass
class ValidationContext:
    """
    Context object for validation operations.
    
    This provides validation-specific configuration and utilities.
    """
    instrument_name: str
    primary_key_field: str
    validation_rules: Dict[str, Any]
    event_name: Optional[str] = None
    include_temporal_rules: bool = False
    include_compatibility_rules: bool = True
    
    @property
    def is_dynamic_instrument(self) -> bool:
        """Check if this is a dynamic rule instrument."""
        from .config_manager import is_dynamic_rule_instrument
        return is_dynamic_rule_instrument(self.instrument_name)
    
    def get_discriminant_variable(self) -> Optional[str]:
        """Get discriminant variable for dynamic instruments."""
        if self.is_dynamic_instrument:
            from .config_manager import get_discriminant_variable
            return get_discriminant_variable(self.instrument_name)
        return None


@dataclass
class AnalyticsConfiguration:
    """
    Configuration for data quality analytics and debugging.
    
    This provides structured configuration for analysis operations.
    """
    verbosity_level: str = "normal"  # "minimal", "normal", "detailed", "debug"
    include_coverage_analysis: bool = True
    include_orphaned_columns: bool = True
    include_missing_variables: bool = True
    max_variables_to_show: int = 10
    
    @property
    def is_debug_mode(self) -> bool:
        """Check if debug mode is enabled."""
        return self.verbosity_level == "debug"
    
    @property
    def is_minimal_mode(self) -> bool:
        """Check if minimal output mode is enabled."""
        return self.verbosity_level == "minimal"


@dataclass
class ReportConfiguration:
    """
    Configuration for unified report generation.
    
    This standardizes report generation settings across different report types.
    """
    qc_run_by: str
    primary_key_field: str
    instruments: List[str]
    generate_error_report: bool = True
    generate_status_report: bool = True
    generate_aggregate_report: bool = True
    generate_json_export: bool = True
    export_config: Optional[ExportConfiguration] = None
    
    def get_status_columns(self) -> List[str]:
        """Get standard columns for status reports."""
        return [
            self.primary_key_field,
            "redcap_event_name",
            "qc_status_complete",
            "qc_run_by", 
            "qc_last_run",
            "qc_status",
            "quality_control_check_complete"
        ]
