"""
Validation utilities — validation logging and complete-visit detection.

Two public functions:
    build_validation_log  – per-record completeness log entries
    find_complete_visits  – filter to visits where all instruments are complete
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def build_validation_log(
    df: pd.DataFrame, instrument: str, primary_key_field: str
) -> list[dict[str, Any]]:
    """Build per-record validation log entries for *instrument*.

    For each row, checks ``{instrument}_complete == '2'`` and produces a dict
    with ptid, event, instrument, status, pass/fail, error message.
    """
    if df.empty:
        return []

    col = f"{instrument}_complete"
    logs: list[dict] = []

    for _, row in df.iterrows():
        pk = str(row.get(primary_key_field, "N/A"))
        event = str(row.get("redcap_event_name", "N/A"))

        if col in row.index:
            is_complete = str(row.get(col)) == "2"
            target = col
            status = "Complete" if is_complete else "Incomplete"
            pf = "Pass" if is_complete else "Fail"
            err: Any = (
                np.nan
                if is_complete
                else (f"Instrument not marked as complete. Value is '{row.get(col)}'.")
            )
        else:
            target = "N/A"
            status = "No completeness field"
            pf = "Fail"
            err = "Instrument completeness variable not found in data."

        logs.append(
            {
                primary_key_field: pk,
                "redcap_event_name": event,
                "instrument_name": instrument,
                "target_variable": target,
                "completeness_status": status,
                "processing_status": "Processed",
                "pass_fail": pf,
                "error": err,
            }
        )

    return logs


def find_complete_visits(
    df: pd.DataFrame,
    instrument_list: list[str],
    primary_key_field: str = "ptid",
) -> tuple[pd.DataFrame, list[tuple[str, str]]]:
    """Identify visits where every instrument is marked complete (``== '2'``).

    Returns ``(summary_df, [(ptid, event), …])`` for downstream filtering.
    """
    if df.empty:
        return pd.DataFrame(), []

    comp_cols = [f"{i}_complete" for i in instrument_list if i.lower() != "form_header"]

    work = df.copy()
    if "packet" not in work.columns:
        work["packet"] = "unknown"
    for c in comp_cols:
        if c not in work.columns:
            work[c] = "0"
    for c in comp_cols:
        work[c] = work[c].astype(str)

    # Boolean mask: every completion col == '2'
    all_ok = (work[comp_cols] == "2").all(axis=1)
    # Per-visit: all rows in the visit must satisfy the mask
    visit_all = all_ok.groupby([work[primary_key_field], work["redcap_event_name"]]).all()
    complete = visit_all[visit_all]

    if complete.empty:
        return pd.DataFrame(), []

    packets = work.groupby([primary_key_field, "redcap_event_name"])["packet"].first()

    rows = []
    for pk, ev in complete.index:
        rows.append((pk, ev, packets.get((pk, ev), "unknown")))

    summary = pd.DataFrame(rows, columns=[primary_key_field, "redcap_event_name", "packet"])
    summary["complete_instruments_count"] = len(comp_cols)
    summary["completion_status"] = "All Complete"

    tuples = list(
        summary[[primary_key_field, "redcap_event_name"]].itertuples(index=False, name=None)
    )
    return summary, tuples
