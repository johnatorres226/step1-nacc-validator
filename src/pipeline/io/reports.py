"""
Unified Report Generation Module

Provides a centralized ReportFactory class to consolidate and standardize
all report generation functionality, replacing multiple scattered functions
with a clean, maintainable approach.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import logging
from dataclasses import dataclass
from datetime import datetime

from .context import ProcessingContext, ExportConfiguration, ReportConfiguration

logger = logging.getLogger(__name__)


@dataclass
class ReportMetadata:
    """Metadata for generated reports."""
    report_type: str
    filename: str
    rows_exported: int
    file_size_mb: float
    export_timestamp: datetime


class ReportFactory:
    """
    Unified factory class for generating all types of pipeline reports.
    
    Consolidates the functionality from:
    - export_results_to_csv()
    - generate_aggregate_error_count_report()
    - generate_tool_status_reports()
    
    Provides consistent naming, formatting, and configuration management.
    """
    
    def __init__(self, processing_context: ProcessingContext):
        """
        Initialize report factory.
        
        Args:
            processing_context: Context object with data and configuration
        """
        self.context = processing_context
        self._generated_reports: List[ReportMetadata] = []
    
    def generate_error_report(
        self, 
        df_errors: pd.DataFrame,
        export_config: ExportConfiguration
    ) -> Optional[Path]:
        """
        Generate primary error dataset report.
        
        Args:
            df_errors: DataFrame containing all validation errors
            export_config: Export configuration
            
        Returns:
            Path to generated error report file or None if no errors
        """
        if df_errors.empty:
            logger.info("No validation errors found - skipping error report")
            return None
        
        # Create standardized filename
        filename = f"qc_errors_dataset_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "error_reports" / filename
        
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Export with consistent formatting
        df_errors.to_csv(output_path, index=False)
        
        # Track metadata
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        self._generated_reports.append(ReportMetadata(
            report_type="error_dataset",
            filename=filename,
            rows_exported=len(df_errors),
            file_size_mb=file_size_mb,
            export_timestamp=datetime.now()
        ))
        
        logger.info(f"Generated error report: {filename} ({len(df_errors)} errors)")
        return output_path
    
    def generate_validation_logs_report(
        self,
        df_logs: pd.DataFrame,
        export_config: ExportConfiguration
    ) -> Optional[Path]:
        """
        Generate comprehensive validation logs report.
        
        Args:
            df_logs: DataFrame containing all validation logs
            export_config: Export configuration
            
        Returns:
            Path to generated logs report file or None if no logs
        """
        if df_logs.empty:
            logger.info("No validation logs found - skipping logs report")
            return None
        
        filename = f"qc_validation_logs_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "validation_logs" / filename
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_logs.to_csv(output_path, index=False)
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        self._generated_reports.append(ReportMetadata(
            report_type="validation_logs",
            filename=filename,
            rows_exported=len(df_logs),
            file_size_mb=file_size_mb,
            export_timestamp=datetime.now()
        ))
        
        logger.info(f"Generated validation logs: {filename} ({len(df_logs)} entries)")
        return output_path
    
    def generate_passed_validations_report(
        self,
        df_passed: pd.DataFrame,
        export_config: ExportConfiguration
    ) -> Optional[Path]:
        """
        Generate passed validations report.
        
        Args:
            df_passed: DataFrame containing passed validations
            export_config: Export configuration
            
        Returns:
            Path to generated report file or None if not included
        """
        if not export_config.include_passed:
            logger.info("Passed validations export disabled - skipping")
            return None
            
        if df_passed.empty:
            logger.info("No passed validations found - skipping passed report")
            return None
        
        filename = f"qc_passed_validations_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "passed_validations" / filename
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df_passed.to_csv(output_path, index=False)
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        self._generated_reports.append(ReportMetadata(
            report_type="passed_validations",
            filename=filename,
            rows_exported=len(df_passed),
            file_size_mb=file_size_mb,
            export_timestamp=datetime.now()
        ))
        
        logger.info(f"Generated passed validations: {filename} ({len(df_passed)} entries)")
        return output_path
    
    def generate_aggregate_error_report(
        self,
        df_errors: pd.DataFrame,
        all_records_df: pd.DataFrame,
        export_config: ExportConfiguration,
        report_config: ReportConfiguration
    ) -> Path:
        """
        Generate aggregate error count report per subject/event.
        
        Args:
            df_errors: DataFrame containing all validation errors
            all_records_df: DataFrame containing all processed records
            export_config: Export configuration
            report_config: Report configuration
            
        Returns:
            Path to generated aggregate report file
        """
        # Calculate error counts per subject/event
        if df_errors.empty:
            error_counts = pd.DataFrame(columns=[report_config.primary_key_field, 'redcap_event_name', 'error_count'])
        else:
            error_counts = (df_errors.groupby([report_config.primary_key_field, 'redcap_event_name'])
                          .size()
                          .reset_index(name='error_count'))
        
        # Merge with all records to show zero counts
        aggregate_df = all_records_df[[report_config.primary_key_field, 'redcap_event_name']].merge(
            error_counts, 
            on=[report_config.primary_key_field, 'redcap_event_name'], 
            how='left'
        )
        aggregate_df['error_count'] = aggregate_df['error_count'].fillna(0).astype(int)
        
        # Add summary statistics
        aggregate_df['total_instruments'] = len(self.context.instrument_list)
        aggregate_df['qc_run_by'] = report_config.qc_run_by
        aggregate_df = aggregate_df.sort_values([report_config.primary_key_field, 'redcap_event_name'])
        
        # Export
        filename = f"qc_aggregate_error_counts_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "aggregate_reports" / filename
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        aggregate_df.to_csv(output_path, index=False)
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        self._generated_reports.append(ReportMetadata(
            report_type="aggregate_errors",
            filename=filename,
            rows_exported=len(aggregate_df),
            file_size_mb=file_size_mb,
            export_timestamp=datetime.now()
        ))
        
        logger.info(f"Generated aggregate error report: {filename} ({len(aggregate_df)} records)")
        return output_path
    
    def generate_status_report(
        self,
        all_records_df: pd.DataFrame,
        complete_visits_df: pd.DataFrame,
        detailed_validation_logs_df: pd.DataFrame,
        export_config: ExportConfiguration,
        report_config: ReportConfiguration
    ) -> Path:
        """
        Generate tool status and processing summary report.
        
        Args:
            all_records_df: DataFrame containing all processed records
            complete_visits_df: DataFrame of completed visits
            detailed_validation_logs_df: DataFrame of pre-validation logs
            export_config: Export configuration
            report_config: Report configuration
            
        Returns:
            Path to generated status report file
        """
        # Create comprehensive status report
        status_data = []
        
        # Processing summary
        status_data.append({
            'metric': 'total_records_processed',
            'value': len(all_records_df),
            'category': 'processing'
        })
        
        status_data.append({
            'metric': 'complete_visits_found',
            'value': len(complete_visits_df),
            'category': 'processing'
        })
        
        status_data.append({
            'metric': 'instruments_validated',
            'value': len(self.context.instrument_list),
            'category': 'validation'
        })
        
        # Validation summary from logs
        if not detailed_validation_logs_df.empty:
            status_data.append({
                'metric': 'pre_validation_logs',
                'value': len(detailed_validation_logs_df),
                'category': 'validation'
            })
        
        # Tool configuration
        status_data.append({
            'metric': 'primary_key_field',
            'value': report_config.primary_key_field,
            'category': 'configuration'
        })
        
        status_data.append({
            'metric': 'qc_run_by',
            'value': report_config.qc_run_by,
            'category': 'configuration'
        })
        
        # Create DataFrame and export
        status_df = pd.DataFrame(status_data)
        status_df['timestamp'] = datetime.now().isoformat()
        status_df['run_date'] = export_config.date_tag
        status_df['run_time'] = export_config.time_tag
        
        filename = f"qc_tool_status_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "status_reports" / filename
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        status_df.to_csv(output_path, index=False)
        
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        self._generated_reports.append(ReportMetadata(
            report_type="tool_status",
            filename=filename,
            rows_exported=len(status_df),
            file_size_mb=file_size_mb,
            export_timestamp=datetime.now()
        ))
        
        logger.info(f"Generated status report: {filename} ({len(status_df)} metrics)")
        return output_path
    
    def export_all_reports(
        self,
        df_errors: pd.DataFrame,
        df_logs: pd.DataFrame,
        df_passed: pd.DataFrame,
        all_records_df: pd.DataFrame,
        complete_visits_df: pd.DataFrame,
        detailed_validation_logs_df: pd.DataFrame,
        export_config: ExportConfiguration,
        report_config: ReportConfiguration
    ) -> List[Path]:
        """
        Export all reports with consistent naming and structure.
        
        Args:
            df_errors: DataFrame of all validation errors
            df_logs: DataFrame of comprehensive validation logs
            df_passed: DataFrame of all passed validations
            all_records_df: DataFrame with info on all processed records
            complete_visits_df: DataFrame of completed visits
            detailed_validation_logs_df: DataFrame of pre-validation logs
            export_config: Export configuration
            report_config: Report configuration
            
        Returns:
            List of paths to generated report files
        """
        logger.info("Starting unified report generation...")
        generated_files = []
        
        # Generate all report types
        error_path = self.generate_error_report(df_errors, export_config)
        if error_path:
            generated_files.append(error_path)
        
        logs_path = self.generate_validation_logs_report(df_logs, export_config)
        if logs_path:
            generated_files.append(logs_path)
        
        passed_path = self.generate_passed_validations_report(df_passed, export_config)
        if passed_path:
            generated_files.append(passed_path)
        
        aggregate_path = self.generate_aggregate_error_report(
            df_errors, all_records_df, export_config, report_config
        )
        generated_files.append(aggregate_path)
        
        status_path = self.generate_status_report(
            all_records_df, complete_visits_df, detailed_validation_logs_df,
            export_config, report_config
        )
        generated_files.append(status_path)
        
        # Create summary report of all generated files
        self._create_generation_summary(export_config)
        
        logger.info(f"Report generation complete: {len(generated_files)} files created")
        return generated_files
    
    def _create_generation_summary(self, export_config: ExportConfiguration) -> Path:
        """Create a summary of all generated reports."""
        summary_df = pd.DataFrame([
            {
                'report_type': report.report_type,
                'filename': report.filename,
                'rows_exported': report.rows_exported,
                'file_size_mb': f"{report.file_size_mb:.2f}",
                'export_timestamp': report.export_timestamp.isoformat()
            }
            for report in self._generated_reports
        ])
        
        filename = f"qc_generation_summary_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / filename
        
        summary_df.to_csv(output_path, index=False)
        logger.info(f"Created generation summary: {filename}")
        
        return output_path
    
    def get_report_statistics(self) -> Dict[str, Any]:
        """Get statistics about generated reports."""
        if not self._generated_reports:
            return {'total_reports': 0, 'total_rows': 0, 'total_size_mb': 0.0}
        
        total_rows = sum(r.rows_exported for r in self._generated_reports)
        total_size = sum(r.file_size_mb for r in self._generated_reports)
        
        return {
            'total_reports': len(self._generated_reports),
            'total_rows': total_rows,
            'total_size_mb': f"{total_size:.2f}",
            'report_types': list(set(r.report_type for r in self._generated_reports))
        }


# Legacy compatibility functions for backward compatibility
def create_legacy_export_results_to_csv(
    df_errors: pd.DataFrame,
    df_logs: pd.DataFrame,
    df_passed: pd.DataFrame,
    all_records_df: pd.DataFrame,
    complete_visits_df: pd.DataFrame,
    detailed_validation_logs_df: pd.DataFrame,
    output_dir: Path,
    date_tag: str,
    time_tag: str,
    processing_context: ProcessingContext,
    report_config: ReportConfiguration
) -> List[Path]:
    """
    Legacy compatibility wrapper for export_results_to_csv.
    
    This function maintains the old interface while using the new ReportFactory.
    """
    export_config = ExportConfiguration(
        output_dir=output_dir,
        date_tag=date_tag,
        time_tag=time_tag
    )
    
    factory = ReportFactory(processing_context)
    return factory.export_all_reports(
        df_errors, df_logs, df_passed, all_records_df,
        complete_visits_df, detailed_validation_logs_df,
        export_config, report_config
    )
