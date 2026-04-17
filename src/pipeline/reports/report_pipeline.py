"""Report pipeline — per-record validation with REDCap variable context enrichment."""

import csv
import json as _json
import logging
import re
import threading
from datetime import datetime
from pathlib import Path as _Path
from typing import Any

import pandas as pd

from nacc_form_validator.quality_check import QualityCheck

from ..config.config_manager import get_config
from ..io.rule_loader import _NAMESPACE_DISCRIMINANTS, get_rules_for_record
from ..utils.schema_builder import _build_schema_from_raw

logger = logging.getLogger(__name__)

# Regex to extract actual failing variable from compatibility error messages
# Pattern: "('variable_name', [...]) for if {...} then/else {...} - compatibility rule no: X"
_COMPATIBILITY_ERROR_PATTERN = re.compile(r"^\('([^']+)',\s*\[")

# Regex to extract the trigger variable from compatibility errors
# Pattern: "... for if {'trigger_var': {...}} then ..."
_COMPATIBILITY_TRIGGER_PATTERN = re.compile(r"for if \{'([^']+)':")

# Regex to collect every variable key from compatibility rule clause text.
# Variable names appear as first-level dict keys with dict values:
#   'varname': { ...constraint... }
# Inner constraint keys (e.g. 'allowed') have list values and do NOT match.
_COMPAT_VAR_KEYS_PATTERN = re.compile(r"'([^']+)':\s*\{")

# HTML tag pattern — used to strip markup from field labels
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

# Error message phrases that indicate a simple missingness failure.
# These only need field_label context; choices add no value.
_MISSINGNESS_PHRASES = frozenset(
    [
        "null value not allowed",
        "cannot be blank",
        "must be present",
        "required field",
        "cannot be empty",
        "must be blank",
        "conditionally present",
        "conditionally blank",
    ]
)

# REDCap data dictionary — loaded once at first use
_CONTEXT_DIR = _Path(__file__).parents[3] / "config" / "context"
_DATA_DICT: dict[str, dict] = {}  # variable (lowercase) -> {form, field_label, choices}
_DATA_DICT_LOADED = False
_DATA_DICT_LOCK = threading.Lock()


def _strip_html(text: str) -> str:
    """Remove HTML tags from text. Fast-paths strings with no '<'."""
    if "<" not in text:
        return text
    return _HTML_TAG_PATTERN.sub("", text).strip()


def _load_data_dict() -> dict[str, dict]:
    """Load the REDCap data dictionary CSV from config/context/.

    Picks the first CSV found in the directory. Strips HTML from field labels
    and choices at load time so lookup is clean. Thread-safe via double-checked
    locking. Returns empty dict on any error.
    """
    global _DATA_DICT, _DATA_DICT_LOADED
    if _DATA_DICT_LOADED:
        return _DATA_DICT
    with _DATA_DICT_LOCK:
        if _DATA_DICT_LOADED:  # re-check after acquiring lock
            return _DATA_DICT

        csv_files = sorted(_CONTEXT_DIR.glob("*.csv"))
        if not csv_files:
            logger.debug("No data dictionary CSV found in %s", _CONTEXT_DIR)
            _DATA_DICT_LOADED = True
            return _DATA_DICT

        csv_path = csv_files[0]
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                with csv_path.open(encoding=encoding) as f:
                    for row in csv.DictReader(f):
                        var = row.get("Variable / Field Name", "").strip().lower()
                        if not var:
                            continue
                        raw_label = row.get("Field Label", "").strip()
                        raw_choices = row.get("Choices, Calculations, OR Slider Labels", "").strip()
                        _DATA_DICT[var] = {
                            "form": row.get("Form Name", "").strip(),
                            "field_label": _strip_html(raw_label).replace("\xa0", " ").strip(),
                            "choices": _strip_html(raw_choices),
                        }
                logger.debug(
                    "Loaded data dictionary: %d variables from %s", len(_DATA_DICT), csv_path.name
                )
                break
            except UnicodeDecodeError:
                continue
            except Exception:
                logger.warning("Failed to load data dictionary from %s", csv_path, exc_info=True)
                break

        _DATA_DICT_LOADED = True
    return _DATA_DICT


def _is_missingness_error(error_msg: str) -> bool:
    """True when the error message describes a blank/null requirement."""
    msg_lc = error_msg.lower()
    return any(p in msg_lc for p in _MISSINGNESS_PHRASES)


def _build_variable_context(variable: str, error_msg: str) -> str:
    """Build a JSON context string for the variable(s) involved in this error.

    For simple missingness failures (null/blank), returns only field_label —
    choices and form add no value when the expected answer is simply "fill it in."

    For all other errors, returns the full entry: variable, form, field_label,
    and choices (when present). For compatibility rule errors, all involved
    variables (failing + trigger) are included as a JSON array.

    Returns an empty string when the data dictionary is unavailable or the
    variable is not found.
    """
    dd = _load_data_dict()
    if not dd:
        return ""

    is_miss = _is_missingness_error(error_msg)
    is_compat = "compatibility rule" in error_msg.lower()

    # Collect all variables to include
    vars_to_include: list[str] = [variable.lower()]
    if is_compat:
        for v in _extract_all_compatibility_variables(error_msg):
            if v not in vars_to_include:
                vars_to_include.append(v)

    def _entry(var: str) -> dict | None:
        info = dd.get(var)
        if not info:
            return None
        if is_miss and not is_compat:
            # Missingness: field label is sufficient context
            return {"variable": var, "field_label": info["field_label"]}
        entry: dict = {
            "variable": var,
            "form": info["form"],
            "field_label": info["field_label"],
        }
        if info["choices"]:
            entry["choices"] = info["choices"]
        return entry

    entries = [e for v in vars_to_include if (e := _entry(v)) is not None]

    if not entries:
        return ""
    if len(entries) == 1:
        return _json.dumps(entries[0])
    return _json.dumps(entries)


