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

# Regex to extract the trigger variable from compatibility errors
# Pattern: "... for if {'trigger_var': {...}} then ..."
_COMPATIBILITY_TRIGGER_PATTERN = re.compile(r"for if \{'([^']+)':")

# Packet normalization for check code lookup
# Maps local packet codes to NACC's code format
_PACKET_NORMALIZATION = {"I4": "I"}

# NACC check classification lookup (loaded once at first use)
_CLASSIFICATIONS_PATH = _Path(__file__).parents[3] / "config" / "nacc_check_classifications.json"
_CHECK_LOOKUP: dict[str, str] = {}
_CHECK_DETAILS: dict[str, list[dict]] = {}  # Full check metadata by key


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
        local_lookup = data.get("lookup", {})
        # Build detailed lookup locally first — must be fully populated before
        # _CHECK_LOOKUP is set, otherwise racing threads that see _CHECK_LOOKUP
        # as truthy (early-return) would find _CHECK_DETAILS partially empty.
        local_details: dict[str, list[dict]] = {}
        for check in data.get("checks", []):
            key = f"{check['packet']}|{check['form']}|{check['variable']}|{check['check_category']}"
            if key not in local_details:
                local_details[key] = []
            local_details[key].append(check)
        # Atomically promote to globals: _CHECK_DETAILS first, _CHECK_LOOKUP last.
        # Any thread that observes _CHECK_LOOKUP as truthy will already see
        # a fully populated _CHECK_DETAILS (dict.update is a single C-level op).
        _CHECK_DETAILS.update(local_details)
        _CHECK_LOOKUP = local_lookup  # Set last — acts as the "ready" signal
        return _CHECK_LOOKUP
    except Exception:
        logger.warning("Failed to load nacc_check_classifications.json", exc_info=True)
        return {}


# Form name aliases: instrument prefix -> NACC form name(s) to try
_FORM_ALIASES: dict[str, list[str]] = {
    "c2c2t": ["c2", "c2t"],  # Combined C2/C2T instrument
    "form": ["uds header"],  # form_header -> uds header
}

# Category fallback order when primary doesn't match
_CATEGORY_FALLBACKS = ["Conformity", "Missingness", "Plausibility"]


def _extract_compatibility_trigger(error_msg: str) -> str | None:
    """Extract the trigger variable from a compatibility rule error message.

    For cross-form compatibility rules (e.g., B5→B9), NACC classifies errors
    under the TRIGGER variable (e.g., 'depd'), not the TARGET variable ('bedep').

    Example error message:
        "('bedep', ['unallowed value 0']) for if {'depd': {'allowed': [1]}}
         then {'bedep': {'allowed': [1]}} - compatibility rule no: 0"

    Returns:
        The trigger variable name (e.g., 'depd') if found, None otherwise.
    """
    match = _COMPATIBILITY_TRIGGER_PATTERN.search(error_msg)
    return match.group(1) if match else None


