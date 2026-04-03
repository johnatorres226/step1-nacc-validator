"""Data processing functions for the QC pipeline."""

from typing import Any

import pandas as pd

from ..config.config_manager import get_core_columns
from ..logging.logging_config import get_logger

logger = get_logger(__name__)


class DataProcessingError(Exception):
    """Error during data processing."""


# ---------------------------------------------------------------------------
# Variable helpers
# ---------------------------------------------------------------------------


def _extract_referenced_variables(rule_def: dict[str, Any]) -> set[str]:
    """Extract all variables referenced in a rule's compatibility and compare_age clauses.

    Compatibility rules can reference variables in:
    - `if` clause: the condition variables
    - `then` clause: variables to check when condition is true
    - `else` clause: variables to check when condition is false

    Compare_age rules can reference variables in:
    - `compare_to`: age fields to compare against (e.g., behage, cogage)

    These may be cross-form variables (e.g., A1's compare_age checking B9's `behage`).
    """
    referenced: set[str] = set()

    # Extract from compatibility rules
    compatibility_rules = rule_def.get("compatibility", [])
    if isinstance(compatibility_rules, list):
        for compat in compatibility_rules:
            if not isinstance(compat, dict):
                continue
            for clause_key in ("if", "then", "else"):
                clause = compat.get(clause_key, {})
                if isinstance(clause, dict):
                    referenced.update(clause.keys())

    # Extract from compare_age rules (H1/H4 fix: include cross-form age variables)
    compare_age = rule_def.get("compare_age", {})
    if isinstance(compare_age, dict):
        compare_to = compare_age.get("compare_to", [])
        if isinstance(compare_to, str):
            referenced.add(compare_to)
        elif isinstance(compare_to, list):
            referenced.update(f for f in compare_to if isinstance(f, str))

    return referenced


def _get_variables_for_instrument(instrument: str, rules_cache: dict[str, Any]) -> list[str]:
    """Return all variable names needed for *instrument* validation.

    This includes:
    1. Variables owned by the instrument (rule keys)
    2. Variables referenced in compatibility rules (cross-form variables)
    """
    rules = rules_cache.get(instrument, {})
    if not rules:
        return []

    # Start with owned variables (rule keys)
    variables: set[str] = set(rules.keys())

    # Add cross-form variables referenced in compatibility rules
    for rule_def in rules.values():
        if isinstance(rule_def, dict):
            variables.update(_extract_referenced_variables(rule_def))

    return list(variables)


# ---------------------------------------------------------------------------
# Type casting
# ---------------------------------------------------------------------------


