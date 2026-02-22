"""Report pipeline — thin orchestration layer over core.pipeline."""

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import pandas as pd

from nacc_form_validator.quality_check import QualityCheck

from ..config.config_manager import (
    QCConfig,
    get_config,
    get_discriminant_variable,
    is_dynamic_rule_instrument,
)
from ..core.pipeline import run_pipeline
from ..io.rule_loader import get_rules_for_record
from ..utils.schema_builder import _build_schema_from_raw

logger = logging.getLogger(__name__)


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


def run_report_pipeline(config: QCConfig) -> None:
    """Run the full QC pipeline and log a brief summary."""
    try:
        result = run_pipeline(config)
        if not result["success"]:
            raise RuntimeError(f"Pipeline execution failed: {result['error']}")
        logger.info("Data retrieved: %s records", f"{result['records_fetched']:,}")
        logger.info("Reports saved to: %s", result["output_dir"].name)
    except Exception:
        logger.exception("Pipeline execution failed")
        raise


def validate_data(
    data: pd.DataFrame,
    validation_rules: dict[str, dict[str, Any]],
    instrument_name: str,
    primary_key_field: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate records using packet-based routing with dynamic instrument support.

    Args:
        data: DataFrame containing the data to validate.
        validation_rules: Legacy parameter (ignored — rules resolved per-record).
        instrument_name: Name of the instrument being validated.
        primary_key_field: Name of the primary key field.

    Returns:
        Tuple of (errors, logs, passed_records).
    """
    config = get_config()
    errors: list[dict[str, Any]] = []
    logs: list[dict[str, Any]] = []
    passed_records: list[dict[str, Any]] = []

    for _idx, record in data.iterrows():
        record_dict = record.to_dict()
        pk_value = record_dict.get(primary_key_field, "unknown")
        packet_value = record_dict.get("packet", "")

        try:
            resolved_rules = get_rules_for_record(record_dict, instrument_name)
            if not resolved_rules:
                logger.warning("No rules for %s, skipping %s", instrument_name, pk_value)
                continue

            schema = _build_schema_from_raw(
                resolved_rules, include_temporal_rules=False, include_compatibility_rules=True
            )
            qc = QualityCheck(
                pk_field=primary_key_field,
                schema=schema,
                strict=False,
                datastore=None,
            )
            passed, sys_failure, record_errors, _error_tree = qc.validate_record(record_dict)

            rules_path = (
                config.get_rules_path_for_packet(packet_value) if packet_value else "unknown"
            )

            discriminant_info = ""
            if is_dynamic_rule_instrument(instrument_name):
                d_var = get_discriminant_variable(instrument_name)
                discriminant_info = f"{d_var}={record_dict.get(d_var, '')}"

            if not passed or sys_failure:
                for field_name, field_errors in record_errors.items():
                    for msg in field_errors:
                        errors.append(
                            {
                                primary_key_field: pk_value,
                                "instrument_name": instrument_name,
                                "variable": field_name,
                                "error_message": msg,
                                "current_value": record_dict.get(field_name, ""),
                                "packet": packet_value,
                                "json_rule_path": rules_path,
                                "redcap_event_name": record_dict.get("redcap_event_name", ""),
                                "discriminant": discriminant_info,
                            }
                        )
                logs.append(
                    {
                        primary_key_field: pk_value,
                        "instrument_name": instrument_name,
                        "validation_status": "FAILED",
                        "error_count": sum(len(e) for e in record_errors.values()),
                        "redcap_event_name": record_dict.get("redcap_event_name", ""),
                        "packet": packet_value,
                        "discriminant": discriminant_info,
                    }
                )
            else:
                passed_records.append(
                    {
                        primary_key_field: pk_value,
                        "instrument_name": instrument_name,
                        "packet": packet_value,
                        "redcap_event_name": record_dict.get("redcap_event_name", ""),
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
            logger.exception("Validation error for record %s", pk_value)
            errors.append(
                {
                    primary_key_field: pk_value,
                    "instrument_name": instrument_name,
                    "variable": "system_error",
                    "error_message": f"System validation error: {e}",
                    "current_value": "",
                    "packet": packet_value,
                    "json_rule_path": (
                        config.get_rules_path_for_packet(packet_value)
                        if packet_value
                        else "unknown"
                    ),
                    "redcap_event_name": record_dict.get("redcap_event_name", ""),
                    "discriminant": "",
                }
            )

    return errors, logs, passed_records