def _calculate_check_match_confidence(
    check: dict, error_msg: str, target_var: str, trigger_var: str | None
) -> float:
    """Calculate confidence score (0-100) for how well a check matches an error.

    Scoring breakdown:
    - 40 points: Both trigger AND target variables in description
    - 30 points: Trigger variable in description (cross-form rules)
    - 20 points: Target variable in description
    - 20 points: Condition direction matches (should/should not)
    - 10 points: Specific value constraints match
    - 5 points: Category keyword match (blank/present/equal)

    Args:
        check: NACC check dict with full_desc
        error_msg: The validation error message
        target_var: The target variable from the error (e.g., 'bedep')
        trigger_var: The trigger variable from compatibility rule (e.g., 'depd')

    Returns:
        Confidence score from 0-100
    """
    score = 0.0
    desc = check.get("full_desc", "").upper()
    error_msg_lower = error_msg.lower()
    target_upper = target_var.upper()
    trigger_upper = trigger_var.upper() if trigger_var else ""

    # 1. Variable name matching (most important)
    if trigger_upper and target_upper:
        if trigger_upper in desc and target_upper in desc:
            score += 40  # Both variables present - highly specific match
        elif trigger_upper in desc:
            score += 30  # Trigger variable match - cross-form rule
        elif target_upper in desc:
            score += 20  # Target variable match
    elif target_upper and target_upper in desc:
        score += 20  # Single variable match

    # 2. Condition direction matching (should vs should not)
    # NACC descriptions use various phrasings: "should not equal", "should not =", "should not be"
    is_forbidden_check = "'forbidden'" in error_msg_lower
    desc_is_negative = "SHOULD NOT EQUAL" in desc or "SHOULD NOT =" in desc or "SHOULD NOT BE" in desc
    if is_forbidden_check == desc_is_negative:
        score += 20

    # 3. Specific value constraint matching
    # Extract values from error message like "allowed': [1]" or "forbidden': [0, 9]"
    value_pattern = r"'(?:allowed|forbidden)':\s*\[([^\]]+)\]"
    error_values = set()
    for match in re.finditer(value_pattern, error_msg_lower):
        values_str = match.group(1)
        error_values.update(v.strip() for v in values_str.split(","))

    if error_values:
        # Check if any of these values appear in the check description
        for val in error_values:
            if val in desc.lower():
                score += 5
                break

    # 4. Fine-grained keyword/phrase matching (two tiers)
    # Tier A: Exact phrase match in error AND desc — strong signal (15 pts)
    exact_phrases = [
        ("cannot be blank", "CANNOT BE BLANK"),
        ("must be blank", "MUST BE BLANK"),
        ("must be present", "MUST BE PRESENT"),
        ("cannot be present", "CANNOT BE PRESENT"),
        ("should not equal", "SHOULD NOT EQUAL"),
        ("should equal", "SHOULD EQUAL"),
        ("should be greater", "SHOULD BE GREATER"),
        ("should be less than", "SHOULD BE LESS THAN"),
    ]
    exact_matched = False
    for phrase_lower, phrase_upper in exact_phrases:
        if phrase_lower in error_msg_lower and phrase_upper in desc:
            score += 15
            exact_matched = True
            break

    # Tier B: General keyword present in both — weaker signal (5 pts)
    if not exact_matched:
        keyword_categories = {
            "blank": "BLANK",
            "present": "PRESENT",
            "equal": "EQUAL",
            "greater": "GREATER",
            "less": "LESS",
        }
        for keyword, desc_keyword in keyword_categories.items():
            if keyword in error_msg_lower and desc_keyword in desc:
                score += 5
                break

    return score


