"""
REDCap report-based data fetching.

Provides ``fetch_report_data(config, output_path)`` which fetches pre-filtered
data from a configured REDCap report and returns ``(dataframe, records_processed)``.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from ..config.config_manager import QCConfig

logger = logging.getLogger(__name__)

# Fields that must be present after fetch
# Note: 'packet' field is optional and will be auto-populated with default value 'I' if missing
REQUIRED_FIELDS = ["ptid", "redcap_event_name"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_report_data(
    config: QCConfig,
    output_path: Path | None = None,
    date_tag: str | None = None,
    time_tag: str | None = None,
) -> tuple[pd.DataFrame, int]:
    """Fetch data from a pre-configured REDCap report.

    Uses the REDCap API 'report' content type with the report_id from config.
    The report is assumed to contain pre-filtered data ready for QC validation,
    eliminating the need for ETL filtering logic.

    Returns ``(dataframe, records_processed)``.
    """
    t0 = time.time()

    if not config.report_id:
        raise ValueError("REDCAP_REPORT_ID is not configured")

    payload = _build_report_payload(config)
    raw = _post_api(config, payload)

    if not raw:
        logger.warning("No data returned from REDCap report %s", config.report_id)
        return pd.DataFrame(), 0

    df = _validate_and_map(raw)
    df = _apply_ptid_filter(df, config)

    # Optional save (audit trail)
    if output_path and not df.empty:
        dt = date_tag or ""
        tt = time_tag or ""
        out_dir = Path(output_path) / "Data_Fetched"
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = out_dir / f"Report_Data_{config.report_id}_{dt}_{tt}.csv"
        df.to_csv(csv_path, index=False)
        logger.debug("Saved report data: %s (%d records)", csv_path, len(df))

    logger.info(
        "Fetched %d records from report %s in %.1fs",
        len(df),
        config.report_id,
        time.time() - t0,
    )
    return df, len(df)


def _build_report_payload(config: QCConfig) -> dict[str, Any]:
    """Build the REDCap API POST payload for report export."""
    return {
        "token": config.api_token,
        "content": "report",
        "report_id": config.report_id,
        "format": "json",
        "rawOrLabel": "raw",
        "rawOrLabelHeaders": "raw",
        "exportCheckboxLabel": "false",
        "returnFormat": "json",
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _post_api(config: QCConfig, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """POST to REDCap and return parsed JSON list."""
    if not config.api_url:
        raise ValueError("REDCap API URL is not configured")
    try:
        resp = requests.post(config.api_url, data=payload, timeout=config.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data if data else []
    except requests.exceptions.Timeout:
        raise RuntimeError(f"API request timed out after {config.timeout}s")
    except requests.exceptions.RequestException as exc:
        text = getattr(getattr(exc, "response", None), "text", None)
        raise RuntimeError(f"REDCap API request failed: {text or exc!s}")
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to parse JSON response: {exc!s}")


def _validate_and_map(raw: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert raw records to DataFrame, rename record_id → ptid, validate."""
    df = pd.DataFrame(raw)
    if "record_id" in df.columns and "ptid" not in df.columns:
        df = df.rename(columns={"record_id": "ptid"})
    missing = [f for f in REQUIRED_FIELDS if f not in df.columns]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    # Add packet field with default value if missing from REDCap export
    if "packet" not in df.columns:
        logger.warning(
            "packet field missing from REDCap report. Adding default value 'I'. "
            "To fix this: add the 'packet' field to your REDCap report configuration."
        )
        df["packet"] = "I"  # Default to Initial Visit

    return df


def _apply_ptid_filter(df: pd.DataFrame, config: QCConfig) -> pd.DataFrame:
    """Filter to specific PTIDs if ``config.ptid_list`` is set."""
    if not config.ptid_list or "ptid" not in df.columns:
        return df
    before = len(df)
    targets = [str(p) for p in config.ptid_list]
    df = df[df["ptid"].isin(targets)].reset_index(drop=True)
    logger.info("PTID filter: %d → %d records", before, len(df))
    return df