def preprocess_cast_types(df: pd.DataFrame, rules: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Cast DataFrame columns according to rule-defined types.

    Also handles special cases:
    - compare_age rules: cast compare_to fields to numeric (prevents type errors)
    """
    out = df.copy()

    # Collect fields that need numeric casting from compare_age rules
    compare_age_fields: set[str] = set()
    for field, cfg in rules.items():
        if "compare_age" in cfg:
            compare_to = cfg["compare_age"].get("compare_to", [])
            if isinstance(compare_to, str):
                compare_age_fields.add(compare_to)
            elif isinstance(compare_to, list):
                compare_age_fields.update(f for f in compare_to if isinstance(f, str))

    # Cast compare_age referenced fields to numeric
    for field in compare_age_fields:
        if field in out.columns:
            try:
                out[field] = pd.to_numeric(out[field], errors="coerce")
            except Exception as e:
                logger.warning("Failed to cast compare_age field '%s' to numeric: %s", field, e)

    # Standard type casting based on rule definitions
    for field, cfg in rules.items():
        if field not in out.columns:
            continue
        dtype = cfg.get("type")
        try:
            if dtype == "integer":
                out[field] = pd.to_numeric(out[field], errors="coerce").astype("Int64")
            elif dtype == "float":
                out[field] = pd.to_numeric(out[field], errors="coerce")
            elif dtype in ("date", "datetime"):
                out[field] = pd.to_datetime(out[field], errors="coerce")
        except Exception as e:
            logger.warning("Failed to cast '%s' to %s: %s", field, dtype, e)
    return out


# ---------------------------------------------------------------------------
# Variable maps
# ---------------------------------------------------------------------------


def build_variable_maps(
    instrument_list: list[str], rules_cache: dict[str, Any]
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Build variable-to-instrument and instrument-to-variables mappings."""
    var_to_inst: dict[str, str] = {}
    inst_to_vars: dict[str, list[str]] = {}
    for instrument in instrument_list:
        variables = _get_variables_for_instrument(instrument, rules_cache)
        inst_to_vars[instrument] = variables
        for var in variables:
            var_to_inst[var] = instrument
    return var_to_inst, inst_to_vars


# ---------------------------------------------------------------------------
# Instrument data preparation
# ---------------------------------------------------------------------------


def _prepare_single_instrument(
    instrument: str,
    data_df: pd.DataFrame,
    rules_cache: dict[str, Any],
    primary_key_field: str,
) -> pd.DataFrame:
    """Filter *data_df* to columns relevant for *instrument* and rows with data."""
    variables = _get_variables_for_instrument(instrument, rules_cache)
    if not variables:
        return pd.DataFrame()

    core_cols = get_core_columns()
    cols: list[str] = [c for c in core_cols if c in data_df.columns]
    cols += [v for v in variables if v in data_df.columns]

    # Always include discriminant column for C2/C2T instrument
    if instrument == "c2c2t_neuropsychological_battery_scores":
        if "loc_c2_or_c2t" in data_df.columns:
            cols.append("loc_c2_or_c2t")

    cols = list(dict.fromkeys(cols))  # deduplicate preserving order
    if not cols:
        return pd.DataFrame()

    df = data_df[cols].copy()
    non_core = [c for c in cols if c not in core_cols and not c.endswith("_complete")]
    if non_core:
        df = df[df[non_core].notna().any(axis=1)].reset_index(drop=True)
    return df


def prepare_instrument_data_cache(
    data_df: pd.DataFrame,
    instrument_list: list[str],
    instrument_variable_map: dict[str, list[str]],
    rules_cache: dict[str, Any],
    primary_key_field: str,
) -> dict[str, pd.DataFrame]:
    """Prepare per-instrument DataFrames for all instruments."""
    cache: dict[str, pd.DataFrame] = {}
    for instrument in instrument_list:
        df = _prepare_single_instrument(instrument, data_df, rules_cache, primary_key_field)
        cache[instrument] = df
        logger.debug("Prepared %d rows for '%s'", len(df), instrument)
    return cache


# ---------------------------------------------------------------------------
# Packet grouping
# ---------------------------------------------------------------------------


def prepare_packet_grouped_data(
    data_df: pd.DataFrame,
    primary_key_field: str = "ptid",
) -> dict[str, pd.DataFrame]:
    """Group data by packet type for parallel packet-grouped validation.

    This is the key function for thread-safe parallel validation. By grouping
    data by packet BEFORE spawning workers, each worker batch operates on a
    single packet type, eliminating race conditions with rule pool switching.

    Args:
        data_df: Full data from REDCap
        primary_key_field: Record identifier field

    Returns:
        Dict mapping packet code to DataFrame: {'I': df_initial, 'I4': df_i4, 'F': df_fvp}
    """
    if data_df.empty:
        return {}

    if "packet" not in data_df.columns:
        logger.warning("No 'packet' column in data — defaulting all to 'I'")
        data_df = data_df.copy()
        data_df["packet"] = "I"

    packet_groups: dict[str, pd.DataFrame] = {}
    valid_packets = {"I", "I4", "F", "M"}  # H5 fix: Added M (Milestone) packet support

    for packet_value in data_df["packet"].dropna().unique():
        packet_upper = str(packet_value).upper()
        if packet_upper not in valid_packets:
            logger.warning("Unknown packet value '%s' — skipping", packet_value)
            continue

        packet_df = data_df[data_df["packet"].str.upper() == packet_upper].copy()
        if not packet_df.empty:
            packet_groups[packet_upper] = packet_df
            logger.debug("Packet %s: %d records", packet_upper, len(packet_df))

    logger.info(
        "Grouped data into %d packets: %s",
        len(packet_groups),
        ", ".join(f"{k}={len(v)}" for k, v in packet_groups.items()),
    )

    return packet_groups
