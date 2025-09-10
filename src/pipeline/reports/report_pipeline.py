"""
Main pipeline for processing and validating REDCap instrument data.

This module orchestrates the entire QC process, from fetching raw data to
generating final summary reports. It provides both improved structured
pipeline execution and legacy compatibility functions.

The improved pipeline operates in clear stages:
1. **Data Fetching**: Extract data from REDCap with structured error handling
2. **Rules Loading**: Load and cache validation rules with proper error tracking
3. **Data Preparation**: Prepare instrument data with explicit result objects
4. **Validation**: Standardized per-record validation with comprehensive logging
5. **Report Generation**: Generate all reports with unified interface

MAIN ENTRY POINTS:
- `run_improved_report_pipeline()` - NEW: Structured pipeline with result objects
  (RECOMMENDED)
- `run_report_pipeline()` - LEGACY: Backward compatible interface
- `process_instruments_etl()` - LEGACY: ETL-style interface for backward
  compatibility
- `validate_data()` - UTILITY: Data validation for specific datasets

PIPELINE UTILITIES:
- `create_pipeline_orchestrator()` - Factory for pipeline orchestrator
- `validate_pipeline_config()` - Configuration validation
- `get_pipeline_status_summary()` - Status summary extraction
"""

import json

# Set up logging
import logging
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pandas as pd

from nacc_form_validator.quality_check import QualityCheck

from ..config.config_manager import (
    QCConfig,
    get_config,
    get_discriminant_variable,
    is_dynamic_rule_instrument,
)

# Import pipeline components directly
from ..core.pipeline_orchestrator import PipelineOrchestrator
from ..core.pipeline_results import PipelineExecutionResult
from ..io.hierarchical_router import HierarchicalRuleResolver

# Import packet router for enhanced validation
from ..io.packet_router import PacketRuleRouter
from ..utils.schema_builder import build_cerberus_schema_for_instrument

logger = logging.getLogger(__name__)


# =============================================================================
# PRODUCTION CLI LOGGING UTILITIES
# =============================================================================


@contextmanager
def operation_context(operation_name: str, details: str = "") -> Generator[None]:
    """Context manager for tracking CLI operations."""
    logger.info("%s: %s", operation_name.title(), details)
    start_time = time.time()
    try:
        yield
        duration = time.time() - start_time
        logger.info("%s complete (%.1f s)", operation_name.title(), duration)
    except Exception:
        logger.exception("%s failed", operation_name.title())
        raise


# =============================================================================
# IMPROVED PIPELINE IMPLEMENTATION
# =============================================================================


def run_improved_report_pipeline(config: QCConfig) -> PipelineExecutionResult:
    """
    Main entry point for the improved QC report pipeline.

    This function provides a structured, stage-based approach to pipeline execution
    with proper error handling, result objects, and clear data flow.

    Args:
        config: The configuration object for the pipeline.

    Returns:
        Complete pipeline execution result with all stage results.
    """
    try:
        with operation_context("pipeline_execute", "Running QC pipeline stages"):
            orchestrator = PipelineOrchestrator(config)
            return orchestrator.run_pipeline()

    except Exception:
        logger.exception("Pipeline execution failed")
        raise


