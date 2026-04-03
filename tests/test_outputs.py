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
        }
    )


# ── Error report ─────────────────────────────────────────────────────────────


class TestExportErrorReport:
    def test_writes_flat_csv_with_correct_row_count(self, tmp_path):
        path = export_error_report(_errors_df(), tmp_path, DATE_TAG, TIME_TAG)
        assert path is not None and path.exists()
        assert path.parent == tmp_path  # flat — no Errors/ subdir
        assert len(pd.read_csv(path)) == 3

    def test_empty_returns_none(self, tmp_path):
        assert export_error_report(pd.DataFrame(), tmp_path, DATE_TAG, TIME_TAG) is None


# ── Validation logs ──────────────────────────────────────────────────────────


class TestExportValidationLogs:
    def test_writes_csv_under_validation_logs_subdir(self, tmp_path):
        df = pd.DataFrame({"record": [1, 2], "status": ["ok", "ok"]})
        path = export_validation_logs(df, tmp_path, DATE_TAG, TIME_TAG)
        assert path is not None and path.exists()
        assert path.parent.name == "Validation_Logs"
        assert len(pd.read_csv(path)) == 2

    def test_empty_returns_none(self, tmp_path):
        assert export_validation_logs(pd.DataFrame(), tmp_path, DATE_TAG, TIME_TAG) is None


# ── Data fetched ──────────────────────────────────────────────────────────────


class TestExportDataFetched:
    def test_writes_csv_under_data_fetched_subdir(self, tmp_path):
        path = export_data_fetched(_records_df(), tmp_path, DATE_TAG, TIME_TAG)
        assert path is not None and path.exists()
        assert path.parent.name == "Data_Fetched"
        assert len(pd.read_csv(path)) == 2

    def test_empty_returns_none(self, tmp_path):
        assert export_data_fetched(pd.DataFrame(), tmp_path, DATE_TAG, TIME_TAG) is None


# ── JSON tracking ─────────────────────────────────────────────────────────────


class TestExportJsonTracking:
    def test_passed_status(self, tmp_path):
        path = export_json_tracking(_records_df(), pd.DataFrame(), tmp_path, DATE_TAG, TIME_TAG)
        data = json.loads(path.read_text())
        assert len(data) == 2
        assert all(r["qc_status"] == "PASSED" for r in data)
        assert all(r["qc_status_complete"] == "1" for r in data)
        assert all(r["quality_control_check_complete"] == "2" for r in data)

    def test_failed_status_lists_instruments(self, tmp_path):
        path = export_json_tracking(_records_df(), _errors_df(), tmp_path, DATE_TAG, TIME_TAG)
        data = json.loads(path.read_text())
        p001 = next(r for r in data if r["ptid"] == "P001")
        assert "Failed in instruments:" in p001["qc_status"]
        assert "a1" in p001["qc_status"] and "b4" in p001["qc_status"]
        assert p001["qc_status_complete"] == "0"

    def test_user_initials_recorded(self, tmp_path):
        path = export_json_tracking(
            _records_df(), None, tmp_path, DATE_TAG, TIME_TAG, user_initials="JT"
        )
        data = json.loads(path.read_text())
        assert all(r["qc_run_by"] == "JT" for r in data)

    def test_upload_ready_path_redirects_output(self, tmp_path):
        alt = tmp_path / "upload_ready"
        path = export_json_tracking(
            _records_df(), None, tmp_path, DATE_TAG, TIME_TAG, upload_ready_path=str(alt)
        )
        assert path.parent == alt

    def test_includes_redcap_repeat_instance(self, tmp_path):
        path = export_json_tracking(_records_df(), pd.DataFrame(), tmp_path, DATE_TAG, TIME_TAG)
        data = json.loads(path.read_text())
        p001 = next(r for r in data if r["ptid"] == "P001")
        assert p001["redcap_repeat_instance"] == "1"

    def test_empty_input_produces_empty_json(self, tmp_path):
        path = export_json_tracking(None, None, tmp_path, DATE_TAG, TIME_TAG)
        assert json.loads(path.read_text()) == []
