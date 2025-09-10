"""
Improved pipeline orchestrator with clear stages, proper error handling, and result objects.

This module provides a structured approach to running the QC pipeline with explicit
stage separation, comprehensive error handling, and proper data flow tracking.
"""
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..config_manager import QCConfig
from ..logging_config import get_logger
from .pipeline_results import (
    CompleteVisitsResult,
    DataFetchError,
    DataFetchResult,
    DataPreparationError,
    DataPreparationResult,
    PipelineExecutionResult,
    ReportGenerationError,
    ReportGenerationResult,
    RulesLoadingError,
    RulesLoadingResult,
    ValidationError,
    ValidationResult,
)

logger = get_logger(__name__)


class PipelineOrchestrator:
    """
    Orchestrates the QC pipeline execution with clear stage separation and error handling.

    This class implements the improved pipeline structure with:
    - Clear pipeline steps with explicit data passing
    - Proper result objects instead of loose variables
    - Pipeline-level error handling and recovery
    - Comprehensive logging and monitoring
    """

    def __init__(self, config: QCConfig):
        """
        Initialize the pipeline orchestrator.

        Args:
            config: QC configuration object
        """
        self.config = config
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.start_time = None

    def run_pipeline(
        self,
        output_path: str | Path | None = None,
        date_tag: str | None = None,
        time_tag: str | None = None
    ) -> PipelineExecutionResult:
        """
        Execute the complete QC pipeline with structured stages.

        Args:
            output_path: Optional output path override
            date_tag: Optional date tag for output directory
            time_tag: Optional time tag for output directory

        Returns:
            Complete pipeline execution result with all stage results
        """
        self.start_time = time.time()

        # Create output directory
        output_dir = self._create_output_directory(
            output_path, date_tag, time_tag)

        self.logger.info("Starting QC pipeline")
        self.logger.info(
            "Configuration: %d instruments, mode: %s",
            len(self.config.instruments),
            self.config.mode,
        )
        self.logger.info("Output directory: %s", output_dir)

        try:
            # Stage 1: Data Fetching
            self.logger.info("Stage 1: Data Fetching")
            data_fetch_result = self._execute_data_fetch_stage(
                output_dir, date_tag, time_tag)
            self.logger.info(
                "Data fetch completed: %d records in %.2fs",
                data_fetch_result.records_processed,
                data_fetch_result.execution_time,
            )

            # Stage 2: Rules Loading
            self.logger.info("Stage 2: Rules Loading")
            rules_loading_result = self._execute_rules_loading_stage()
            self.logger.info(
                "Rules loading completed: %d/%d instruments in %.2fs",
                rules_loading_result.loaded_instruments_count,
                len(self.config.instruments),
                rules_loading_result.loading_time,
            )

            # Stage 3: Data Preparation
            self.logger.info("Stage 3: Data Preparation")
            data_prep_result = self._execute_data_preparation_stage(
                data_fetch_result, rules_loading_result
            )
            self.logger.info(
                "Data preparation completed: %d records prepared in %.2fs",
                data_prep_result.total_records_prepared,
                data_prep_result.preparation_time,
            )

            # Stage 4: Validation
            self.logger.info("Stage 4: Validation Processing")
            validation_result = self._execute_validation_stage(
                data_prep_result, rules_loading_result
            )
            self.logger.info(
                "Validation completed: %d errors found in %.2fs",
                validation_result.total_errors,
                validation_result.validation_time,
            )

            # Stage 5: Report Generation
            self.logger.info("Stage 5: Report Generation")
            report_result = self._execute_report_generation_stage(
                validation_result, data_prep_result, output_dir, date_tag, time_tag)
            self.logger.info(
                "Report generation completed: %d files created in %.2fs",
                report_result.total_files_created,
                report_result.export_time,
            )

            # Create final result
            total_time = time.time() - self.start_time

            result = PipelineExecutionResult(
                data_fetch=data_fetch_result,
                rules_loading=rules_loading_result,
                data_preparation=data_prep_result,
                validation=validation_result,
                report_generation=report_result,
                total_execution_time=total_time,
                output_directory=output_dir,
                run_metadata=self._create_run_metadata(),
                success=True
            )

            self.logger.info("Pipeline execution completed successfully")
            self.logger.info("Total execution time: %.2fs", total_time)
            self.logger.info("Output directory: %s", output_dir)

            return result

        except Exception as e:
            total_time = time.time() - self.start_time if self.start_time else 0
            self.logger.exception("Pipeline execution failed: %s", e)

            # Create failed result with whatever stages completed
            failed_result = self._create_failed_result(
                e, total_time, output_dir)

            self.logger.error("Pipeline execution failed")
            self.logger.error("Error: %s", e)
            self.logger.error("Execution time: %.2fs", total_time)

            return failed_result

    def _create_output_directory(
        self,
        output_path: str | Path | None,
        date_tag: str | None,
        time_tag: str | None
    ) -> Path:
        """Create output directory with proper naming."""
        if date_tag is None or time_tag is None:
            current_datetime = datetime.now()
            date_tag = date_tag or current_datetime.strftime("%d%b%Y").upper()
            time_tag = time_tag or current_datetime.strftime("%H%M%S")

        run_type_str = self.config.mode.replace(
            "_", " ").title().replace(" ", "")
        run_dir_name = f"QC_{run_type_str}_{date_tag}_{time_tag}"

        base_path = Path(output_path) if output_path else Path(
            self.config.output_path)
        output_dir = base_path / run_dir_name
        output_dir.mkdir(parents=True, exist_ok=True)

        return output_dir

    def _execute_data_fetch_stage(
        self,
        output_dir: Path,
        date_tag: str | None,
        time_tag: str | None
    ) -> DataFetchResult:
        """Execute the data fetching stage."""
        try:
            from .fetcher import RedcapETLPipeline

            stage_start = time.time()

            self.logger.info("Initializing REDCap ETL Pipeline...")
            pipeline = RedcapETLPipeline(self.config)

            self.logger.info("Fetching data from REDCap...")
            etl_result = pipeline.run(output_dir, date_tag, time_tag)

            execution_time = time.time() - stage_start

            return DataFetchResult(
                data=etl_result.data,
                records_processed=etl_result.records_processed,
                execution_time=execution_time,
                source_info={
                    "redcap_url": getattr(self.config, "redcap_url", "N/A"),
                    "project_id": getattr(self.config, "project_id", "N/A")
                },
                fetch_timestamp=datetime.now(),
                success=True
            )

        except Exception as e:
            self.logger.error(f"Data fetch stage failed: {e}")
            raise DataFetchError(f"Failed to fetch data: {e}", e)

    def _execute_rules_loading_stage(self) -> RulesLoadingResult:
        """Execute the rules loading stage using packet-based routing."""
        try:
            from ..core.data_processing import build_variable_maps
            from ..io.hierarchical_router import HierarchicalRuleResolver
            from ..io.packet_router import PacketRuleRouter

            stage_start = time.time()

            # Use lazy logging to avoid eager formatting
            self.logger.info(
                "Loading validation rules for %d instruments using packet routing...",
                len(self.config.instruments),
            )

            # Initialize packet router for production rule loading
            PacketRuleRouter(self.config)
            hierarchical_resolver = HierarchicalRuleResolver(self.config)

            # Load rules for all instruments using packet routing
            rules_cache = {}
            failed_instruments = []
            error_messages = {}

            for instrument in self.config.instruments:
                try:
                    # Use the new rules loading method that handles dynamic instruments
                    # properly
                    instrument_rules = hierarchical_resolver.load_all_rules_for_instrument(
                        instrument)

                    if instrument_rules:
                        rules_cache[instrument] = instrument_rules
                        self.logger.debug(
                            f"Loaded rules for instrument: {instrument}")
                    else:
                        failed_instruments.append(instrument)
                        error_messages[instrument] = f"No rules found for instrument {instrument}"

                except Exception as e:
                    failed_instruments.append(instrument)
                    error_messages[instrument] = str(e)
                    self.logger.warning(
                        f"Failed to load rules for {instrument}: {e}")

            self.logger.info("Building variable mappings...")
            variable_to_instrument_map, instrument_to_variables_map = build_variable_maps(
                self.config.instruments, rules_cache)

            execution_time = time.time() - stage_start

            return RulesLoadingResult(
                rules_cache=rules_cache,
                instruments_processed=self.config.instruments,
                loading_time=execution_time,
                variable_to_instrument_map=variable_to_instrument_map,
                instrument_to_variables_map=instrument_to_variables_map,
                success=len(failed_instruments) < len(self.config.instruments),
                failed_instruments=failed_instruments,
                error_messages=error_messages
            )

        except Exception as e:
            self.logger.error(f"Rules loading stage failed: {e}")
            raise RulesLoadingError(f"Failed to load validation rules: {e}", e)

    def _execute_data_preparation_stage(
        self,
        data_fetch_result: DataFetchResult,
        rules_loading_result: RulesLoadingResult
    ) -> DataPreparationResult:
        """Execute the data preparation stage."""
        try:
            from ..core.data_processing import prepare_instrument_data_cache
            from ..core.visit_processing import build_complete_visits_df

            stage_start = time.time()

            data_df = data_fetch_result.data
            complete_visits_result = None

            # Handle complete visits mode
            if self.config.mode == "complete_visits" and not data_df.empty:
                self.logger.info("Processing complete visits...")
                visits_start = time.time()

                complete_visits_df, complete_visits_tuples = build_complete_visits_df(
                    data_df, self.config.instruments)

                visits_time = time.time() - visits_start

                complete_visits_result = CompleteVisitsResult(
                    summary_dataframe=complete_visits_df,
                    complete_visits_tuples=complete_visits_tuples,
                    total_visits_processed=len(data_df.groupby(
                        [self.config.primary_key_field, "redcap_event_name"])),
                    complete_visits_count=len(complete_visits_df),
                    processing_time=visits_time
                )

                # Filter data to complete visits only
                if not complete_visits_df.empty:
                    # Avoid f-strings in logging
                    self.logger.info(
                        "Filtering to %d complete visits...",
                        len(complete_visits_df),
                    )
                    # Create index for comparison
                    data_index = data_df.set_index([
                        self.config.primary_key_field, "redcap_event_name"
                    ]).index
                    complete_index = complete_visits_df.set_index([
                        self.config.primary_key_field, "redcap_event_name"
                    ]).index
                    complete_visits_mask = data_index.isin(complete_index)
                    data_df = data_df[complete_visits_mask].copy()
                else:
                    self.logger.warning(
                        "No complete visits found - no data will be processed")
                    data_df = pd.DataFrame()

            # Prepare instrument data cache
            instrument_data_cache = {}
            records_per_instrument = {}

            if not data_df.empty:
                self.logger.info("Preparing instrument data cache...")
                instrument_data_cache = prepare_instrument_data_cache(
                    data_df,
                    self.config.instruments,
                    rules_loading_result.instrument_to_variables_map,
                    rules_loading_result.rules_cache,
                    self.config.primary_key_field,
                )

                # Calculate records per instrument
                records_per_instrument = {
                    instrument: len(df) for instrument, df in instrument_data_cache.items()
                }
            else:
                records_per_instrument = dict.fromkeys(self.config.instruments, 0)

            execution_time = time.time() - stage_start

            return DataPreparationResult(
                instrument_data_cache=instrument_data_cache,
                complete_visits_data=complete_visits_result,
                preparation_time=execution_time,
                records_per_instrument=records_per_instrument,
                success=True
            )

        except Exception as e:
            self.logger.error(f"Data preparation stage failed: {e}")
            raise DataPreparationError(f"Failed to prepare data: {e}", e)

    def _execute_validation_stage(
        self,
        data_prep_result: DataPreparationResult,
        rules_loading_result: RulesLoadingResult
    ) -> ValidationResult:
        """Execute the validation stage."""
        try:
            from ..core.data_processing import preprocess_cast_types
            from ..core.validation_logging import build_detailed_validation_logs
            from ..report_pipeline import validate_data

            stage_start = time.time()

            all_errors = []
            all_logs = []
            all_passed = []
            records_for_status = []
            detailed_validation_logs = []

            instruments_processed = []

            # Process each instrument
            for i, instrument in enumerate(self.config.instruments, 1):
                self.logger.info(
                    f"Validating {instrument} ({i}/{len(self.config.instruments)})")

                df = data_prep_result.get_instrument_data(instrument)
                if df.empty:
                    self.logger.warning(
                        f"No data available for instrument '{instrument}' after preparation.")
                    continue

                instruments_processed.append(instrument)

                # Build detailed validation logs based on instrument
                # completeness
                logs_for_this = build_detailed_validation_logs(
                    df, instrument, primary_key_field=self.config.primary_key_field)
                detailed_validation_logs.extend(logs_for_this)

                # Preprocess data types
                rules = rules_loading_result.get_rules_for_instrument(
                    instrument)
                df = preprocess_cast_types(df, rules)

                # Run validation
                errors, logs, passed_records = validate_data(
                    df, rules, instrument_name=instrument,
                    primary_key_field=self.config.primary_key_field
                )

                all_errors.extend(errors)
                all_logs.extend(logs)
                all_passed.extend(passed_records)

                # Collect records for status - create simple record info with instrument
                # name
                if not df.empty:
                    record_df = df[[self.config.primary_key_field,
                                    "redcap_event_name"]].copy()
                    record_df["instrument_name"] = instrument
                    records_for_status.append(record_df)
                else:
                    # Create empty DataFrame with proper columns
                    empty_df = pd.DataFrame(
                        columns=[
                            self.config.primary_key_field,
                            "redcap_event_name",
                            "instrument_name"])
                    records_for_status.append(empty_df)

            # Create result DataFrames
            errors_df = pd.DataFrame(
                all_errors) if all_errors else pd.DataFrame()
            logs_df = pd.DataFrame(all_logs) if all_logs else pd.DataFrame()
            passed_df = pd.DataFrame(
                all_passed) if all_passed else pd.DataFrame()
            validation_logs_df = pd.DataFrame(
                detailed_validation_logs) if detailed_validation_logs else pd.DataFrame()

            all_records_df = pd.DataFrame()
            if records_for_status:
                all_records_df = pd.concat(
                    records_for_status,
                    ignore_index=True).drop_duplicates(
                    subset=[
                        self.config.primary_key_field,
                        "redcap_event_name",
                        "instrument_name"])

            execution_time = time.time() - stage_start

            # Create validation summary
            validation_summary = {
                "total_errors": len(errors_df),
                "total_records": len(all_records_df),
                "instruments_processed": len(instruments_processed),
                "error_rate": (
                    len(errors_df) /
                    len(all_records_df) *
                    100) if len(all_records_df) > 0 else 0.0}

            return ValidationResult(
                errors_df=errors_df,
                logs_df=logs_df,
                passed_df=passed_df,
                validation_logs_df=validation_logs_df,
                all_records_df=all_records_df,
                validation_time=execution_time,
                instruments_processed=instruments_processed,
                validation_summary=validation_summary,
                success=True
            )

        except Exception as e:
            self.logger.error(f"Validation stage failed: {e}")
            raise ValidationError(f"Failed to validate data: {e}", e)

    def _execute_report_generation_stage(
        self,
        validation_result: ValidationResult,
        data_prep_result: DataPreparationResult,
        output_dir: Path,
        date_tag: str | None,
        time_tag: str | None
    ) -> ReportGenerationResult:
        """Execute the report generation stage."""
        try:
            from ..io.context import (
                ExportConfiguration,
                ProcessingContext,
                ReportConfiguration,
            )
            from ..io.reports import ReportFactory

            stage_start = time.time()

            # Create processing context
            processing_context = ProcessingContext(
                data_df=validation_result.all_records_df,
                instrument_list=self.config.instruments,
                rules_cache={},  # Not needed for export
                primary_key_field=self.config.primary_key_field,
                config=self.config
            )

            # Create export configuration
            # Ensure we have proper date and time tags
            if date_tag is None or time_tag is None:
                current_datetime = datetime.now()
                date_tag = date_tag or current_datetime.strftime(
                    "%d%b%Y").upper()
                time_tag = time_tag or current_datetime.strftime("%H%M%S")

            export_config = ExportConfiguration(
                output_dir=output_dir,
                date_tag=date_tag,
                time_tag=time_tag
            )

            # Create report configuration
            report_config = ReportConfiguration(
                qc_run_by=self.config.user_initials or "N/A",
                primary_key_field=self.config.primary_key_field,
                instruments=self.config.instruments
            )

            # Generate reports
            self.logger.info("Generating reports...")
            report_factory = ReportFactory(processing_context)

            complete_visits_df = pd.DataFrame()
            if data_prep_result.complete_visits_data:
                complete_visits_df = data_prep_result.complete_visits_data.summary_dataframe

            generated_files = report_factory.export_all_reports(
                df_errors=validation_result.errors_df,
                df_logs=validation_result.logs_df,
                df_passed=validation_result.passed_df,
                all_records_df=validation_result.all_records_df,
                complete_visits_df=complete_visits_df,
                detailed_validation_logs_df=validation_result.validation_logs_df,
                export_config=export_config,
                report_config=report_config)

            execution_time = time.time() - stage_start

            # Map generated files to report types
            reports_created = {}
            for file_path in generated_files:
                if "errors" in file_path.name.lower():
                    reports_created["errors"] = file_path
                elif "logs" in file_path.name.lower():
                    reports_created["logs"] = file_path
                elif "status" in file_path.name.lower():
                    reports_created["status"] = file_path
                elif "visits" in file_path.name.lower():
                    reports_created["complete_visits"] = file_path

            return ReportGenerationResult(
                generated_files=generated_files,
                export_time=execution_time,
                reports_created=reports_created,
                success=True
            )

        except Exception as e:
            self.logger.error(f"Report generation stage failed: {e}")
            raise ReportGenerationError(f"Failed to generate reports: {e}", e)

    def _create_run_metadata(self) -> dict:
        """Create run metadata for the pipeline execution."""
        return {
            "pipeline_version": "2.0.0-improved",
            "execution_timestamp": datetime.now().isoformat(),
            "config_mode": self.config.mode,
            "instruments_requested": self.config.instruments.copy(),
            "primary_key_field": self.config.primary_key_field,
            "user_initials": getattr(self.config, "user_initials", "N/A")
        }

    def _create_failed_result(
        self,
        error: Exception,
        total_time: float,
        output_dir: Path
    ) -> PipelineExecutionResult:
        """Create a pipeline result for failed execution."""
        # Create minimal failed results for each stage
        failed_data_fetch = DataFetchResult(
            data=pd.DataFrame(),
            records_processed=0,
            execution_time=0,
            source_info={},
            fetch_timestamp=datetime.now(),
            success=False,
            error_message=str(error)
        )

        failed_rules_loading = RulesLoadingResult(
            rules_cache={},
            instruments_processed=[],
            loading_time=0,
            variable_to_instrument_map={},
            instrument_to_variables_map={},
            success=False,
            failed_instruments=self.config.instruments
        )

        failed_data_prep = DataPreparationResult(
            instrument_data_cache={},
            complete_visits_data=None,
            preparation_time=0,
            records_per_instrument={},
            success=False,
            error_message=str(error)
        )

        failed_validation = ValidationResult(
            errors_df=pd.DataFrame(),
            logs_df=pd.DataFrame(),
            passed_df=pd.DataFrame(),
            validation_logs_df=pd.DataFrame(),
            all_records_df=pd.DataFrame(),
            validation_time=0,
            instruments_processed=[],
            validation_summary={},
            success=False,
            error_message=str(error)
        )

        failed_report_generation = ReportGenerationResult(
            generated_files=[],
            export_time=0,
            reports_created={},
            success=False,
            failed_reports=["all"],
            error_messages={"pipeline": str(error)}
        )

        return PipelineExecutionResult(
            data_fetch=failed_data_fetch,
            rules_loading=failed_rules_loading,
            data_preparation=failed_data_prep,
            validation=failed_validation,
            report_generation=failed_report_generation,
            total_execution_time=total_time,
            output_directory=output_dir,
            run_metadata=self._create_run_metadata(),
            success=False,
            pipeline_error=str(error)
        )
