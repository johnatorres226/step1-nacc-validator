"""
Validation utilities — validation logging.

One public function:
    build_validation_log  – per-record completeness log entries
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
