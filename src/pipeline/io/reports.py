"""
Unified Report Generation Module

Provides a centralized ReportFactory class to consolidate and standardize
all report generation functionality, replacing multiple scattered functions
with a clean, maintainable approach.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .context import ExportConfiguration, ProcessingContext, ReportConfiguration

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
        filename = f"Final_Error_Dataset_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "Errors" / filename

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
        Generate Event Completeness Screening log report.
        
        Format: ptid, redcap_event_name, instrument_name, target_variable, completeness_status, processing_status, pass_fail, error
        """
        if df_logs.empty:
            logger.info("No validation logs found - skipping logs report")
            return None

        filename = f"Log_EventCompletenessScreening_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "Validation_Logs" / filename

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
        Generate passed validations report with detailed rule information.
        
        Format: ptid, variable, current_value, json_rule, rule_file, redcap_event_name, instrument_name
        """
        if not export_config.include_passed:
            logger.info("Passed validations export disabled - skipping")
            return None

        if df_passed.empty:
            logger.info("No passed validations found - skipping passed report")
            return None

        filename = f"Log_PassedValidations_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "Validation_Logs" / filename

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
        Generate aggregate error count report per subject/event with error counts per instrument.
        
        Format: ptid, redcap_event_name, [instrument columns with error counts], total_error_count
        """
        # Get all instruments from config
        from ..config_manager import get_instruments
        instruments = get_instruments()

        # Get unique participants and events (remove duplicates from all_records_df)
        unique_records = all_records_df[[report_config.primary_key_field, 'redcap_event_name']].drop_duplicates()

        # Initialize result with unique participants and events
        result_df = unique_records.copy()

        # Initialize all instrument columns with 0
        for instrument in instruments:
            result_df[instrument] = 0

        # Count errors per instrument per participant/event
        if not df_errors.empty:
            error_counts = df_errors.groupby([
                report_config.primary_key_field,
                'redcap_event_name',
                'instrument_name'
            ]).size().reset_index(name='error_count')

            # Pivot to get instruments as columns
            for _, row in error_counts.iterrows():
                mask = (
                    (result_df[report_config.primary_key_field] == row[report_config.primary_key_field]) &
                    (result_df['redcap_event_name'] == row['redcap_event_name'])
                )
                if row['instrument_name'] in instruments:
                    result_df.loc[mask, row['instrument_name']] = row['error_count']

        # Calculate total error count
        instrument_cols = [col for col in result_df.columns if col in instruments]
        result_df['total_error_count'] = result_df[instrument_cols].sum(axis=1)

        # Sort by ptid and event
        result_df = result_df.sort_values([report_config.primary_key_field, 'redcap_event_name'])

        # Export
        filename = f"QC_Report_ErrorCount_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "Reports" / filename

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(output_path, index=False)

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        self._generated_reports.append(ReportMetadata(
            report_type="aggregate_errors",
            filename=filename,
            rows_exported=len(result_df),
            file_size_mb=file_size_mb,
            export_timestamp=datetime.now()
        ))

        logger.info(f"Generated aggregate error report: {filename} ({len(result_df)} records)")
        return output_path

    def generate_status_report(
        self,
        all_records_df: pd.DataFrame,
        complete_visits_df: pd.DataFrame,
        detailed_validation_logs_df: pd.DataFrame,
        export_config: ExportConfiguration,
        report_config: ReportConfiguration,
        df_errors: pd.DataFrame
    ) -> Path:
        """
        Generate QC Status Report with Pass/Fail status per instrument per participant.
        
        Format: ptid, redcap_event_name, [instrument Pass/Fail columns], qc_status_complete, qc_run_by, qc_last_run, qc_status, quality_control_check_complete
        """
        from ..config_manager import get_instruments
        instruments = get_instruments()

        # Get unique participants and events (remove duplicates from all_records_df)
        unique_records = all_records_df[[report_config.primary_key_field, 'redcap_event_name']].drop_duplicates()

        # Initialize result with unique participants and events
        result_df = unique_records.copy()

        # Initialize all instrument columns with "Pass"
        for instrument in instruments:
            result_df[instrument] = "Pass"

        # Mark instruments with errors as "Fail"
        if not df_errors.empty:
            error_groups = df_errors.groupby([
                report_config.primary_key_field,
                'redcap_event_name',
                'instrument_name'
            ]).size().reset_index(name='error_count')

            for _, row in error_groups.iterrows():
                mask = (
                    (result_df[report_config.primary_key_field] == row[report_config.primary_key_field]) &
                    (result_df['redcap_event_name'] == row['redcap_event_name'])
                )
                if row['instrument_name'] in instruments:
                    result_df.loc[mask, row['instrument_name']] = "Fail"

        # Add QC status columns
        result_df['qc_status_complete'] = 0
        result_df['qc_run_by'] = report_config.qc_run_by
        result_df['qc_last_run'] = datetime.now().strftime("%Y-%m-%d")

        # Generate qc_status based on failed instruments
        def get_qc_status(row):
            failed_instruments = []
            for instrument in instruments:
                if row[instrument] == "Fail":
                    failed_instruments.append(instrument)

            if failed_instruments:
                return f"Failed in instruments: {', '.join(failed_instruments)}"
            else:
                return "Pass"

        result_df['qc_status'] = result_df.apply(get_qc_status, axis=1)
        result_df['quality_control_check_complete'] = 0

        # Sort by ptid and event
        result_df = result_df.sort_values([report_config.primary_key_field, 'redcap_event_name'])

        # Export

        filename = f"QC_Status_Report_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "Reports" / filename

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(output_path, index=False)

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        self._generated_reports.append(ReportMetadata(
            report_type="tool_status",
            filename=filename,
            rows_exported=len(result_df),
            file_size_mb=file_size_mb,
            export_timestamp=datetime.now()
        ))

        logger.info(f"Generated status report: {filename} ({len(result_df)} metrics)")
        return output_path

    def generate_ptid_completed_visits_report(
        self,
        complete_visits_df: pd.DataFrame,
        export_config: ExportConfiguration,
        report_config: ReportConfiguration
    ) -> Path:
        """
        Generate PTID Completed Visits report.
        
        Format: ptid, redcap_event_name, packet, complete_instruments_count, completion_status
        """
        from ..config_manager import get_instruments
        instruments = get_instruments()

        # Get unique participants, events, and packets (remove duplicates while preserving packet info)
        unique_records = complete_visits_df[[report_config.primary_key_field, 'redcap_event_name', 'packet']].drop_duplicates()

        # Calculate completed instruments count
        result_df = unique_records.copy()
        result_df['complete_instruments_count'] = len(instruments) - 1  # Exclude quality_control_check
        result_df['completion_status'] = 'All Complete'

        # Sort by ptid and event
        result_df = result_df.sort_values([report_config.primary_key_field, 'redcap_event_name'])

        # Export
        filename = f"PTID_CompletedVisits_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "Completed_Visits" / filename

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(output_path, index=False)

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        self._generated_reports.append(ReportMetadata(
            report_type="ptid_completed_visits",
            filename=filename,
            rows_exported=len(result_df),
            file_size_mb=file_size_mb,
            export_timestamp=datetime.now()
        ))

        logger.info(f"Generated PTID completed visits report: {filename} ({len(result_df)} records)")
        return output_path

    def generate_rules_validation_log(
        self,
        all_records_df: pd.DataFrame,
        export_config: ExportConfiguration,
        report_config: ReportConfiguration
    ) -> Path:
        """
        Generate Rules Validation log with all validation rules that were checked.
        
        Format: ptid, variable, json_rule, json_rule_path, redcap_event_name, instrument_name
        """
        # This would need to be populated during validation - for now create a basic structure
        # Import validation rules and create entries for all variables
        from ..config_manager import (
            get_config,
            get_instruments,
        )
        from ..utils.instrument_mapping import load_json_rules_for_instrument

        instruments = get_instruments()
        config = get_config()
        records = []

        for _, record in all_records_df.iterrows():
            ptid = record[report_config.primary_key_field]
            event = record['redcap_event_name']
            packet_value = record.get('packet', 'unknown')

            for instrument in instruments:
                try:
                    rules = load_json_rules_for_instrument(instrument)
                    # Get the full rules path based on packet type
                    rules_path = config.get_rules_path_for_packet(packet_value) if packet_value != 'unknown' else config.json_rules_path_i

                    for variable, rule_data in rules.items():
                        records.append({
                            'ptid': ptid,
                            'variable': variable,
                            'json_rule': str(rule_data),
                            'json_rule_path': rules_path,
                            'redcap_event_name': event,
                            'instrument_name': instrument
                        })
                except Exception as e:
                    logger.warning(f"Could not load rules for instrument {instrument}: {e}")
                    continue

        result_df = pd.DataFrame(records)

        # Export
        filename = f"Log_RulesValidation_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "Validation_Logs" / filename

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_df.to_csv(output_path, index=False)

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        self._generated_reports.append(ReportMetadata(
            report_type="rules_validation_log",
            filename=filename,
            rows_exported=len(result_df),
            file_size_mb=file_size_mb,
            export_timestamp=datetime.now()
        ))

        logger.info(f"Generated rules validation log: {filename} ({len(result_df)} records)")
        return output_path

    def generate_json_status_report(
        self,
        status_report_path: Path,
        export_config: ExportConfiguration
    ) -> Path:
        """
        Generate JSON report from the QC Status Report CSV and save to UPLOAD_READY_PATH.
        """
        import json

        from ..config_manager import get_config

        # Read the CSV status report
        status_df = pd.read_csv(status_report_path)

        # Convert to JSON format
        json_data = {
            "qc_run_metadata": {
                "run_date": export_config.date_tag,
                "run_time": export_config.time_tag,
                "total_participants": len(status_df)
            },
            "participant_status": []
        }

        for _, row in status_df.iterrows():
            participant_data = {
                "ptid": row['ptid'],
                "redcap_event_name": row['redcap_event_name'],
                "qc_status": row['qc_status'],
                "qc_run_by": row['qc_run_by'],
                "qc_last_run": row['qc_last_run'],
                "instruments": {}
            }

            # Add instrument status
            from ..config_manager import get_instruments
            instruments = get_instruments()
            for instrument in instruments:
                if instrument in row:
                    participant_data["instruments"][instrument] = row[instrument]

            json_data["participant_status"].append(participant_data)

        # Get upload ready path from config
        config = get_config()
        if config.upload_ready_path:
            upload_dir = Path(config.upload_ready_path)
            upload_dir.mkdir(parents=True, exist_ok=True)
            output_path = upload_dir / f"QC_Status_Report_{export_config.date_tag}_{export_config.time_tag}.json"
        else:
            # Fallback to export_config output_dir if no upload path configured
            output_path = export_config.output_dir / f"QC_Status_Report_{export_config.date_tag}_{export_config.time_tag}.json"

        with open(output_path, 'w') as f:
            json.dump(json_data, f, indent=2)

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        self._generated_reports.append(ReportMetadata(
            report_type="json_status_report",
            filename=output_path.name,
            rows_exported=len(status_df),
            file_size_mb=file_size_mb,
            export_timestamp=datetime.now()
        ))

        logger.info(f"Generated JSON status report: {output_path}")
        return output_path

    def _generate_data_fetched_report(
        self,
        all_records_df: pd.DataFrame,
        export_config: ExportConfiguration
    ) -> Optional[Path]:
        """
        Generate Data_Fetched report containing all fetched records.
        
        Args:
            all_records_df: DataFrame containing all fetched records
            export_config: Export configuration
            
        Returns:
            Path to generated Data_Fetched report file or None if no data
        """
        if all_records_df.empty:
            logger.info("No fetched data found - skipping Data_Fetched report")
            return None

        # Create standardized filename
        filename = f"Data_Fetched_{export_config.date_tag}_{export_config.time_tag}.csv"
        output_path = export_config.output_dir / "Data_Fetched" / filename

        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Export with consistent formatting
        all_records_df.to_csv(output_path, index=False)

        # Track metadata
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        self._generated_reports.append(ReportMetadata(
            report_type="data_fetched",
            filename=filename,
            rows_exported=len(all_records_df),
            file_size_mb=file_size_mb,
            export_timestamp=datetime.now()
        ))

        logger.info(f"Generated Data_Fetched report: {filename} ({len(all_records_df)} records)")
        return output_path

    def _generate_basic_json_report(
        self,
        all_records_df: pd.DataFrame,
        df_errors: pd.DataFrame,
        export_config: ExportConfiguration
    ) -> Path:
        """
        Generate basic JSON status report for default run mode.
        
        Args:
            all_records_df: DataFrame containing all fetched records
            df_errors: DataFrame containing validation errors
            export_config: Export configuration
            
        Returns:
            Path to generated JSON report file
        """
        import json

        from ..config_manager import get_config

        # Create basic JSON structure
        json_data = {
            "report_type": "basic_qc_status",
            "generation_timestamp": datetime.now().isoformat(),
            "run_mode": "standard",
            "summary": {
                "total_records_fetched": len(all_records_df),
                "total_validation_errors": len(df_errors),
                "participants_with_errors": len(df_errors['ptid'].unique()) if not df_errors.empty else 0
            },
            "files_generated": [
                "Errors/",
                "Data_Fetched/",
                "QC_Status_Report.json"
            ]
        }

        # Get output path
        config = get_config()
        if config.upload_ready_path:
            upload_dir = Path(config.upload_ready_path)
            upload_dir.mkdir(parents=True, exist_ok=True)
            output_path = upload_dir / f"QC_Status_Report_{export_config.date_tag}_{export_config.time_tag}.json"
        else:
            # Fallback to export_config output_dir if no upload path configured
            output_path = export_config.output_dir / f"QC_Status_Report_{export_config.date_tag}_{export_config.time_tag}.json"

        with open(output_path, 'w') as f:
            json.dump(json_data, f, indent=2)

        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        self._generated_reports.append(ReportMetadata(
            report_type="basic_json_status",
            filename=output_path.name,
            rows_exported=0,  # Not applicable for summary report
            file_size_mb=file_size_mb,
            export_timestamp=datetime.now()
        ))

        logger.info(f"Generated basic JSON status report: {output_path.name}")
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

        # Check if detailed run is enabled
        detailed_run = getattr(self.context.config, 'detailed_run', False) if self.context.config else False

        # Always generate core outputs: Errors, Data_Fetched (all_records), and Json files
        error_path = self.generate_error_report(df_errors, export_config)
        if error_path:
            generated_files.append(error_path)

        # Generate Data_Fetched report (this is the all_records_df data)
        data_fetched_path = self._generate_data_fetched_report(all_records_df, export_config)
        if data_fetched_path:
            generated_files.append(data_fetched_path)

        # Always generate basic JSON status report
        json_path = self._generate_basic_json_report(all_records_df, df_errors, export_config)
        generated_files.append(json_path)

        # Only generate detailed outputs if detailed_run flag is set
        if detailed_run:
            logger.info("Detailed run mode enabled - generating additional reports...")

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
                export_config, report_config, df_errors
            )
            generated_files.append(status_path)

            # Generate PTID Completed Visits report
            ptid_path = self.generate_ptid_completed_visits_report(
                complete_visits_df, export_config, report_config
            )
            generated_files.append(ptid_path)

            # Generate Rules Validation log (only if passed_rules flag is enabled)
            passed_rules_enabled = getattr(self.context.config, 'passed_rules', False) if self.context.config else False
            if passed_rules_enabled:
                logger.info("Passed rules flag enabled - generating comprehensive Rules Validation log...")
                rules_log_path = self.generate_rules_validation_log(
                    all_records_df, export_config, report_config
                )
                generated_files.append(rules_log_path)
            else:
                logger.info("Passed rules flag disabled - skipping Rules Validation log (use --passed-rules/-ps to generate)")

            # Generate detailed JSON status report (requires status report to be created first)
            detailed_json_path = self.generate_json_status_report(status_path, export_config)
            generated_files.append(detailed_json_path)

            # Create detailed generation summary report
            self._create_generation_summary(export_config)
        else:
            logger.info("Standard run mode - generating core outputs only (Errors, Data_Fetched, Json)")

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

        filename = f"Generation_Summary_{export_config.date_tag}_{export_config.time_tag}.csv"
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
