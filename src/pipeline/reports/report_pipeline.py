"""Report pipeline — thin orchestration layer over core.pipeline."""

import json as _json
import logging
import re
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path as _Path
from typing import Any

import pandas as pd

from nacc_form_validator.quality_check import QualityCheck

from ..config.config_manager import (
    QCConfig,
    get_config,
)
from ..core.pipeline import run_pipeline
from ..io.rule_loader import _NAMESPACE_DISCRIMINANTS, get_rules_for_record
from ..utils.schema_builder import _build_schema_from_raw

logger = logging.getLogger(__name__)

# Regex to extract actual failing variable from compatibility error messages
# Pattern: "('variable_name', [...]) for if {...} then/else {...} - compatibility rule no: X"
_COMPATIBILITY_ERROR_PATTERN = re.compile(r"^\('([^']+)',\s*\[")

# NACC check classification lookup (loaded once at first use)
_CLASSIFICATIONS_PATH = _Path(__file__).parents[3] / "config" / "nacc_check_classifications.json"
_CHECK_LOOKUP: dict[str, str] = {}
_CHECK_DETAILS: dict[str, dict] = {}  # Full check metadata by key


def _infer_check_category(error_msg: str) -> str:
    """Infer check category from error message.

    Args:
        error_msg: The validation error message

    Returns:
        'Missingness', 'Plausibility', or 'Conformity' (default)
    """
    msg_lc = error_msg.lower()
    # Missingness: presence/absence rules
    if any(
        p in msg_lc
        for p in (
            "cannot be blank",
            "must be blank",
            "must be present",
            "conditionally present",
            "conditionally blank",
            "cannot be empty",
            "required field",
        )
    ):
        return "Missingness"
    # Plausibility: logic/temporal/compatibility rules
    if any(
        p in msg_lc
        for p in (
            "temporalrules",
            "compatibility rule",
            "should not equal",
            "should equal",
            "should be less than",
            "should be greater",
        )
    ):
        return "Plausibility"
    # Default: value/range checks
    return "Conformity"


def _load_check_lookup() -> dict[str, str]:
    """Load the pre-scraped NACC check classifications lookup.

    Returns:
        Dict mapping '{packet}|{form}|{variable}|{category}' -> 'alert' or 'error'.
        Returns empty dict on any error.
    """
    global _CHECK_LOOKUP, _CHECK_DETAILS
    if _CHECK_LOOKUP:
        return _CHECK_LOOKUP
    if not _CLASSIFICATIONS_PATH.exists():
        logger.warning(
            "nacc_check_classifications.json not found. "
            "Run: python src/scrapper/convert_csv_to_json.py"
        )
        return {}
    try:
        data = _json.loads(_CLASSIFICATIONS_PATH.read_text(encoding="utf-8"))
        _CHECK_LOOKUP = data.get("lookup", {})
        # Build detailed lookup from checks array
        for check in data.get("checks", []):
            key = f"{check['packet']}|{check['form']}|{check['variable']}|{check['check_category']}"
            _CHECK_DETAILS[key] = check
        return _CHECK_LOOKUP
    except Exception:
        logger.warning("Failed to load nacc_check_classifications.json", exc_info=True)
        return {}


def _get_nacc_check_info(packet: str, instrument: str, variable: str, error_msg: str) -> dict:
    """Return full NACC check metadata for this failure.

    Args:
        packet: Packet code ('I', 'I4', 'F', 'M')
        instrument: Instrument name (e.g., 'a1_participant_demographics')
        variable: Variable name (e.g., 'zip')
        error_msg: The error message string

    Returns:
        Dict with keys: error_type, check_code, interpretation
    """
    lookup = _load_check_lookup()
    default = {"error_type": "error", "check_code": "", "interpretation": ""}
    if not lookup:
        return default

    # Extract short form name from full instrument name
    # e.g., 'a1_participant_demographics' -> 'a1'
    # e.g., 'c2c2t_neuropsychological_battery_scores' -> 'c2c2t'
    form = instrument.lower().split("_")[0] if "_" in instrument else instrument.lower()

    category = _infer_check_category(error_msg)
    key = f"{packet}|{form}|{variable.lower()}|{category}"
    
    check = _CHECK_DETAILS.get(key)
    if check:
        return {
            "error_type": check.get("error_type", "error"),
            "check_code": check.get("check_code", ""),
            "interpretation": check.get("full_desc", ""),
        }
    # Fallback: at least return error_type from simple lookup
    return {
        "error_type": lookup.get(key, "error"),
        "check_code": "",
        "interpretation": "",
    }


