"""
Main pipeline for processing and validating REDCap instrument data.

This module orchestrates the entire QC process, from fetching raw data to
generating final summary reports. It is designed to be run from the command
line via `cli/cli.py`.

The pipeline operates in several stages:
1.  **Configuration**: Loads settings from `QCConfig`.
2.  **Data Fetching**: Extracts data from the source using `pipeline.fetcher`.
3.  **Rule Loading**: Caches all JSON validation rules for the requested instruments.
4.  **Data Preparation**: Prepares instrument-specific dataframes for validation.
5.  **Validation**: Uses a standardized per-record validation approach through
    the QualityCheck system for consistent processing across all instrument types.
6.  **Reporting**: Generates several output files, including:
    - A final dataset of all identified errors.
    - Aggregate error counts per participant/event.
    - A tool status report indicating pass/fail for each instrument.
    - Detailed validation logs.

REFACTORING NOTE: The validation process has been standardized to use a single
unified approach instead of separate vectorized and dynamic validation paths.
This ensures consistency across all validation scenarios at the cost of some
performance optimization.
"""
import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING
from dataclasses import asdict

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from .context import ExportConfiguration, ReportConfiguration

from pipeline.config_manager import (
    QCConfig,
    get_dynamic_rule_instruments,
    get_discriminant_variable,
    is_dynamic_rule_instrument,
    get_rule_mappings,
    get_instrument_json_mapping,
    upload_ready_path
)
from pipeline.fetcher import RedcapETLPipeline
from nacc_form_validator.quality_check import QualityCheck
from pipeline.helpers import (
    build_complete_visits_df,
    build_detailed_validation_logs,
    build_variable_maps,
    debug_variable_mapping,  # Deprecated - use analytics.create_simplified_debug_info
    load_rules_for_instruments,
    load_json_rules_for_instrument,
    prepare_instrument_data_cache,
    _preprocess_cast_types,
    load_dynamic_rules_for_instrument,
)
from pipeline.analytics import create_simplified_debug_info
from pipeline.reports import ReportFactory
from pipeline.schema_builder import build_cerberus_schema_for_instrument
from nacc_form_validator.utils import (
    convert_to_date,
    convert_to_datetime,
)

# Set up logging
import logging

logger = logging.getLogger(__name__)


def run_report_pipeline(config: QCConfig):
    """
    Main entry point for the QC report pipeline.

    This function orchestrates the entire process, from fetching data to
    generating the final reports.

    Args:
        config: The configuration object for the pipeline.
    """
    print("")
    print("="*80)
    print("STARTING QC REPORT PIPELINE")
    print("="*80)
    print("")

    # Create the main output directory based on run type, date, and time
    run_type_str = config.mode.replace("_", " ").title().replace(" ", "")
    current_datetime = datetime.datetime.now()
    date_tag = current_datetime.strftime("%d%b%Y").upper()
    time_tag = current_datetime.strftime("%H%M%S")
    run_dir_name = f"QC_{run_type_str}_{date_tag}_{time_tag}"

    output_path = Path(config.output_path) / run_dir_name
    output_path.mkdir(parents=True, exist_ok=True)

    (
        df_errors,
        df_logs,
        df_passed,
        all_records_df,
        complete_visits_df,
        detailed_logs_df,
    ) = process_instruments_etl(config, output_path, date_tag, time_tag)

    export_results_to_csv(
        df_errors,
        df_logs,
        df_passed,
        all_records_df,
        complete_visits_df,
        detailed_logs_df,
        output_dir=output_path,
        date_tag=date_tag,
        time_tag=time_tag,
    )

    if not all_records_df.empty:
        generate_aggregate_error_count_report(
            df_errors,
            config.instruments,
            all_records_df,
            output_dir=output_path,
            primary_key_field=config.primary_key_field,
            date_tag=date_tag,
            time_tag=time_tag,
        )
        generate_tool_status_reports(
            processed_records_df=all_records_df,
            pass_fail_log=[
                {str(k): v for k, v in row.items()}
                for row in detailed_logs_df.to_dict("records")
            ],
            output_dir=output_path,
            file_suffix=f"{date_tag}_{time_tag}",
            qc_run_by=config.user_initials or "N/A",
            primary_key_field=config.primary_key_field,
            errors_df=df_errors,
            instruments=config.instruments,
        )


