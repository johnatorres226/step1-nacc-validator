"""Data processing functions for the QC pipeline."""

from typing import Any

import pandas as pd

from ..config.config_manager import (
    get_completion_columns,
    get_core_columns,
    get_discriminant_variable,
    is_dynamic_rule_instrument,
)
from ..io.rule_loader import load_rules_for_instrument
from ..logging.logging_config import get_logger

logger = get_logger(__name__)


class DataProcessingError(Exception):
    """Error during data processing."""


# ---------------------------------------------------------------------------
# Variable helpers
# ---------------------------------------------------------------------------


def _get_variables_for_instrument(instrument: str, rules_cache: dict[str, Any]) -> list[str]:
    """Return variable names for *instrument*."""
    if is_dynamic_rule_instrument(instrument):
        variant_rules = load_rules_for_instrument(instrument)
        return list({var for rules in variant_rules.values() for var in rules})
    return list(rules_cache.get(instrument, {}).keys())


# ---------------------------------------------------------------------------
# Type casting
# ---------------------------------------------------------------------------


def preprocess_cast_types(df: pd.DataFrame, rules: dict[str, dict[str, Any]]) -> pd.DataFrame:
    """Cast DataFrame columns according to rule-defined types."""
    out = df.copy()
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
    cols += [c for c in get_completion_columns() if c in data_df.columns]

    if is_dynamic_rule_instrument(instrument):
        d_var = get_discriminant_variable(instrument)
        if d_var in data_df.columns:
            cols.append(d_var)

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