def _get_nacc_check_type(packet: str, instrument: str, variable: str, error_msg: str) -> str:
    """Return 'alert' or 'error' for this failure (backward compatibility)."""
    return _get_nacc_check_info(packet, instrument, variable, error_msg)["error_type"]


def _extract_failing_variable(field_name: str, error_msg: str) -> str:
    """
    Extract the actual failing variable from compatibility rule error messages.
    
    Bug fix for nacc-form-validator compatibility rule error reporting:
    When a compatibility rule fails, the error is logged under the trigger variable
    (IF clause), but the error message contains the actual failing variable (THEN/ELSE clause).
    
    Example error message:
        "('apraxsp', ['unallowed value 0']) for if {'othersign': {'allowed': [1]}} 
         then {'apraxsp': {'allowed': [1, 2, 3]}} - compatibility rule no: 0"
    
    In this case:
        - field_name = 'othersign' (trigger variable)
        - actual failing variable = 'apraxsp' (extracted from error message)
    
    Args:
        field_name: The field name from validator.errors (trigger variable)
        error_msg: The error message string
    
    Returns:
        The actual failing variable if it's a compatibility error, otherwise field_name
    """
    if "compatibility rule no:" in error_msg:
        match = _COMPATIBILITY_ERROR_PATTERN.match(error_msg)
        if match:
            return match.group(1)
    return field_name


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
        validation_rules: Instrument-scoped variable set used to filter per-record rules.
            Keys are the variables belonging to this instrument; used to strip
            cross-instrument bleed from the full pool returned by get_rules_for_record().
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
            # Filter to only this instrument's variables — validation_rules keys are
            # correctly scoped by _build_rules_cache_from_pool(); this eliminates
            # cross-instrument bleed while preserving C2/C2T namespace resolution.
            if validation_rules:
                resolved_rules = {k: v for k, v in resolved_rules.items() if k in validation_rules}
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
            disc_var = _NAMESPACE_DISCRIMINANTS.get(instrument_name)
            if disc_var:
                discriminant_info = f"{disc_var}={record_dict.get(disc_var, '')}"

            if not passed or sys_failure:
                for field_name, field_errors in record_errors.items():
                    for msg in field_errors:
                        # Extract actual failing variable from compatibility errors
                        # (fixes bug where trigger variable is logged instead of failing variable)
                        actual_variable = _extract_failing_variable(field_name, msg)
                        
                        # Get full NACC check metadata (error_type, check_code, interpretation)
                        nacc_info = _get_nacc_check_info(
                            packet_value, instrument_name, actual_variable, msg
                        )
                        
                        errors.append(
                            {
                                primary_key_field: pk_value,
                                "instrument_name": instrument_name,
                                "variable": actual_variable,
                                "error_message": msg,
                                "current_value": record_dict.get(actual_variable, ""),
                                "packet": packet_value,
                                "json_rule_path": rules_path,
                                "redcap_event_name": record_dict.get(
                                    "redcap_event_name", ""
                                ),
                                "redcap_repeat_instance": record_dict.get(
                                    "redcap_repeat_instance", ""
                                ),
                                "visitdate": record_dict.get("visitdate", ""),
                                "qc_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "discriminant": discriminant_info,
                                "nacc_check_code": nacc_info["check_code"],
                                "nacc_check_type": nacc_info["error_type"],
                                "nacc_interpretation": nacc_info["interpretation"],
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
                    "redcap_repeat_instance": record_dict.get("redcap_repeat_instance", ""),
                    "visitdate": record_dict.get("visitdate", ""),
                    "qc_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "discriminant": "",
                }
            )

    return errors, logs, passed_records