def _match_check_to_error(checks: list[dict], error_msg: str, target_var: str) -> dict | None:
    """Find the best matching check from a list based on confidence scoring.

    Returns None if no check meets the minimum confidence threshold (50/100),
    preventing incorrect quality check assignments when ambiguous.

    Args:
        checks: List of check dicts with same base key
        error_msg: The validation error message
        target_var: The target variable from the error (e.g., 'bedep')

    Returns:
        Best matching check dict if confidence >= 50, otherwise None
    """
    if not checks:
        return None
    if len(checks) == 1:
        # Single check — the key (packet|form|variable|category) already uniquely identifies it.
        # No ambiguity to resolve, so always return it.
        return checks[0]

    # Multiple checks - need strong confidence to disambiguate
    trigger_var = _extract_compatibility_trigger(error_msg)
    scored_checks = []

    for check in checks:
        confidence = _calculate_check_match_confidence(check, error_msg, target_var, trigger_var)
        scored_checks.append((confidence, check))

    # Sort by confidence descending
    scored_checks.sort(key=lambda x: x[0], reverse=True)
    best_confidence, best_check = scored_checks[0]

    # Minimum confidence threshold: 50/100 for multiple checks
    # This prevents guessing when we can't confidently match
    if best_confidence < 50:
        logger.debug(
            "Low confidence (%.1f) matching check for variable '%s'. "
            "Found %d candidates but none meet threshold. Error: %s",
            best_confidence,
            target_var,
            len(checks),
            error_msg[:100],
        )
        return None

    # If top two scores are very close, require higher confidence
    if len(scored_checks) > 1:
        second_confidence = scored_checks[1][0]
        if best_confidence - second_confidence < 10:
            # Ambiguous - require even higher confidence
            if best_confidence < 65:
                logger.debug(
                    "Ambiguous match for variable '%s' (top scores: %.1f vs %.1f). "
                    "Skipping check assignment.",
                    target_var,
                    best_confidence,
                    second_confidence,
                )
                return None

    logger.debug(
        "Matched check with confidence %.1f for variable '%s': %s",
        best_confidence,
        target_var,
        best_check.get("check_code", ""),
    )
    return best_check


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

    # Build packets to try: original first, then normalized fallback
    # NACC has both I4-specific codes (i4vp) and common codes (ivp)
    normalized_packet = _PACKET_NORMALIZATION.get(packet, packet)
    packets_to_try = [packet, normalized_packet] if normalized_packet != packet else [packet]

    # Extract short form name from full instrument name
    # e.g., 'a1_participant_demographics' -> 'a1'
    # e.g., 'c2c2t_neuropsychological_battery_scores' -> 'c2c2t'
    form = instrument.lower().split("_")[0] if "_" in instrument else instrument.lower()
    var_lc = variable.lower()

    # Build list of variables to try
    # For compatibility rules, also try the trigger variable (cross-form checks)
    vars_to_try = [var_lc]
    trigger_var = None
    if "compatibility rule" in error_msg.lower():
        trigger_var = _extract_compatibility_trigger(error_msg)
        if trigger_var and trigger_var.lower() != var_lc:
            vars_to_try.append(trigger_var.lower())

    # Build list of forms to try (original + aliases)
    forms_to_try = [form] + _FORM_ALIASES.get(form, [])

    # Infer category from error message
    inferred_category = _infer_check_category(error_msg)

    # Try each packet/form/variable/category combination
    for try_packet in packets_to_try:
        for try_form in forms_to_try:
            for try_var in vars_to_try:
                # First try inferred category
                key = f"{try_packet}|{try_form}|{try_var}|{inferred_category}"
                checks = _CHECK_DETAILS.get(key)
                if checks:
                    check = _match_check_to_error(checks, error_msg, var_lc)
                    if check:
                        return {
                            "error_type": check.get("error_type", "error"),
                            "check_code": check.get("check_code", ""),
                            "interpretation": check.get("full_desc", ""),
                        }

                # Then try fallback categories
                for fallback_cat in _CATEGORY_FALLBACKS:
                    if fallback_cat == inferred_category:
                        continue  # Already tried
                    key = f"{try_packet}|{try_form}|{try_var}|{fallback_cat}"
                    checks = _CHECK_DETAILS.get(key)
                    if checks:
                        check = _match_check_to_error(checks, error_msg, var_lc)
                        if check:
                            return {
                                "error_type": check.get("error_type", "error"),
                                "check_code": check.get("check_code", ""),
                                "interpretation": check.get("full_desc", ""),
                            }

    # No match found
    return default


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
    datastore: Any | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate records using packet-based routing with dynamic instrument support.

    Args:
        data: DataFrame containing the data to validate.
        validation_rules: Instrument-scoped variable set used to filter per-record rules.
            Keys are the variables belonging to this instrument; used to strip
            cross-instrument bleed from the full pool returned by get_rules_for_record().
        instrument_name: Name of the instrument being validated.
        primary_key_field: Name of the primary key field.
        datastore: Optional datastore for temporal rule validation. When provided,
            enables cross-visit comparisons (H2 fix - temporal rules support).

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

            # H2 fix: Enable temporal rules when datastore is available
            schema = _build_schema_from_raw(
                resolved_rules,
                include_temporal_rules=datastore is not None,
                include_compatibility_rules=True,
            )
            qc = QualityCheck(
                pk_field=primary_key_field,
                schema=schema,
                strict=False,
                datastore=datastore,  # H2 fix: Pass datastore for temporal validation
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
                                "redcap_event_name": record_dict.get("redcap_event_name", ""),
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
