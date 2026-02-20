"""
Main pipeline for processing and validating REDCap instrument data.

This module orchestrates the entire QC process, from fetching raw data to
generating final summary reports.

The pipeline operates in clear stages:
1. **Data Fetching**: Extract data from REDCap with structured error handling
2. **Rules Loading**: Load and cache validation rules with proper error tracking
3. **Data Preparation**: Prepare instrument data with explicit result objects
4. **Validation**: Standardized per-record validation with comprehensive logging
5. **Report Generation**: Generate all reports with unified interface

MAIN ENTRY POINTS:
- `run_report_pipeline()` - Main pipeline entry point
- `validate_data()` - Production validation using hierarchical packet routing
- `validate_data_unified()` - Unified validation using packet-level rule loading
"""

import json

# Set up logging
import logging
import time
from collections.abc import Generator
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
from ..io.hierarchical_router import HierarchicalRuleResolver
from ..io.unified_rule_loader import UnifiedRuleLoader

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
            orchestrator = PipelineOrchestrator(config)
            result = orchestrator.run_pipeline()

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
            # rules. Include compatibility rules to catch cross-field logic errors.
            schema = _build_schema_from_raw(
                resolved_rules, include_temporal_rules=False, include_compatibility_rules=True
            )

            # Perform validation using existing QualityCheck engine
            qc = QualityCheck(
                pk_field=primary_key_field, schema=schema, strict=False, datastore=None
            )
            passed, sys_failure, record_errors, error_tree = qc.validate_record(record_dict)

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

            if not passed or sys_failure:

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
                                for field_errors in record_errors.values()
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