def _extract_compatibility_trigger(error_msg: str) -> str | None:
    """Extract the trigger variable from a compatibility rule error message.

    For cross-form compatibility rules (e.g., B5->B9), the trigger variable
    is in the if-clause of the error message.

    Example:
        "('bedep', ['unallowed value 0']) for if {'depd': {'allowed': [1]}}
         then {'bedep': {'allowed': [1]}} - compatibility rule no: 0"

    Returns 'depd', or None if not found.
    """
    match = _COMPATIBILITY_TRIGGER_PATTERN.search(error_msg)
    return match.group(1) if match else None


def _extract_all_compatibility_variables(error_msg: str) -> list[str]:
    """Extract every variable name referenced in a compatibility rule error message.

    Scans the full ``for if ... then/else ...`` clause text and collects every
    dict key whose value is itself a dict (i.e. a constraint object such as
    ``{'allowed': [...]}``).  Inner constraint keys like ``allowed`` have list
    values and are therefore *not* matched.

    Returns a de-duplicated, order-preserving list (all lowercase).  Variables
    appear in clause order: IF-clause variables first, then THEN/ELSE-clause
    variables.

    Example::

        "('lmndist', [...]) for if {'othersign': {'allowed': [1]}} then
         {'limbaprax': {'allowed': [1,2,3]}, 'lmndist': {'allowed': [1,2,3]}, ...}
         - compatibility rule no: 2"
        → ['othersign', 'limbaprax', 'lmndist', ...]
    """
    m = re.search(r"for if (.+?) - compatibility rule no:", error_msg, re.DOTALL)
    if not m:
        return []
    clause_text = m.group(1)
    seen: set[str] = set()
    result: list[str] = []
    for name in _COMPAT_VAR_KEYS_PATTERN.findall(clause_text):
        name_lc = name.lower()
        if name_lc not in seen:
            seen.add(name_lc)
            result.append(name_lc)
    return result


def _get_field_label(variable: str) -> str:
    """Return the field label for a variable, or empty string if not found."""
    dd = _load_data_dict()
    info = dd.get(variable.lower())
    return info["field_label"] if info else ""


def _extract_failing_variable(field_name: str, error_msg: str) -> str:
    """Extract the actual failing variable from compatibility rule error messages.

    When a compatibility rule fails, the error is keyed under the trigger variable
    (IF clause), but the actual failing variable is in the THEN/ELSE clause.

    Example:
        field_name = 'othersign' (trigger)
        error_msg  = "('apraxsp', [...]) for if {'othersign': ...} ..."
        returns    = 'apraxsp'
    """
    if "compatibility rule no:" in error_msg:
        match = _COMPATIBILITY_ERROR_PATTERN.match(error_msg)
        if match:
            return match.group(1)
    return field_name


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
        instrument_name: Name of the instrument being validated.
        primary_key_field: Name of the primary key field.
        datastore: Optional datastore for temporal rule validation.

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
            if validation_rules:
                resolved_rules = {k: v for k, v in resolved_rules.items() if k in validation_rules}
            if not resolved_rules:
                logger.warning("No rules for %s, skipping %s", instrument_name, pk_value)
                continue

            schema = _build_schema_from_raw(
                resolved_rules,
                include_temporal_rules=False,
                include_compatibility_rules=True,
            )
            qc = QualityCheck(
                pk_field=primary_key_field,
                schema=schema,
                strict=False,
                datastore=datastore,
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
                        actual_variable = _extract_failing_variable(field_name, msg)
                        errors.append(
                            {
                                primary_key_field: pk_value,
                                "instrument_name": instrument_name,
                                "variable": actual_variable,
                                "field_label": _get_field_label(actual_variable),
                                "error_message": msg,
                                "current_value": record_dict.get(actual_variable, ""),
                                "packet": packet_value,
                                "json_rule_path": rules_path,
                                "redcap_event_name": record_dict.get("redcap_event_name", ""),
                                "redcap_repeat_instance": record_dict.get(
                                    "redcap_repeat_instance", ""
                                ),
                                "visitdate": record_dict.get("visitdate", ""),
                                "qc_date": datetime.now().strftime("%Y-%m-%d"),
                                "discriminant": discriminant_info,
                                "variable_context": _build_variable_context(actual_variable, msg),
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
                    "qc_date": datetime.now().strftime("%Y-%m-%d"),
                    "discriminant": "",
                }
            )

    return errors, logs, passed_records