def process_instruments_etl(
    config: QCConfig,
    output_path: str | Path | None = None,
    date_tag: str | None = None,
    time_tag: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    LEGACY: ETL-optimized processing of instruments.

    This function maintains backward compatibility by wrapping the improved
    pipeline and returning the expected tuple of DataFrames.

    Args:
        config: A `QCConfig` object containing all pipeline settings.
        output_path: Optional path to use for ETL output.
        date_tag: Optional date tag for output directory.
        time_tag: Optional time tag for output directory.

    Returns:
        A tuple of DataFrames:
        (df_errors, df_logs, df_passed, all_records_df, complete_visits_df,
         detailed_validation_logs)
    """
    logger.warning(
        "process_instruments_etl() is using the legacy interface. "
        "Consider using PipelineOrchestrator directly for better "
        "structure."
    )

    try:
        # Use improved pipeline
        orchestrator = PipelineOrchestrator(config)
        result = orchestrator.run_pipeline(output_path, date_tag, time_tag)

        if not result.success:
            _msg = "Pipeline execution failed: %s"
            raise RuntimeError(_msg % result.pipeline_error)

        # Extract data for legacy interface
        complete_visits_df = pd.DataFrame()
        if result.data_preparation.complete_visits_data:
            complete_visits_df = result.data_preparation.complete_visits_data.summary_dataframe

        return (
            result.validation.errors_df,
            result.validation.logs_df,
            result.validation.passed_df,
            result.validation.all_records_df,
            complete_visits_df,
            result.validation.validation_logs_df,
        )

    except Exception:
        logger.exception("ETL processing failed")
        raise


# =============================================================================
# LEGACY PIPELINE INTERFACE
# =============================================================================


def run_report_pipeline(config: QCConfig) -> None:
    """
    Main entry point for the QC report pipeline.

    This function orchestrates the entire process, from fetching data to
    generating the final reports using streamlined production logging.

    Args:
        config: The configuration object for the pipeline.
    """

    try:
        with operation_context("data_fetch", "Fetching REDCap data"):
            # Use the improved pipeline implementation
            result = run_improved_report_pipeline(config)

            if not result.success:
                _err_msg = f"Pipeline execution failed: {result.pipeline_error}"
                raise RuntimeError(_err_msg)

        # Log success with metrics in production format
        records_processed = f"{result.data_fetch.records_processed:,}"
        logger.info("Data retrieved: %s records", records_processed)

        # Log rules loading information
        rules_count = len(result.rules_loading.instruments_processed)
        logger.info("Rules loaded: %d rule sets for 3 packets", rules_count)

        # Log validation completion
        logger.info("Validation complete: %s records processed", records_processed)

        # Extract output directory information
        output_name = result.output_directory.name
        logger.info("Reports saved to: output/%s/", output_name)

    except Exception:
        logger.exception("Pipeline execution failed")
        raise


def _collect_processed_records_info(
    all_records_df: pd.DataFrame, validation_errors: list[dict[str, Any]], config: QCConfig
) -> tuple[int, int, dict[str, int]]:
    """
    Collect summary information about processed records.

    Args:
        all_records_df: DataFrame containing all processed records
        validation_errors: List of validation errors
        config: QC configuration

    Returns:
        Tuple of (total_records, error_records, instrument_counts)
    """
    total_records = len(all_records_df)

    # Count unique records with errors
    error_records = 0
    if validation_errors:
        error_df = pd.DataFrame(validation_errors)
        unique_error_records = error_df[config.primary_key_field].nunique()
        error_records = unique_error_records

    # Count records by instrument
    instrument_counts = {}
    if "instrument_name" in all_records_df.columns:
        instrument_counts = all_records_df["instrument_name"].value_counts().to_dict()

    return total_records, error_records, instrument_counts


# =============================================================================
# LEGACY VALIDATION FUNCTIONALITY
# =============================================================================


class _SchemaAndRulesCache:
    """
    Cache for storing and retrieving validation schemas and rules.

    This class provides caching functionality for validation schemas and rules
    to avoid repeated loading and processing during validation.
    """

    def __init__(self):
        self._cache = {}

    def _get_cache_key(self, instrument_name: str, variant: str = "") -> str:
        """Generate cache key for instrument and variant."""
        return f"{instrument_name}_{variant}" if variant else instrument_name

    def _get_cached_schema_and_rules(
        self,
        instrument_name: str,
        variant: str = "",
        fallback_func: Callable[..., tuple[dict[str, Any], dict[str, Any]]] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Get cached schema and rules, or compute and cache them.

        Args:
            instrument_name: Name of the instrument
            variant: Variant identifier for dynamic instruments
            fallback_func: Function to compute schema/rules if not cached

        Returns:
            Tuple of (schema, rules)
        """
        cache_key = self._get_cache_key(instrument_name, variant)

        if cache_key not in self._cache:
            if fallback_func:
                schema, rules = fallback_func(instrument_name, variant)
                self._cache[cache_key] = (schema, rules)
            else:
                # Default fallback
                try:
                    if is_dynamic_rule_instrument(instrument_name):
                        from ..utils.instrument_mapping import (
                            load_dynamic_rules_for_instrument,
                        )

                        dynamic_rules = load_dynamic_rules_for_instrument(instrument_name)
                        rules = dynamic_rules.get(variant, {})
                    else:
                        from ..utils.instrument_mapping import (
                            load_json_rules_for_instrument,
                        )

                        rules = load_json_rules_for_instrument(instrument_name)

                    # Build schema without temporal rules since no datastore is
                    # available
                    schema = build_cerberus_schema_for_instrument(
                        instrument_name, include_temporal_rules=False
                    )
                    self._cache[cache_key] = (schema, rules)
                except Exception as e:  # noqa: BLE001 - intentional broad catch for rule loading
                    logger.warning("Failed to load rules for %s: %s", instrument_name, e)
                    self._cache[cache_key] = ({}, {})

        return self._cache[cache_key]


# Global cache instance
_schema_rules_cache = _SchemaAndRulesCache()


class _SchemaAndRulesOptimizedCache(_SchemaAndRulesCache):
    """
    Optimized cache with additional features for better performance.
    """

    def validate_data_optimized(
        self,
        data: pd.DataFrame,
        validation_rules: dict[str, dict[str, Any]],
        instrument_name: str,
        primary_key_field: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Optimized validation using cached schemas and rules.

        Args:
            data: DataFrame to validate
            validation_rules: Validation rules dictionary
            instrument_name: Name of the instrument
            primary_key_field: Primary key field name

        Returns:
            Tuple of (errors, logs, passed_records)
        """
        errors = []
        logs = []
        passed_records = []

        for _index, record in data.iterrows():
            record_dict = record.to_dict()

            # Get schema and rules from cache - handle dynamic instruments
            # properly
            if is_dynamic_rule_instrument(instrument_name):
                # For dynamic instruments, we need to get the discriminant variable
                # value
                discriminant_var = get_discriminant_variable(instrument_name)
                discriminant_value = record_dict.get(discriminant_var, "")

                # Get the cached schema structure (which contains variants)
                schema_variants, rules = self._get_cached_schema_and_rules(instrument_name)

                # Select the appropriate schema variant
                if discriminant_value in schema_variants:
                    schema = schema_variants[discriminant_value]
                else:
                    # Fallback to first available variant if discriminant value not
                    # found
                    available_variants = list(schema_variants.keys())
                    if available_variants:
                        schema = schema_variants[available_variants[0]]
                        logger.warning(
                            "Discriminant value '%s' not found for %s, using %s",
                            discriminant_value,
                            instrument_name,
                            available_variants[0],
                        )
                    else:
                        schema = {}
                        logger.error("No schema variants available for %s", instrument_name)
            else:
                # For standard instruments, get schema directly
                schema, rules = self._get_cached_schema_and_rules(instrument_name)

            # Create QualityCheck instance without datastore (temporal rules already
            # excluded from schema)
            qc = QualityCheck(schema=schema, pk_field=primary_key_field, datastore=None)

            # Validate record
            validation_result = qc.validate_record(record_dict)

            # Process results
            pk_value = record_dict.get(primary_key_field, "unknown")

            # Check if validation failed or had system errors
            if not validation_result.passed or validation_result.sys_failure:
                # Extract errors from the ValidationResult object
                record_errors = validation_result.errors

                # Get packet value for tracking
                packet_value = record_dict.get("packet", "unknown")

                # Process each field that has errors
                for field_name, field_errors in record_errors.items():
                    for error_message in field_errors:
                        errors.append(
                            {
                                primary_key_field: pk_value,
                                "instrument_name": instrument_name,
                                "variable": field_name,
                                "error_message": error_message,
                                "current_value": record_dict.get(field_name, ""),
                                "packet": packet_value,
                                "redcap_event_name": record_dict.get("redcap_event_name", ""),
                            }
                        )

                logs.append(
                    {
                        primary_key_field: pk_value,
                        "instrument_name": instrument_name,
                        "validation_status": "FAILED",
                        "packet": packet_value,
                        "redcap_event_name": record_dict.get("redcap_event_name", ""),
                    }
                )
            else:
                # Record passed validation - capture detailed information for each
                # validated field
                packet_value = record_dict.get("packet", "unknown")
                rule_file = f"{instrument_name}_rules.json"

                # Log detailed passed validations for each field that has rules
                for field_name, field_value in record_dict.items():
                    # Skip metadata fields
                    if field_name in [primary_key_field, "redcap_event_name", "instrument_name"]:
                        continue

                    # Get the JSON rule for this field if it exists in
                    # validation_rules
                    json_rule = validation_rules.get(field_name, {})
                    if json_rule:  # Only log fields that have validation rules
                        passed_records.append(
                            {
                                primary_key_field: pk_value,
                                "variable": field_name,
                                "current_value": field_value,
                                "json_rule": json.dumps(json_rule),
                                "rule_file": rule_file,
                                "packet": packet_value,
                                "redcap_event_name": record_dict.get("redcap_event_name", ""),
                                "instrument_name": instrument_name,
                            }
                        )

                logs.append(
                    {
                        primary_key_field: pk_value,
                        "instrument_name": instrument_name,
                        "validation_status": "PASSED",
                        "packet": packet_value,
                        "redcap_event_name": record_dict.get("redcap_event_name", ""),
                    }
                )

        return errors, logs, passed_records

    def _log_validation_results_optimized(
        self, errors: list[dict[str, Any]], logs: list[dict[str, Any]], instrument_name: str
    ) -> None:
        """
        Log validation results in an optimized format.

        Args:
            errors: List of validation errors
            logs: List of validation logs
            instrument_name: Name of the instrument
        """
        total_records = len(logs)
        error_count = len(errors)
        if total_records > 0:
            success_rate = (total_records - error_count) / total_records * 100
        else:
            success_rate = 0

        logger.info("Validation completed for %s", instrument_name)
        logger.info("  Records processed: %d", total_records)
        logger.info("  Errors found: %d", error_count)
        logger.info("  Success rate: %.1f%%", success_rate)


# Global optimized cache instance
_optimized_cache = _SchemaAndRulesOptimizedCache()


def validate_data(
    data: pd.DataFrame,
    validation_rules: dict[str, dict[str, Any]],
    instrument_name: str,
    primary_key_field: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Production validation using hierarchical packet routing.

    This is the primary validation function for all QC operations.
    Uses packet-based routing (I, I4, F) with dynamic instrument support.

    Args:
        data: DataFrame containing the data to validate.
        validation_rules: Dictionary of validation rules.
        instrument_name: Name of the instrument being validated.
        primary_key_field: Name of the primary key field.

    Returns:
        Tuple of (errors, logs, passed_records) where:
        - errors: List of validation error dictionaries
        - logs: List of validation log dictionaries
        - passed_records: List of passed record dictionaries
    """
    return validate_data_with_hierarchical_routing(
        data=data,
        validation_rules=validation_rules,
        instrument_name=instrument_name,
        primary_key_field=primary_key_field,
    )


def validate_data_with_hierarchical_routing(
    data: pd.DataFrame,
    validation_rules: dict[str, dict[str, Any]],
    instrument_name: str,
    primary_key_field: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Enhanced validation with hierarchical packet + dynamic routing (Phase 2).

    This function uses the HierarchicalRuleResolver to provide intelligent rule
    resolution that combines packet-based routing (I, I4, F) with dynamic
    instrument routing (e.g., C2/C2T forms) for the most accurate validation.

    Args:
        data: DataFrame containing the data to validate.
        validation_rules: Dictionary of validation rules (legacy parameter, now ignored).
        instrument_name: Name of the instrument being validated.
        primary_key_field: Name of the primary key field.

    Returns:
        Tuple of (errors, logs, passed_records) where:
        - errors: List of validation error dictionaries
        - logs: List of validation log dictionaries
        - passed_records: List of passed record dictionaries
    """
    config = get_config()
    hierarchical_resolver = HierarchicalRuleResolver(config)

    errors = []
    logs = []
    passed_records = []

    logger.debug(
        "Starting hierarchical validation for %s with %d records",
        instrument_name,
        len(data),
    )

    for _index, record in data.iterrows():
        record_dict = record.to_dict()

        try:
            # Use hierarchical rule resolution
            resolved_rules = hierarchical_resolver.resolve_rules(record_dict, instrument_name)

            if not resolved_rules:
                logger.warning(
                    "No rules resolved for %s, skipping record %s",
                    instrument_name,
                    record_dict.get(primary_key_field, "unknown"),
                )
                continue

            # Build schema from resolved rules
            from ..utils.schema_builder import _build_schema_from_raw

            # For hierarchical routing, always use the resolved rules directly
            # The hierarchical resolver already provides flat, variant-specific
            # rules
            schema = _build_schema_from_raw(
                resolved_rules, include_temporal_rules=False, include_compatibility_rules=True
            )

            # Perform validation using existing QualityCheck engine
            qc = QualityCheck(schema=schema, pk_field=primary_key_field, datastore=None)
            validation_result = qc.validate_record(record_dict)

            # Process results using existing logic pattern
            pk_value = record_dict.get(primary_key_field, "unknown")
            packet_value = record_dict.get("packet", "unknown")

            # Get the rules path for this packet (required in production)
            if packet_value == "unknown" or not packet_value:
                _msg = (
                    "Record %s: Missing or invalid packet value. "
                    "Packet-based routing requires valid packet field "
                    "(I, I4, or F)"
                )
                raise ValueError(_msg % pk_value)
            rules_path = config.get_rules_path_for_packet(packet_value)

            # Add discriminant info for dynamic instruments
            discriminant_info = ""
            if is_dynamic_rule_instrument(instrument_name):
                discriminant_var = get_discriminant_variable(instrument_name)
                discriminant_value = record_dict.get(discriminant_var, "")
                discriminant_info = "%s=%s" % (discriminant_var, discriminant_value)

            if not validation_result.passed or validation_result.sys_failure:
                # Extract errors from the ValidationResult object
                record_errors = validation_result.errors

                # Process each field that has errors
                for field_name, field_errors in record_errors.items():
                    for error_message in field_errors:
                        errors.append(
                            {
                                primary_key_field: pk_value,
                                "instrument_name": instrument_name,
                                "variable": field_name,
                                "error_message": error_message,
                                "current_value": record_dict.get(field_name, ""),
                                "packet": packet_value,
                                "json_rule_path": rules_path,
                                "redcap_event_name": record_dict.get("redcap_event_name", ""),
                                "discriminant": discriminant_info,  # Enhanced routing info
                            }
                        )

                logs.append(
                    {
                        primary_key_field: pk_value,
                        "instrument_name": instrument_name,
                        "validation_status": "FAILED",
                        "error_count": len(
                            [
                                err
                                for field_errors in validation_result.errors.values()
                                for err in field_errors
                            ]
                        ),
                        "redcap_event_name": record_dict.get("redcap_event_name", ""),
                        "packet": packet_value,
                        "discriminant": discriminant_info,
                    }
                )
            else:
                # Record passed validation - capture detailed information for each
                # validated field
                rule_file = f"{instrument_name}_rules.json"

                # Log detailed passed validations for each field that has rules
                for field_name, field_value in record_dict.items():
                    # Skip metadata fields
                    if field_name in [primary_key_field, "redcap_event_name", "instrument_name"]:
                        continue

                    # Get the JSON rule for this field if it exists in
                    # resolved_rules
                    json_rule = resolved_rules.get(field_name, {})
                    if json_rule:  # Only log fields that have validation rules
                        passed_records.append(
                            {
                                primary_key_field: pk_value,
                                "variable": field_name,
                                "current_value": field_value,
                                "json_rule": json.dumps(json_rule),
                                "rule_file": rule_file,
                                "packet": packet_value,
                                "json_rule_path": rules_path,
                                "redcap_event_name": record_dict.get("redcap_event_name", ""),
                                "instrument_name": instrument_name,
                                "discriminant": discriminant_info,
                            }
                        )

                logs.append(
                    {
                        primary_key_field: pk_value,
                        "instrument_name": instrument_name,
                        "validation_status": "PASSED",
                        "error_count": 0,
                        "redcap_event_name": record_dict.get("redcap_event_name", ""),
                        "packet": packet_value,
                        "discriminant": discriminant_info,
                    }
                )

        except Exception as e:
            pk_value = record_dict.get(primary_key_field, "unknown")
            logger.exception("Validation error for record %s", pk_value)

            packet_value = record_dict.get("packet", "unknown")
            packet_value = record_dict.get("packet", "unknown")
            if packet_value == "unknown" or not packet_value:
                rules_path = "unknown (missing packet)"
            else:
                rules_path = config.get_rules_path_for_packet(packet_value)

                errors.append(
                    {
                        primary_key_field: pk_value,
                        "instrument_name": instrument_name,
                        "variable": "system_error",
                        "error_message": "System validation error: %s" % str(e),
                        "current_value": "",
                        "packet": packet_value,
                        "json_rule_path": rules_path,
                        "redcap_event_name": record_dict.get("redcap_event_name", ""),
                        "discriminant": "",
                    }
                )

    logger.debug(
        "Hierarchical validation completed: %d errors, %d passed",
        len(errors),
        len(passed_records),
    )
    return errors, logs, passed_records


def validate_data_with_packet_routing(
    data: pd.DataFrame,
    validation_rules: dict[str, dict[str, Any]],
    instrument_name: str,
    primary_key_field: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Enhanced validation with packet-based routing.

    This function routes each record to the appropriate rule set based on its
    packet value (I, I4, F) while maintaining compatibility with existing
    dynamic instrument routing (e.g., C2/C2T forms).

    Args:
        data: DataFrame containing the data to validate.
        validation_rules: Dictionary of validation rules (legacy parameter, now ignored).
        instrument_name: Name of the instrument being validated.
        primary_key_field: Name of the primary key field.

    Returns:
        Tuple of (errors, logs, passed_records) where:
        - errors: List of validation error dictionaries
        - logs: List of validation log dictionaries
        - passed_records: List of passed record dictionaries
    """
    config = get_config()
    packet_router = PacketRuleRouter(config)

    errors = []
    logs = []
    passed_records = []

    logger.debug(
        "Starting packet-based validation for %s with %d records",
        instrument_name,
        len(data),
    )

    for _index, record in data.iterrows():
        record_dict = record.to_dict()

        try:
            # Get packet-specific rules
            packet_rules = packet_router.get_rules_for_record(record_dict, instrument_name)

            if not packet_rules:
                logger.warning(
                    "No rules found for %s, skipping record %s",
                    instrument_name,
                    record_dict.get(primary_key_field, "unknown"),
                )
                continue

            # Handle dynamic routing for instruments like C2/C2T
            final_rules = packet_rules
            if is_dynamic_rule_instrument(instrument_name):
                discriminant_var = get_discriminant_variable(instrument_name)
                discriminant_value = record_dict.get(discriminant_var, "")
                if discriminant_value in packet_rules:
                    final_rules = packet_rules[discriminant_value]
                    logger.debug(
                        "Using dynamic rules for %s=%s",
                        discriminant_var,
                        discriminant_value,
                    )
                else:
                    logger.debug(
                        "Dynamic discriminant value '%s' not found, using base rules",
                        discriminant_value,
                    )

            # Build schema from rules
            from ..utils.schema_builder import (
                build_cerberus_schema_for_instrument,
            )

            try:
                # Try to build schema from rules directly
                schema = build_cerberus_schema_for_instrument(
                    instrument_name,
                    include_temporal_rules=False,
                )
                # Update schema with packet-specific rules if different
                if final_rules != packet_rules:
                    # For dynamic instruments, we need to merge the specific variant rules
                    # This is a simplified approach - in production, you'd want more
                    # sophisticated merging
                    schema.update(final_rules)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to build schema for %s: %s, using rules directly",
                    instrument_name,
                    "error",
                )
                schema = final_rules

            # Perform validation using existing QualityCheck engine
            qc = QualityCheck(schema=schema, pk_field=primary_key_field, datastore=None)
            validation_result = qc.validate_record(record_dict)

            # Process results using existing logic pattern
            pk_value = record_dict.get(primary_key_field, "unknown")
            packet_value = record_dict.get("packet", "unknown")

            if not validation_result.passed or validation_result.sys_failure:
                # Extract errors from the ValidationResult object
                record_errors = validation_result.errors

                # Get the packet-specific rules path for error tracking
                packet_value = record_dict.get("packet", "unknown")
                if packet_value == "unknown" or not packet_value:
                    rules_path = "unknown (missing packet)"
                else:
                    rules_path = config.get_rules_path_for_packet(packet_value)

                # Process each field that has errors
                for field_name, field_errors in record_errors.items():
                    for error_message in field_errors:
                        errors.append(
                            {
                                primary_key_field: pk_value,
                                "instrument_name": instrument_name,
                                "variable": field_name,
                                "error_message": error_message,
                                "current_value": record_dict.get(field_name, ""),
                                "packet": packet_value,
                                "json_rule_path": rules_path,
                                "redcap_event_name": record_dict.get("redcap_event_name", ""),
                            }
                        )

                logs.append(
                    {
                        primary_key_field: pk_value,
                        "instrument_name": instrument_name,
                        "validation_status": "FAILED",
                        "redcap_event_name": record_dict.get("redcap_event_name", ""),
                        "packet": packet_value,
                    }
                )
            else:
                # Record passed validation - capture detailed information for each
                # validated field
                packet_value = record_dict.get("packet", "unknown")
                if packet_value == "unknown" or not packet_value:
                    rules_path = "unknown (missing packet)"
                else:
                    rules_path = config.get_rules_path_for_packet(packet_value)
                rule_file = f"{instrument_name}_rules.json"

                # Log detailed passed validations for each field that has rules
                for field_name, field_value in record_dict.items():
                    # Skip metadata fields
                    if field_name in [primary_key_field, "redcap_event_name", "instrument_name"]:
                        continue

                    # Get the JSON rule for this field if it exists in
                    # final_rules
                    json_rule = final_rules.get(field_name, {})
                    if json_rule:  # Only log fields that have validation rules
                        passed_records.append(
                            {
                                primary_key_field: pk_value,
                                "variable": field_name,
                                "current_value": field_value,
                                "json_rule": json.dumps(json_rule),
                                "rule_file": rule_file,
                                "packet": packet_value,
                                "json_rule_path": rules_path,
                                "redcap_event_name": record_dict.get("redcap_event_name", ""),
                                "instrument_name": instrument_name,
                            }
                        )

                logs.append(
                    {
                        primary_key_field: pk_value,
                        "instrument_name": instrument_name,
                        "validation_status": "PASSED",
                        "redcap_event_name": record_dict.get("redcap_event_name", ""),
                        "packet": packet_value,
                    }
                )

        except Exception as e:
            logger.exception(
                "Error validating record %s",
                record_dict.get(primary_key_field, "unknown"),
            )
            # Add system error entry
            packet_value = record_dict.get("packet", "unknown")
            if packet_value == "unknown" or not packet_value:
                rules_path = "unknown (missing packet)"
            else:
                rules_path = config.get_rules_path_for_packet(packet_value)

            errors.append(
                {
                    primary_key_field: record_dict.get(primary_key_field, "unknown"),
                    "instrument_name": instrument_name,
                    "variable": "system",
                    "error_message": "System error during validation: %s" % str(e),
                    "current_value": "",
                    "packet": packet_value,
                    "json_rule_path": rules_path,
                    "redcap_event_name": record_dict.get("redcap_event_name", ""),
                }
            )

    logger.info(
        "Packet-based validation complete for %s: %d passed, %d errors",
        instrument_name,
        len(passed_records),
        len(errors),
    )

    return errors, logs, passed_records


def _get_schema_and_rules_for_record(
    record: dict[str, Any], instrument_name: str, validation_rules_cache: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Get validation schema and rules for a specific record.

    Args:
        record: Record dictionary
        instrument_name: Name of the instrument
        validation_rules_cache: Cache of validation rules

    Returns:
        Tuple of (schema, rules)
    """
    if is_dynamic_rule_instrument(instrument_name):
        # For dynamic instruments, determine the discriminant variable
        discriminant_variable = get_discriminant_variable(instrument_name)
        discriminant_value = record.get(discriminant_variable, "")
        cache_key = f"{instrument_name}_{discriminant_value}"
    else:
        cache_key = instrument_name

    rules = validation_rules_cache.get(cache_key, {})
    # Build schema without temporal rules since no datastore is available
    schema = build_cerberus_schema_for_instrument(instrument_name, include_temporal_rules=False)

    return schema, rules


def _log_validation_results(
    errors: list[dict[str, Any]],
    pass_fail_log: list[dict[str, Any]],
    instrument_name: str,
    pk_field: str,
    validation_rules: dict[str, dict[str, Any]],
    rule_file: str,
    event: str = "",
) -> None:
    """
    Log detailed validation results.

    Args:
        errors: List of validation errors
        pass_fail_log: List of pass/fail logs
        instrument_name: Name of the instrument
        pk_field: Primary key field name
        validation_rules: Validation rules dictionary
        rule_file: Name of the rule file
        event: REDCap event name
    """
    total_records = len(pass_fail_log)
    error_count = len(errors)
    success_count = total_records - error_count

    logger.info("Validation results for %s (event: %s)", instrument_name, event)
    logger.info("  Total records: %d", total_records)
    logger.info("  Successful validations: %d", success_count)
    logger.info("  Failed validations: %d", error_count)
    logger.info("  Rule file: %s", rule_file)

    if error_count > 0:
        # Log sample errors
        sample_errors = errors[:5]  # Show first 5 errors
        logger.info("  Sample errors:")
        for error in sample_errors:
            pk_val = error.get(pk_field, "unknown")
            var = error.get("variable", "unknown")
            message = error.get("error_message", "unknown")
            logger.info("    %s: %s - %s", pk_val, var, message)

        # Add detailed error information to errors list
        for error in errors:
            pk_val = error.get(pk_field, "unknown")
            var = error.get("variable", "unknown")
            current_val = error.get("current_value", "")

            # Extract rule information
            var_rules = validation_rules.get(var, {})

            # Add to pass_fail_log for detailed tracking
            pass_fail_log.append(
                {
                    pk_field: pk_val,
                    "variable": var,
                    "current_value": current_val,
                    "json_rule": json.dumps(var_rules),
                    "rule_file": rule_file,
                    "redcap_event_name": event,
                    "instrument_name": instrument_name,
                }
            )


# =============================================================================
# PIPELINE FACTORY FUNCTIONS
# =============================================================================


def create_pipeline_orchestrator(config: QCConfig) -> PipelineOrchestrator:
    """
    Factory function to create a pipeline orchestrator.

    Args:
        config: QC configuration object.

    Returns:
        Configured pipeline orchestrator.
    """
    return PipelineOrchestrator(config)


def run_pipeline_stage_by_stage(
    config: QCConfig, stop_after_stage: str | None = None
) -> PipelineExecutionResult:
    """
    Run pipeline with option to stop after a specific stage (useful for debugging).

    Args:
        config: QC configuration object.
        stop_after_stage: Stage to stop after ('data_fetch', 'rules_loading',
                         'data_preparation', 'validation', 'report_generation').
                         If None, runs complete pipeline.

    Returns:
        Pipeline execution result (potentially partial if stopped early).
    """
    orchestrator = PipelineOrchestrator(config)

    if stop_after_stage is None:
        return orchestrator.run_pipeline()

    # Implement partial execution for debugging
    # This would require modifications to the orchestrator
    logger.info("Running pipeline until stage: %s", stop_after_stage)
    msg = "Partial pipeline execution not yet implemented"
    raise NotImplementedError(msg)


# =============================================================================
# PIPELINE MONITORING AND UTILITIES
# =============================================================================


def validate_pipeline_config(config: QCConfig) -> bool:
    """
    Validate pipeline configuration before execution.

    Args:
        config: QC configuration to validate.

    Returns:
        True if configuration is valid, False otherwise.
    """
    try:
        # Basic validation
        if not config.instruments:
            logger.error("No instruments specified in configuration")
            return False

        if not config.primary_key_field:
            logger.error("No primary key field specified in configuration")
            return False

        if not config.output_path:
            logger.error("No output path specified in configuration")
            return False

        # Check output path exists or can be created
        output_path = Path(config.output_path)
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.exception("Cannot create output directory %s", output_path)
            return False

        logger.info("Pipeline configuration validation passed")
        return True

    except Exception:
        logger.exception("Configuration validation failed")
        return False


def get_pipeline_status_summary(result: PipelineExecutionResult) -> dict:
    """
    Get a simplified status summary from pipeline result.

    Args:
        result: Pipeline execution result.

    Returns:
        Dictionary with simplified status information.
    """
    return {
        "success": result.success,
        "execution_time": f"{result.total_execution_time:.2f}s",
        "records_processed": result.data_fetch.records_processed,
        "errors_found": result.validation.total_errors,
        "reports_created": result.report_generation.total_files_created,
        "output_directory": str(result.output_directory),
        "stage_status": {
            "data_fetch": result.data_fetch.success,
            "rules_loading": result.rules_loading.success,
            "data_preparation": result.data_preparation.success,
            "validation": result.validation.success,
            "report_generation": result.report_generation.success,
        },
    }