def validate_data_unified(
    data: pd.DataFrame,
    primary_key_field: str,
    instrument_name: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Unified validation using packet-level rule loading (Phase 2 - NEW).
    
    This function represents the new architecture where rules are loaded once per
    packet type rather than per instrument. It eliminates instrument-based routing
    by loading all rules for a packet at once and validating against the merged set.
    
    Key improvements over previous approaches:
    - Loads rules once per packet (not per record, not per instrument)
    - Validates against merged rule set with allow_unknown=True
    - Maintains instrument context for reporting via variable name prefixes
    - Significantly reduced overhead and simpler architecture
    
    Args:
        data: DataFrame containing the data to validate.
        primary_key_field: Name of the primary key field.
        instrument_name: Name of the instrument (optional, for logging/reporting).
    
    Returns:
        Tuple of (errors, logs, passed_records) where:
        - errors: List of validation error dictionaries
        - logs: List of validation log dictionaries
        - passed_records: List of passed record dictionaries
    """
    config = get_config()
    unified_loader = UnifiedRuleLoader(config)
    
    errors = []
    logs = []
    passed_records = []
    
    # Track performance
    start_time = time.time()
    
    # Cache for loaded packet rules (one load per packet type)
    packet_rules_cache = {}
    packet_schemas_cache = {}
    
    logger.info(
        "Starting unified validation for %s (%d records)",
        instrument_name or "mixed instruments",
        len(data),
    )
    
    for _index, record in data.iterrows():
        record_dict = record.to_dict()
        pk_value = record_dict.get(primary_key_field, "unknown")
        packet_value = record_dict.get("packet", "").upper()
        
        try:
            # Validate packet field
            if not packet_value:
                raise ValueError(
                    f"Missing packet value for record {pk_value}. "
                    "Packet-based routing requires valid packet field (I, I4, or F)."
                )
            
            # Load packet rules once per packet type (cached)
            if packet_value not in packet_rules_cache:
                logger.debug(f"Loading rules for packet {packet_value}")
                packet_rules = unified_loader.load_packet_rules(packet_value)
                packet_rules_cache[packet_value] = packet_rules
                
                # Build schema from packet rules
                from ..utils.schema_builder import _build_schema_from_raw
                
                schema = _build_schema_from_raw(
                    packet_rules,
                    include_temporal_rules=False,
                    include_compatibility_rules=True
                )
                packet_schemas_cache[packet_value] = schema
            else:
                packet_rules = packet_rules_cache[packet_value]
                schema = packet_schemas_cache[packet_value]
            
            # Get rules path for reporting
            rules_path = config.get_rules_path_for_packet(packet_value)
            
            # Perform validation with allow_unknown=True (key to unified approach)
            qc = QualityCheck(
                pk_field=primary_key_field,
                schema=schema,
                strict=False,  # Allow unknown variables
                datastore=None
            )
            passed, sys_failure, record_errors, error_tree = qc.validate_record(record_dict)
            
            # Infer instrument from variable names if not provided
            inferred_instrument = instrument_name
            if not inferred_instrument and record_errors:
                # Try to infer from first error variable (e.g., "a1_birthmo" -> "a1")
                first_var = list(record_errors.keys())[0]
                if "_" in first_var:
                    inferred_instrument = first_var.split("_")[0]
            
            # Process results
            if not passed or sys_failure:
                # Process each field that has errors
                for field_name, field_errors in record_errors.items():
                    # Infer instrument from variable name if possible
                    var_instrument = inferred_instrument
                    if "_" in field_name:
                        var_instrument = field_name.split("_")[0]
                    
                    for error_message in field_errors:
                        errors.append(
                            {
                                primary_key_field: pk_value,
                                "instrument_name": var_instrument or "unknown",
                                "variable": field_name,
                                "error_message": error_message,
                                "current_value": record_dict.get(field_name, ""),
                                "packet": packet_value,
                                "json_rule_path": rules_path,
                                "redcap_event_name": record_dict.get("redcap_event_name", ""),
                                "routing_method": "unified",  # Mark as new method
                            }
                        )
                
                logs.append(
                    {
                        primary_key_field: pk_value,
                        "instrument_name": inferred_instrument or "unknown",
                        "validation_status": "FAILED",
                        "error_count": sum(len(errs) for errs in record_errors.values()),
                        "redcap_event_name": record_dict.get("redcap_event_name", ""),
                        "packet": packet_value,
                        "routing_method": "unified",
                    }
                )
            else:
                # Record passed - log fields that have rules
                for field_name, field_value in record_dict.items():
                    # Skip metadata fields
                    if field_name in [primary_key_field, "redcap_event_name", "packet"]:
                        continue
                    
                    # Check if field has rules in packet_rules
                    if field_name in packet_rules:
                        # Infer instrument from variable name
                        var_instrument = inferred_instrument
                        if "_" in field_name:
                            var_instrument = field_name.split("_")[0]
                        
                        passed_records.append(
                            {
                                primary_key_field: pk_value,
                                "variable": field_name,
                                "current_value": field_value,
                                "json_rule": json.dumps(packet_rules[field_name]),
                                "rule_file": f"{var_instrument}_rules.json",
                                "packet": packet_value,
                                "json_rule_path": rules_path,
                                "redcap_event_name": record_dict.get("redcap_event_name", ""),
                                "instrument_name": var_instrument or "unknown",
                                "routing_method": "unified",
                            }
                        )
                
                logs.append(
                    {
                        primary_key_field: pk_value,
                        "instrument_name": inferred_instrument or "unknown",
                        "validation_status": "PASSED",
                        "error_count": 0,
                        "redcap_event_name": record_dict.get("redcap_event_name", ""),
                        "packet": packet_value,
                        "routing_method": "unified",
                    }
                )
        
        except Exception as e:
            logger.exception(f"Validation error for record {pk_value}: {e}")
            
            # Get packet for error reporting
            packet_value = record_dict.get("packet", "unknown")
            if packet_value == "unknown" or not packet_value:
                rules_path = "unknown (missing packet)"
            else:
                rules_path = config.get_rules_path_for_packet(packet_value)
            
            errors.append(
                {
                    primary_key_field: pk_value,
                    "instrument_name": instrument_name or "unknown",
                    "variable": "system_error",
                    "error_message": f"System validation error: {str(e)}",
                    "current_value": "",
                    "packet": packet_value,
                    "json_rule_path": rules_path,
                    "redcap_event_name": record_dict.get("redcap_event_name", ""),
                    "routing_method": "unified",
                }
            )
    
    # Log performance statistics
    duration = time.time() - start_time
    packets_loaded = len(packet_rules_cache)
    logger.info(
        "Unified validation complete: %d records in %.2fs (%.1f ms/record)",
        len(data),
        duration,
        (duration * 1000) / len(data) if len(data) > 0 else 0,
    )
    logger.info(
        "  Packets loaded: %d (%s)",
        packets_loaded,
        ", ".join(packet_rules_cache.keys()),
    )
    logger.info("  Passed records: %d, Errors: %d", len(passed_records), len(errors))
    
    # Log cache statistics
    cache_stats = unified_loader.get_cache_stats()
    logger.debug(
        "UnifiedRuleLoader cache stats: hits=%d, misses=%d, cached=%d",
        cache_stats["hits"],
        cache_stats["misses"],
        cache_stats["cached_packets"],
    )
    
    return errors, logs, passed_records






