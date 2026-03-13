"""Tests for src.pipeline.io.reports — the 4 core export functions."""

import json

import pandas as pd

from src.pipeline.io.reports import (
    export_data_fetched,
    export_error_report,
    export_json_tracking,
    export_validation_logs,
)

DATE_TAG = "21FEB2026"
TIME_TAG = "143000"


def _errors_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ptid": ["P001", "P001", "P002"],
            "redcap_event_name": ["visit_1", "visit_1", "visit_1"],
            "instrument_name": ["a1", "b4", "a1"],
            "error": ["missing", "range", "missing"],
        }
    )


def _records_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ptid": ["P001", "P002"],
            "redcap_event_name": ["visit_1", "visit_1"],
            "redcap_repeat_instance": ["1", "2"],
            "value": [10, 20],
        }
    )


# ── Error report ────────────────────────────────────────────────────────────


class TestExportErrorReport:
    def test_valid_data_writes_csv(self, tmp_path):
        path = export_error_report(_errors_df(), tmp_path, DATE_TAG, TIME_TAG)
        assert path is not None
        assert path.exists()
        assert path.parent.name == "Errors"
        round_trip = pd.read_csv(path)
        assert len(round_trip) == 3

    def test_filename_format(self, tmp_path):
        path = export_error_report(_errors_df(), tmp_path, DATE_TAG, TIME_TAG)
        assert path.name == f"Final_Error_Dataset_{DATE_TAG}_{TIME_TAG}.csv"

    def test_empty_df_returns_none(self, tmp_path):
        assert export_error_report(pd.DataFrame(), tmp_path, DATE_TAG, TIME_TAG) is None

    def test_none_returns_none(self, tmp_path):
        assert export_error_report(None, tmp_path, DATE_TAG, TIME_TAG) is None


# ── Validation logs ─────────────────────────────────────────────────────────


class TestExportValidationLogs:
    def test_valid_data_writes_csv(self, tmp_path):
        df = pd.DataFrame({"record": [1, 2], "status": ["ok", "ok"]})
        path = export_validation_logs(df, tmp_path, DATE_TAG, TIME_TAG)
        assert path is not None and path.exists()
        assert path.parent.name == "Validation_Logs"
        assert len(pd.read_csv(path)) == 2

    def test_filename_format(self, tmp_path):
        df = pd.DataFrame({"x": [1]})
        path = export_validation_logs(df, tmp_path, DATE_TAG, TIME_TAG)
        assert path.name == f"Log_EventCompletenessScreening_{DATE_TAG}_{TIME_TAG}.csv"

    def test_empty_df_returns_none(self, tmp_path):
        assert export_validation_logs(pd.DataFrame(), tmp_path, DATE_TAG, TIME_TAG) is None

    def test_none_returns_none(self, tmp_path):
        assert export_validation_logs(None, tmp_path, DATE_TAG, TIME_TAG) is None


# ── Data fetched ─────────────────────────────────────────────────────────────


class TestExportDataFetched:
    def test_valid_data_writes_csv(self, tmp_path):
        path = export_data_fetched(_records_df(), tmp_path, DATE_TAG, TIME_TAG)
        assert path is not None and path.exists()
        assert path.parent.name == "Data_Fetched"
        assert len(pd.read_csv(path)) == 2

    def test_filename_format(self, tmp_path):
        path = export_data_fetched(_records_df(), tmp_path, DATE_TAG, TIME_TAG)
        assert path.name == f"Data_Fetched_{DATE_TAG}_{TIME_TAG}.csv"

    def test_empty_df_returns_none(self, tmp_path):
        assert export_data_fetched(pd.DataFrame(), tmp_path, DATE_TAG, TIME_TAG) is None

    def test_none_returns_none(self, tmp_path):
        assert export_data_fetched(None, tmp_path, DATE_TAG, TIME_TAG) is None


# ── JSON tracking ────────────────────────────────────────────────────────────


class TestExportJsonTracking:
    def test_passed_status(self, tmp_path):
        """All participants pass when no errors exist."""
        path = export_json_tracking(_records_df(), pd.DataFrame(), tmp_path, DATE_TAG, TIME_TAG)
        data = json.loads(path.read_text())
        assert len(data) == 2
        assert all(r["qc_status"] == "PASSED" for r in data)
        assert all(r["qc_status_complete"] == "1" for r in data)
        assert all(r["quality_control_check_complete"] == "2" for r in data)

    def test_failed_status(self, tmp_path):
        """Participants with errors get Failed status listing instruments."""
        path = export_json_tracking(_records_df(), _errors_df(), tmp_path, DATE_TAG, TIME_TAG)
        data = json.loads(path.read_text())
        p001 = next(r for r in data if r["ptid"] == "P001")
        assert "Failed in instruments:" in p001["qc_status"]
        assert "a1" in p001["qc_status"] and "b4" in p001["qc_status"]
        assert p001["qc_status_complete"] == "0"
        assert p001["quality_control_check_complete"] == "0"

    def test_user_initials(self, tmp_path):
        path = export_json_tracking(
            _records_df(), None, tmp_path, DATE_TAG, TIME_TAG, user_initials="AB"
        )
        data = json.loads(path.read_text())
        assert all(r["qc_run_by"] == "AB" for r in data)

    def test_upload_ready_path(self, tmp_path):
        alt = tmp_path / "upload_ready"
        path = export_json_tracking(
            _records_df(),
            None,
            tmp_path,
            DATE_TAG,
            TIME_TAG,
            upload_ready_path=str(alt),
        )
        assert path.parent == alt
        assert alt.exists()

    def test_filename_format(self, tmp_path):
        path = export_json_tracking(_records_df(), None, tmp_path, DATE_TAG, TIME_TAG)
        assert path.name == f"QC_Status_Report_{DATE_TAG}_{TIME_TAG}.json"

    def test_empty_all_produces_empty_json(self, tmp_path):
        path = export_json_tracking(pd.DataFrame(), pd.DataFrame(), tmp_path, DATE_TAG, TIME_TAG)
        assert json.loads(path.read_text()) == []

    def test_none_all_produces_empty_json(self, tmp_path):
        path = export_json_tracking(None, None, tmp_path, DATE_TAG, TIME_TAG)
        assert json.loads(path.read_text()) == []

    def test_includes_redcap_repeat_instance(self, tmp_path):
        """Verify that redcap_repeat_instance is included in JSON output."""
        path = export_json_tracking(_records_df(), pd.DataFrame(), tmp_path, DATE_TAG, TIME_TAG)
        data = json.loads(path.read_text())
        assert len(data) == 2
        assert all("redcap_repeat_instance" in r for r in data)
        p001 = next(r for r in data if r["ptid"] == "P001")
        p002 = next(r for r in data if r["ptid"] == "P002")
        assert p001["redcap_repeat_instance"] == "1"
        assert p002["redcap_repeat_instance"] == "2"