def _collect_processed_records_info(
    df: pd.DataFrame, instrument: str, primary_key_field: str
) -> pd.DataFrame:
    """
    Collects key information about processed records for status reporting.

    This includes ptid, event name, instrument, and the discriminant
    variable for dynamic instruments.

    Args:
        df: The DataFrame of records processed for a single instrument.
        instrument: The name of the instrument.
        primary_key_field: The name of the primary key field.

    Returns:
        A DataFrame with essential information for status reports.
    """
    info_cols = [primary_key_field, "redcap_event_name"]
    rec = df[info_cols].copy()
    rec["instrument_name"] = instrument

    if is_dynamic_rule_instrument(instrument):
        discriminant_var = get_discriminant_variable(instrument)
        if discriminant_var in df.columns:
            rec[discriminant_var] = df[discriminant_var]
        else:
            rec[discriminant_var] = None

    return rec


# ───────────────────────────────── Data Validation with Json Rules ─────────────────────────────────

class ValidationEngine:
    """
    Optimized validation engine with caching and performance improvements.
    
    This maintains the per-record validation approach while optimizing
    supporting infrastructure for better performance.
    """
    
    def __init__(self):
        """Initialize validation engine with caches."""
        self._schema_cache: Dict[str, Any] = {}
        self._rule_cache: Dict[str, Any] = {}
        self._qc_cache: Dict[str, QualityCheck] = {}
    
    def _get_cache_key(self, instrument_name: str, variant: str = "") -> str:
        """Generate cache key for instrument and variant."""
        return f"{instrument_name}:{variant}" if variant else instrument_name
    
    def _get_cached_schema_and_rules(
        self,
        record: Dict[str, Any],
        instrument_name: str,
        default_rules: Dict[str, Any],
        primary_key_field: str,
    ) -> Tuple[QualityCheck, Dict[str, Any]]:
        """
        Get cached schema and rules with optimized lookups.
        
        This replaces _get_schema_and_rules_for_record with caching.
        """
        if is_dynamic_rule_instrument(instrument_name):
            discriminant_var = get_discriminant_variable(instrument_name)
            variant = str(record.get(discriminant_var, "")).upper()
            
            # Fallback to first variant if missing
            if not variant:
                rule_mappings = get_rule_mappings(instrument_name)
                variant = list(rule_mappings.keys())[0]
            
            cache_key = self._get_cache_key(instrument_name, variant)
        else:
            cache_key = self._get_cache_key(instrument_name)
            variant = ""
        
        # Check QualityCheck cache first
        if cache_key in self._qc_cache:
            qc = self._qc_cache[cache_key]
            rules = self._rule_cache.get(cache_key, default_rules)
            return qc, rules
        
        # Build schema and QualityCheck if not cached
        if is_dynamic_rule_instrument(instrument_name):
            # Get cached schema or build it
            if cache_key not in self._schema_cache:
                cerb_schema = build_cerberus_schema_for_instrument(
                    instrument_name, 
                    include_temporal_rules=False,
                    include_compatibility_rules=True
                )
                self._schema_cache[cache_key] = cerb_schema[variant]
                
                # Cache rules for this variant
                dynamic_rules = load_dynamic_rules_for_instrument(instrument_name)
                self._rule_cache[cache_key] = dynamic_rules[variant]
            
            sub_schema = self._schema_cache[cache_key]
            rules = self._rule_cache[cache_key]
            qc = QualityCheck(pk_field=primary_key_field, schema=sub_schema, datastore=None)
        else:
            # Standard instrument
            if cache_key not in self._schema_cache:
                cerb_schema = build_cerberus_schema_for_instrument(
                    instrument_name,
                    include_temporal_rules=False,
                    include_compatibility_rules=True
                )
                self._schema_cache[cache_key] = cerb_schema
                self._rule_cache[cache_key] = default_rules
            
            schema = self._schema_cache[cache_key]
            rules = self._rule_cache[cache_key]
            qc = QualityCheck(pk_field=primary_key_field, schema=schema, datastore=None)
        
        # Cache QualityCheck instance
        self._qc_cache[cache_key] = qc
        return qc, rules
    
    def validate_data_optimized(
        self,
        data: pd.DataFrame,
        validation_rules: Dict[str, Any],
        instrument_name: str,
        primary_key_field: str,
        event_name: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Optimized validation with caching and reduced object creation.
        
        Maintains per-record processing while optimizing supporting infrastructure.
        """
        errors: List[Dict[str, Any]] = []
        validation_logs: List[Dict[str, Any]] = []
        passed_validations: List[Dict[str, Any]] = []

        df = data.copy()
        if event_name:
            df = df[df["redcap_event_name"] == event_name]

        # Pre-compute rule file mapping
        if is_dynamic_rule_instrument(instrument_name):
            instrument_json_mapping = get_rule_mappings(instrument_name)
        else:
            instrument_json_mapping = get_instrument_json_mapping()
            
        rule_files = instrument_json_mapping.get(instrument_name, [])
        rule_file_str = ",".join(rule_files) if isinstance(rule_files, list) else rule_files

        # --- Optimized per-record validation ---
        for _, row in df.iterrows():
            record = row.to_dict()

            qc, rules = self._get_cached_schema_and_rules(
                record, instrument_name, validation_rules, primary_key_field
            )

            result = qc.validate_record(record)

            # Optimized error logging with reduced object creation
            self._log_validation_results_optimized(
                record, rules, result.errors, qc, instrument_name,
                errors, validation_logs, passed_validations,
                primary_key_field, rule_file_str
            )

        return errors, validation_logs, passed_validations
    
    def _log_validation_results_optimized(
        self,
        record: Dict[str, Any],
        rules: Dict[str, Any],
        errs_dict: Dict[str, Any],
        qc: QualityCheck,
        instrument_name: str,
        errors: List[Dict[str, Any]],
        validation_logs: List[Dict[str, Any]],
        passed_validations: List[Dict[str, Any]],
        primary_key_field: str,
        rule_file_str: str,
    ):
        """
        Optimized validation result logging with reduced overhead.
        """
        pk_val = record.get(primary_key_field)
        event = record.get("redcap_event_name")

        # Process all variables in a single loop to reduce overhead
        for var, var_rules in rules.items():
            raw_val = record.get(var)
            str_val = str(raw_val) if raw_val is not None else ""
            interp_val = qc.validator.cast_record({var: str_val}).get(var, raw_val)

            expected_t = var_rules.get("type")
            fld_errs = errs_dict.get(var, [])
            err_msg = fld_errs[0] if fld_errs else None

            # Pre-computed common data
            base_log_data = {
                primary_key_field: pk_val,
                "variable": var,
                "redcap_event_name": event,
                "instrument_name": instrument_name,
            }

            # Always add to validation logs
            validation_logs.append({
                **base_log_data,
                "json_rule": json.dumps(var_rules),
                "rule_file": rule_file_str,
            })

            if err_msg:
                # Add to errors
                errors.append({
                    **base_log_data,
                    "current_value": interp_val,
                    "expected_value": expected_t,
                    "error": err_msg,
                })
            else:
                # Add to passed validations
                passed_validations.append({
                    **base_log_data,
                    "current_value": interp_val,
                    "json_rule": json.dumps(var_rules),
                    "rule_file": rule_file_str,
                })


# Global validation engine instance for reuse
_validation_engine = ValidationEngine()


def validate_data(
    data: pd.DataFrame,
    validation_rules: Dict[str, Any],
    instrument_name: str,
    primary_key_field: str,
    event_name: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validates a DataFrame of instrument data against a set of rules using a standardized process.

    This function now uses an optimized validation engine while maintaining the
    per-record validation approach required for ETL modularity and nacc_form_validator compatibility.

    Args:
        data: DataFrame containing the data for a specific instrument.
        validation_rules: A dictionary of JSON validation rules for the instrument.
        instrument_name: The name of the instrument being validated.
        primary_key_field: The name of the primary key field.
        event_name: If provided, filters the DataFrame to this specific event.

    Returns:
        A tuple containing:
        - A list of dictionaries, where each dictionary is a validation error.
        - A list of dictionaries representing detailed validation logs.
        - A list of dictionaries for validations that passed.
    """
    return _validation_engine.validate_data_optimized(
        data, validation_rules, instrument_name, primary_key_field, event_name
    )

    return errors, validation_logs, passed_validations

def _get_schema_and_rules_for_record(
    record: Dict[str, Any],
    cerb_schema: Dict[str, Any],
    instrument_name: str,
    default_rules: Dict[str, Any],
    primary_key_field: str,
) -> Tuple[QualityCheck, Dict[str, Any]]:
    """
    Selects the appropriate schema and rules for a record.
    
    Handles dynamic instruments by selecting a sub-schema and rules based on a
    discriminant variable's value in the record.

    Args:
        record: The data record (as a dictionary).
        cerb_schema: The top-level Cerberus schema for the instrument.
        instrument_name: The name of the instrument.
        default_rules: The default set of validation rules.

    Returns:
        A tuple containing the configured `QualityCheck` object and the
        applicable dictionary of validation rules.
    """
    if is_dynamic_rule_instrument(instrument_name):
        discriminant_var = get_discriminant_variable(instrument_name)
        variant = str(record.get(discriminant_var, "")).upper()
        
        # Fallback to the first defined variant if the key is missing or empty
        if not variant or variant not in cerb_schema:
            variant = list(cerb_schema.keys())[0]

        sub_schema = cerb_schema[variant]
        qc = QualityCheck(pk_field=primary_key_field, schema=sub_schema, datastore=None)
        # Load the specific rules for this variant
        rules = load_dynamic_rules_for_instrument(instrument_name)[variant]
    else:
        qc = QualityCheck(pk_field=primary_key_field, schema=cerb_schema, datastore=None)
        rules = default_rules

    return qc, rules


def _log_validation_results(
    record: Dict[str, Any],
    rules: Dict[str, Any],
    errs_dict: Dict[str, Any],
    qc: QualityCheck,
    instrument_name: str,
    errors: List[Dict[str, Any]],
    validation_logs: List[Dict[str, Any]],
    passed_validations: List[Dict[str, Any]],
    primary_key_field: str,
):
    """
    Logs the outcome of a validation check for each field in a record.

    For each variable in the rule set, this function records whether it passed
    or failed validation, creating detailed log entries.

    Args:
        record: The record that was validated.
        rules: The validation rules applied to the record.
        errs_dict: A dictionary of errors from the validator.
        qc: The `QualityCheck` instance used for validation.
        instrument_name: The name of the instrument.
        errors: The master list of errors to append to.
        validation_logs: The master list of validation logs to append to.
        passed_validations: The master list of passed validations to append to.
        primary_key_field: The name of the primary key field.
    """
    pk_val = record.get(primary_key_field)
    event = record.get("redcap_event_name")

    # Get the correct rule mapping based on instrument type
    if is_dynamic_rule_instrument(instrument_name):
        # For dynamic instruments, the rules are already specific, so we can get the mapping directly
        instrument_json_mapping = get_rule_mappings(instrument_name)
        # The variant is needed to get the correct file
        discriminant_var = get_discriminant_variable(instrument_name)
        variant = str(record.get(discriminant_var, "")).upper()
        files = instrument_json_mapping.get(variant, [])
    else:
        # For standard instruments, get the global mapping
        instrument_json_mapping = get_instrument_json_mapping()
        files = instrument_json_mapping.get(instrument_name, [])

    for var, var_rules in rules.items():
        raw_val = record.get(var)
        # Use the validator's type casting to get the interpreted value
        str_val = str(raw_val) if raw_val is not None else ""
        interp_val = qc.validator.cast_record({var: str_val}).get(var, raw_val)

        expected_t = var_rules.get("type")
        fld_errs = errs_dict.get(var, [])
        err_msg = fld_errs[0] if fld_errs else None

        rule_file = ",".join(files) if isinstance(files, list) else files

        validation_logs.append(
            {
                primary_key_field: pk_val,
                "variable": var,
                "json_rule": json.dumps(var_rules),
                "rule_file": rule_file,
                "redcap_event_name": event,
                "instrument_name": instrument_name,
            }
        )

        if err_msg:
            errors.append(
                {
                    primary_key_field: pk_val,
                    "redcap_event_name": event,
                    "instrument_name": instrument_name,
                    "variable": var,
                    "current_value": interp_val,
                    "expected_value": expected_t,
                    "error": err_msg,
                }
            )
        else:
            passed_validations.append(
                {
                    primary_key_field: pk_val,
                    "variable": var,
                    "current_value": interp_val,
                    "json_rule": json.dumps(var_rules),
                    "rule_file": rule_file,
                    "redcap_event_name": event,
                    "instrument_name": instrument_name,
                }
            )


# ──────────────────────────────────── Main ETL-Optimized Processing Function ─────────────────────────────────


def process_instruments_etl(
    config: QCConfig,
    output_path: Optional[Union[str, Path]] = None,
    date_tag: Optional[str] = None,
    time_tag: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Orchestrates the ETL-optimized processing of instruments based on a config.

    Args:
        config: A `QCConfig` object containing all pipeline settings.
        output_path: Optional path to use for ETL output. If None, uses config.output_path.

    Returns:
        A tuple of DataFrames:
        (df_errors, df_logs, df_passed, all_records_df, complete_visits_df, detailed_validation_logs)
    """
    output_dir = Path(config.output_path)
    output_dir.mkdir(exist_ok=True)

    # Step 1: Load all necessary validation rules into a cache
    logger.info(f"Loading validation rules for {len(config.instruments)} instruments")
    rules_cache = load_rules_for_instruments(config.instruments)

    # Step 2: Fetch data using the modern ETL pipeline
    logger.info("Fetching data using modern RedcapETLPipeline.")
    try:
        pipeline = RedcapETLPipeline(config)
        etl_result = pipeline.run(output_path, date_tag, time_tag)
        data_df = etl_result.data
        logger.info(f"ETL pipeline completed: {etl_result.records_processed} records ready for processing "
                   f"(execution time: {etl_result.execution_time:.2f}s)")
    except Exception as e:
        logger.error(f"ETL pipeline failed: {e}", exc_info=True)
        raise RuntimeError(f"ETL data fetch failed: {e}") from e

    # Step 3: Apply complete visits filtering BEFORE building the instrument data cache
    complete_visits_df = pd.DataFrame()
    if config.mode == "complete_visits" and not data_df.empty:
        complete_visits_df, _ = build_complete_visits_df(data_df, config.instruments)
        
        # Filter data_df to only include records from complete visits
        if not complete_visits_df.empty:
            # Create a mask for complete visits
            complete_visits_mask = data_df.set_index(['ptid', 'redcap_event_name']).index.isin(
                complete_visits_df.set_index(['ptid', 'redcap_event_name']).index
            )
            data_df = data_df[complete_visits_mask].copy()
            logger.debug(f"Filtered to {len(data_df)} records from {len(complete_visits_df)} complete visits")
        else:
            logger.warning("No complete visits found - no data will be processed")
            data_df = pd.DataFrame()  # Empty the dataframe if no complete visits

    # Step 4: Prepare data and mappings with filtered data
    if not data_df.empty:
        # Use new simplified analytics instead of deprecated debug_variable_mapping
        debug_info = create_simplified_debug_info(data_df, config.instruments, rules_cache, "summary")
        if 'summary' in debug_info:
            coverage = debug_info['summary'].get('overall_coverage', 'N/A')
            logger.debug(f"Variable mapping analysis: {coverage} coverage")
        
        # For backwards compatibility, also run old function (with deprecation warning)
        old_debug_info = debug_variable_mapping(data_df, config.instruments, rules_cache)
        for instrument, missing_vars in old_debug_info['missing_variables'].items():
            if missing_vars:
                logger.warning(f"Missing variables for {instrument}: {missing_vars[:5]}{'...' if len(missing_vars) > 5 else ''}")

    _, instrument_variable_map = build_variable_maps(config.instruments, rules_cache)
    instrument_data_cache = {}
    if not data_df.empty:
        instrument_data_cache = prepare_instrument_data_cache(
            data_df,
            config.instruments,
            instrument_variable_map,
            rules_cache,
            config.primary_key_field,
        )

    logger.info("Starting validation processing...")

    all_errors: List[Dict[str, Any]] = []
    all_logs: List[Dict[str, Any]] = []
    all_passed: List[Dict[str, Any]] = []
    records_for_status: List[pd.DataFrame] = []
    detailed_validation_logs: List[Dict[str, Any]] = []

    # Step 5: Process each instrument
    for i, instrument in enumerate(config.instruments, 1):
        logger.info(f"Processing {instrument} ({i}/{len(config.instruments)})")
        df = instrument_data_cache.get(instrument, pd.DataFrame())
        if df.empty:
            logger.warning(f"No data available for instrument '{instrument}' after ETL filtering.")
            continue
        
        # Build screening logs based on instrument completeness
        logs_for_this = build_detailed_validation_logs(
            df, instrument, primary_key_field=config.primary_key_field
        )
        detailed_validation_logs.extend(logs_for_this)
        
        rules = rules_cache[instrument]
        df = _preprocess_cast_types(df, rules)
        errors, logs, passed_records = validate_data(
            df, rules, instrument_name=instrument, primary_key_field=config.primary_key_field
        )
        
        all_errors.extend(errors)
        all_logs.extend(logs)
        all_passed.extend(passed_records)
        records_for_status.append(
            _collect_processed_records_info(
                df, instrument, primary_key_field=config.primary_key_field
            )
        )

    df_errors = pd.DataFrame(all_errors) if all_errors else pd.DataFrame()
    df_logs = pd.DataFrame(all_logs) if all_logs else pd.DataFrame()
    df_passed = pd.DataFrame(all_passed) if all_passed else pd.DataFrame()
    
    all_records_df = pd.DataFrame()
    if records_for_status:
        all_records_df = pd.concat(records_for_status, ignore_index=True).drop_duplicates(
            subset=[config.primary_key_field, "redcap_event_name", "instrument_name"]
        )

    logger.info(
        f"VALIDATION SUMMARY: {len(df_errors)} errors found across {len(config.instruments)} instruments"
    )

    print("")
    print("="*80)
    print("ETL INSTRUMENT PROCESSING COMPLETED SUCCESSFULLY")
    print("="*80)

    return (
        df_errors,
        df_logs,
        df_passed,
        all_records_df,
        complete_visits_df,
        pd.DataFrame(detailed_validation_logs) if detailed_validation_logs else pd.DataFrame(),
    )

# ───────────────────────────────── Export Functions ─────────────────────────────────
def export_results_to_csv(
    df_errors: pd.DataFrame,
    df_logs: pd.DataFrame,
    df_passed: pd.DataFrame,
    all_records_df: pd.DataFrame,
    complete_visits_df: pd.DataFrame,
    detailed_validation_logs_df: pd.DataFrame,
    output_dir: Path,
    date_tag: str,
    time_tag: str,
):
    """
    Exports the results of the ETL process to CSV files in organized directories.

    **DEPRECATED**: This function will be removed in version 2.0.0 (Target: March 2026).
    Use `ReportFactory.export_all_reports()` from `reports.py` instead.
    
    The new ReportFactory provides:
    - Unified report generation interface
    - Better organization and naming consistency
    - Improved metadata tracking
    - More maintainable code structure
    
    Migration example:
        # Old way:
        export_results_to_csv(df_errors, df_logs, df_passed, ...)
        
        # New way:
        from .reports import ReportFactory
        factory = ReportFactory(processing_context)
        factory.export_all_reports(df_errors, df_logs, df_passed, ..., export_config, report_config)

    Args:
        df_errors: DataFrame of all validation errors.
        df_logs: DataFrame of comprehensive validation logs.
        df_passed: DataFrame of all passed validations.
        all_records_df: DataFrame with info on all processed records.
        complete_visits_df: DataFrame of completed visits.
        detailed_validation_logs_df: DataFrame of pre-validation screening logs.
        output_dir: The base directory for output files.
        date_tag: Date tag string for consistent naming.
        time_tag: Time tag string for consistent naming.
    """
    import warnings
    warnings.warn(
        "export_results_to_csv is deprecated and will be removed in version 2.0.0 "
        "(Target: March 2026). Use ReportFactory.export_all_reports from reports.py instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Import here to avoid circular dependencies
    from .context import ExportConfiguration
    
    # Create export configuration
    export_config = ExportConfiguration(
        output_dir=Path(output_dir),
        date_tag=date_tag,
        time_tag=time_tag,
        include_logs=True,
        include_passed=True,
        include_detailed_logs=True
    )
    
    # Use the new export function
    export_results_with_config(
        df_errors, df_logs, df_passed, all_records_df, 
        complete_visits_df, detailed_validation_logs_df, export_config
    )


def export_results_with_config(
    df_errors: pd.DataFrame,
    df_logs: pd.DataFrame,
    df_passed: pd.DataFrame,
    all_records_df: pd.DataFrame,
    complete_visits_df: pd.DataFrame,
    detailed_validation_logs_df: pd.DataFrame,
    export_config: 'ExportConfiguration',
):
    """
    Exports results using structured configuration object.

    Args:
        df_errors: DataFrame of all validation errors.
        df_logs: DataFrame of comprehensive validation logs.
        df_passed: DataFrame of all passed validations.
        all_records_df: DataFrame with info on all processed records.
        complete_visits_df: DataFrame of completed visits.
        detailed_validation_logs_df: DataFrame of pre-validation screening logs.
        export_config: Configuration object for export settings.
    """
    # --- Save Key Summary Files to the Run-Specific Directory ---
    if not df_errors.empty:
        error_filename = export_config.get_report_filename("Final_Error_Dataset")
        df_errors.to_csv(export_config.output_dir / error_filename, index=False)

    if not complete_visits_df.empty:
        visits_filename = export_config.get_report_filename("PTID_CompletedVisits")
        complete_visits_df.to_csv(export_config.output_dir / visits_filename, index=False)

    # --- Save Detailed Logs to Validation_Logs Subdirectory ---
    if export_config.include_logs or export_config.include_passed or export_config.include_detailed_logs:
        validation_logs_dir = export_config.get_validation_logs_dir()

        if export_config.include_logs and not df_logs.empty:
            logs_filename = export_config.get_report_filename("Log_RulesValidation")
            df_logs.to_csv(validation_logs_dir / logs_filename, index=False)

        if export_config.include_passed and not df_passed.empty:
            passed_filename = export_config.get_report_filename("Log_PassedValidations")
            df_passed.to_csv(validation_logs_dir / passed_filename, index=False)

        if export_config.include_detailed_logs and not detailed_validation_logs_df.empty:
            detailed_filename = export_config.get_report_filename("Log_EventCompletenessScreening")
            detailed_validation_logs_df.to_csv(validation_logs_dir / detailed_filename, index=False)

    print("Final Error Dataset Created")
    print("Validation Logs Created")


# ── Aggregate Error Count Report ────────────────────────────────────────────────
def generate_aggregate_error_count_report(
    df_errors: pd.DataFrame,
    instrument_list: List[str],
    all_records_df: pd.DataFrame,
    output_dir: Path,
    primary_key_field: str,
    date_tag: str,
    time_tag: str,
):
    """
    Summarizes error counts per ptid & event, writing the report to the output directory.
    
    **DEPRECATED**: This function will be removed in version 2.0.0 (Target: March 2026).
    Use `ReportFactory.generate_aggregate_error_report()` from `reports.py` instead.
    
    Args:
        df_errors: DataFrame containing all validation errors.
        instrument_list: List of all instruments included in the run.
        all_records_df: DataFrame containing all records that were processed.
        output_dir: The directory to save the report to.
        primary_key_field: The name of the primary key field.
        date_tag: Date tag string for consistent naming.
        time_tag: Time tag string for consistent naming.
    """
    import warnings
    warnings.warn(
        "generate_aggregate_error_count_report is deprecated and will be removed in version 2.0.0 "
        "(Target: March 2026). Use ReportFactory.generate_aggregate_error_report from reports.py instead.",
        DeprecationWarning,
        stacklevel=2
    )
    # Import here to avoid circular dependencies
    from .context import ProcessingContext, ExportConfiguration, ReportConfiguration
    from .config_manager import get_config
    
    # Create configuration objects
    export_config = ExportConfiguration(
        output_dir=Path(output_dir),
        date_tag=date_tag,
        time_tag=time_tag
    )
    
    report_config = ReportConfiguration(
        qc_run_by="N/A",  # Not available in legacy interface
        primary_key_field=primary_key_field,
        instruments=instrument_list,
        export_config=export_config
    )
    
    # Use the new function
    generate_aggregate_report_with_config(
        df_errors, all_records_df, report_config
    )


def generate_aggregate_report_with_config(
    df_errors: pd.DataFrame,
    all_records_df: pd.DataFrame,
    report_config: 'ReportConfiguration',
):
    """
    Generate aggregate error count report using configuration objects.
    
    Args:
        df_errors: DataFrame containing all validation errors.
        all_records_df: DataFrame containing all records that were processed.
        report_config: Configuration for report generation.
    """
    if all_records_df.empty:
        logger.warning("No records found — skipping aggregate error report.")
        return

    combos = (
        all_records_df[[report_config.primary_key_field, "redcap_event_name"]]
        .drop_duplicates()
        .reset_index()
        .drop(columns="index")
    )

    if df_errors.empty:
        report = combos.copy()
        for instr in report_config.instruments:
            report[instr] = 0
    else:
        counts = (
            df_errors.groupby(
                [report_config.primary_key_field, "redcap_event_name", "instrument_name"]
            )
            .size()
            .reset_index(name="error_count")
        )
        pivot = counts.pivot_table(
            index=[report_config.primary_key_field, "redcap_event_name"],
            columns="instrument_name",
            values="error_count",
            fill_value=0,
        ).reset_index()
        report = combos.merge(
            pivot, on=[report_config.primary_key_field, "redcap_event_name"], how="left"
        )

    for instr in report_config.instruments:
        if instr not in report.columns:
            report[instr] = 0
        report[instr] = report[instr].fillna(0).astype(int)

    report["total_error_count"] = report[report_config.instruments].sum(axis=1)
    cols = (
        [report_config.primary_key_field, "redcap_event_name"]
        + report_config.instruments
        + ["total_error_count"]
    )
    report = report[cols]

    # Save using export configuration
    if report_config.export_config:
        filename = report_config.export_config.get_report_filename("Report_ErrorCount")
        path = report_config.export_config.output_dir / filename
        report.to_csv(path, index=False)
        print("Aggregate Report Created")


# ── Tool Status Reports ─────────────────────────────────────────────────────────
def generate_tool_status_reports(
    processed_records_df: pd.DataFrame,
    pass_fail_log: List[Dict[str, Any]],
    output_dir: Path,
    file_suffix: str,
    qc_run_by: str,
    primary_key_field: str,
    errors_df: pd.DataFrame,
    instruments: List[str],
):
    """
    Generates a single QC status report CSV in the specified wide format.
    Also exports a JSON file with selected columns.

    **DEPRECATED**: This function will be removed in version 2.0.0 (Target: March 2026).
    Use `ReportFactory.generate_status_report()` from `reports.py` instead.

    Args:
        processed_records_df: DataFrame with information on all processed records.
        pass_fail_log: List of pass/fail logs for each record and instrument.
        output_dir: The directory to save the report.
        file_suffix: Suffix for the report file, typically the date.
        qc_run_by: The identifier for who ran the QC.
        primary_key_field: The name of the primary key field.
        errors_df: DataFrame containing all validation errors.
        instruments: List of all instruments in the run.
    """
    import warnings
    warnings.warn(
        "generate_tool_status_reports is deprecated and will be removed in version 2.0.0 "
        "(Target: March 2026). Use ReportFactory.generate_status_report from reports.py instead.",
        DeprecationWarning,
        stacklevel=2
    )
    if processed_records_df.empty:
        logger.warning("No processed records found — skipping status report.")
        return

    # Start with a unique list of visits
    status_report_df = processed_records_df[[primary_key_field, "redcap_event_name"]].drop_duplicates().reset_index(drop=True)

    # Pivot the errors to get a pass/fail status for each instrument
    if not errors_df.empty:
        error_pivot = errors_df.pivot_table(
            index=[primary_key_field, "redcap_event_name"],
            columns="instrument_name",
            aggfunc='size',
            fill_value=0
        )
        # A value > 0 means there was at least one error, so it's a "Fail"
        for instrument in error_pivot.columns:
            error_pivot[instrument] = error_pivot[instrument].apply(lambda x: 'Fail' if x > 0 else 'Pass')
        
        # Merge the error status back into the main report
        status_report_df = status_report_df.merge(error_pivot, on=[primary_key_field, "redcap_event_name"], how="left")
    
    # Ensure all instrument columns exist, filling with "Pass" if no errors were found
    for instrument in instruments:
        if instrument not in status_report_df.columns:
            status_report_df[instrument] = "Pass"
        else:
            status_report_df[instrument] = status_report_df[instrument].fillna("Pass")

    # --- Add reporting metrics ---
    instrument_statuses = status_report_df[instruments]
    all_passed_mask = (instrument_statuses == 'Pass').all(axis=1)
    status_report_df['qc_status_complete'] = np.where(all_passed_mask, '1', '0')
    status_report_df['qc_run_by'] = qc_run_by
    status_report_df['qc_last_run'] = datetime.datetime.today().strftime("%Y-%m-%d")
    failed_instruments_summary = instrument_statuses.apply(
        lambda row: f"Failed in instruments: {', '.join(row[row == 'Fail'].index)}",
        axis=1
    )
    status_report_df['qc_status'] = np.where(all_passed_mask, 'All Passed', failed_instruments_summary)
    status_report_df['quality_control_check_complete'] = np.where(all_passed_mask, '2', '0')

    # Add form_header column (if not present, fill with empty string)
    if "form_header" not in status_report_df.columns:
        status_report_df["form_header"] = ""

    # Reorder columns to match the required format
    final_columns = [primary_key_field, "redcap_event_name"] + instruments + \
                    ['qc_status_complete', 'qc_run_by', 'qc_last_run', 'qc_status', 'quality_control_check_complete']
    status_report_df = status_report_df[final_columns]

    # Save the report to CSV
    report_path = output_dir / f"QC_Status_Report_{file_suffix}.csv"
    status_report_df.to_csv(report_path, index=False)
    print("Status Report Created")

    # --- Export selected columns to JSON ---
    json_columns = [
        primary_key_field,
        "redcap_event_name",
        "qc_status_complete",
        "qc_run_by",
        "qc_last_run",
        "qc_status",
        "quality_control_check_complete",
    ]
    # Ensure all columns exist
    for col in json_columns:
        if col not in status_report_df.columns:
            status_report_df[col] = ""

    json_export_df = status_report_df[json_columns]
    json_records = json_export_df.to_dict(orient="records")
    # Use upload_ready_path from config_manager instead of json_path
    if upload_ready_path:
        json_path = Path(upload_ready_path) / f"QC_Status_Report_{file_suffix}.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_records, f, indent=2)
        print("Status Report JSON File Created")
    else:
        logger.warning("Upload ready path not configured - skipping JSON export")