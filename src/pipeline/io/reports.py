"""
Report generation for the QC pipeline.

Provides 4 core export functions:
1. Error report (CSV) — validation errors
2. Validation logs (CSV) — per-record completeness logs
3. Data fetched (CSV) — raw data audit trail
4. JSON tracking — structured JSON of the run
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def export_error_report(
    df_errors: pd.DataFrame, output_dir: Path, date_tag: str, time_tag: str
) -> Path | None:
    """Write errors CSV. Returns path or None if empty."""
    if df_errors is None or df_errors.empty:
        logger.info("No validation errors — skipping error report")
        return None

    path = output_dir / "Errors" / f"Final_Error_Dataset_{date_tag}_{time_tag}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    df_errors.to_csv(path, index=False)
    logger.info("Exported %d errors to %s", len(df_errors), path.name)
    return path


def export_validation_logs(
    df_logs: pd.DataFrame, output_dir: Path, date_tag: str, time_tag: str
) -> Path | None:
    """Write validation logs CSV."""
    if df_logs is None or df_logs.empty:
        logger.info("No validation logs — skipping logs report")
        return None

    filename = f"Log_EventCompletenessScreening_{date_tag}_{time_tag}.csv"
    path = output_dir / "Validation_Logs" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    df_logs.to_csv(path, index=False)
    logger.info("Exported %d log entries to %s", len(df_logs), path.name)
    return path


def export_data_fetched(
    df_all: pd.DataFrame, output_dir: Path, date_tag: str, time_tag: str
) -> Path | None:
    """Write the fetched data CSV (audit trail)."""
    if df_all is None or df_all.empty:
        logger.info("No fetched data — skipping Data_Fetched report")
        return None

    path = output_dir / "Data_Fetched" / f"Data_Fetched_{date_tag}_{time_tag}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    df_all.to_csv(path, index=False)
    logger.info("Exported %d records to %s", len(df_all), path.name)
    return path


def export_json_tracking(
    df_all: pd.DataFrame,
    df_errors: pd.DataFrame,
    output_dir: Path,
    date_tag: str,
    time_tag: str,
    user_initials: str = "N/A",
    upload_ready_path: str | None = None,
) -> Path:
    """Write JSON tracking payload with run metadata and per-participant QC status."""
    records: list[dict] = []

    if df_all is not None and not df_all.empty:
        # Include redcap_repeat_instance if available
        cols = ["ptid", "redcap_event_name"]
        if "redcap_repeat_instance" in df_all.columns:
            cols.append("redcap_repeat_instance")
        unique = df_all[cols].drop_duplicates()

        for _, row in unique.iterrows():
            ptid, event = row["ptid"], row["redcap_event_name"]
            event_instance = (
                row.get("redcap_repeat_instance", "")
                if "redcap_repeat_instance" in row
                else ""
            )

            # Determine failed instruments
            failed: list[str] = []
            if df_errors is not None and not df_errors.empty:
                mask = (df_errors["ptid"] == ptid) & (df_errors["redcap_event_name"] == event)
                failed = df_errors.loc[mask, "instrument_name"].unique().tolist()

            if failed:
                qc_status = "Failed in instruments: %s" % ", ".join(failed)
                qc_complete, qcc_complete = "0", "0"
            else:
                qc_status = "PASSED"
                qc_complete, qcc_complete = "1", "2"

            record_data = {
                "ptid": ptid,
                "redcap_event_name": event,
                "redcap_repeat_instance": event_instance,
                "qc_status_complete": qc_complete,
                "qc_run_by": user_initials,
                "qc_last_run": datetime.now().strftime("%Y-%m-%d"),
                "qc_status": qc_status,
                "quality_control_check_complete": qcc_complete,
            }
            records.append(record_data)

    filename = f"QC_Status_Report_{date_tag}_{time_tag}.json"

    if upload_ready_path:
        dest = Path(upload_ready_path)
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / filename
    else:
        path = output_dir / filename

    with path.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    logger.info("Exported JSON tracking (%d participants) to %s", len(records), path.name)
    return path
