"""Tests for REDCap report-based data fetching.

This module tests the fetch_report_data() function which uses the REDCap API
'report' content type to fetch pre-filtered data, eliminating the need for
ETL filtering logic.
"""

import os
from unittest.mock import patch

import pandas as pd
import pytest

from src.pipeline.config.config_manager import QCConfig
from src.pipeline.core.fetcher import (
    _build_report_payload,
    fetch_report_data,
)


class TestBuildReportPayload:
    """Test report API payload construction."""

    def test_builds_payload_with_report_id(self):
        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(api_token="tok123", report_id="24287")
        payload = _build_report_payload(config)

        assert payload["token"] == "tok123"
        assert payload["content"] == "report"
        assert payload["report_id"] == "24287"
        assert payload["format"] == "json"
        assert payload["rawOrLabel"] == "raw"


class TestFetchReportData:
    """Tests for the fetch_report_data function."""

    def test_raises_when_report_id_missing(self):
        """Should raise ValueError when REDCAP_REPORT_ID is not configured."""
        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(api_token="tok", api_url="https://test.url")
            config.report_id = None  # Explicitly no report ID

        with pytest.raises(ValueError, match="REDCAP_REPORT_ID is not configured"):
            fetch_report_data(config)

    def test_successful_report_fetch(self, requests_mock):
        """Mock test: fetch_report_data returns expected DataFrame structure."""
        mock_data = [
            {"ptid": "T1", "redcap_event_name": "ev1", "packet": "I", "age": 65},
            {"ptid": "T2", "redcap_event_name": "ev1", "packet": "I4", "age": 72},
        ]
        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(
                api_token="tok",
                api_url="https://test.redcap.url",
                report_id="24287",
            )
        requests_mock.post("https://test.redcap.url", json=mock_data)

        df, count = fetch_report_data(config)

        assert len(df) == 2
        assert count == 2
        assert "ptid" in df.columns
        assert "packet" in df.columns
        print(f"DataFrame dimensions: {df.shape[0]} rows x {df.shape[1]} columns")

    def test_empty_report_returns_empty_dataframe(self, requests_mock):
        """Should handle empty report gracefully."""
        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(
                api_token="tok",
                api_url="https://test.redcap.url",
                report_id="24287",
            )
        requests_mock.post("https://test.redcap.url", json=[])

        df, count = fetch_report_data(config)

        assert df.empty
        assert count == 0


# =============================================================================
# INTEGRATION TEST - Run with: pytest -v -k test_live_report_fetch
# Requires valid .env with REDCAP_API_TOKEN, REDCAP_API_URL, REDCAP_REPORT_ID
# =============================================================================


@pytest.mark.integration
class TestLiveReportFetch:
    """Live API integration tests for report fetching.

    These tests require valid REDCap credentials in .env.
    Run with: pytest tests/test_report_fetching.py -v -k integration -s
    """

    def test_live_report_fetch(self):
        """Fetch report ID 24287 from live REDCap and validate response.

        Expected: ~70 records returned from pre-configured QC report.
        """
        # Load real config from .env
        config = QCConfig()

        # Skip if credentials not configured
        if not config.api_token or not config.api_url or not config.report_id:
            pytest.skip("REDCap credentials not configured in .env")

        df, count = fetch_report_data(config)

        # Output dimensions and basic stats
        print(f"\n{'='*60}")
        print(f"REPORT FETCH RESULTS (Report ID: {config.report_id})")
        print(f"{'='*60}")
        print(f"DataFrame dimensions: {df.shape[0]} rows x {df.shape[1]} columns")
        print(f"Records fetched: {count}")

        if not df.empty:
            print(f"\nColumns ({len(df.columns)}): {list(df.columns[:10])}...")
            if "packet" in df.columns:
                print(f"Packets: {df['packet'].value_counts().to_dict()}")
            if "ptid" in df.columns:
                print(f"Unique PTIDs: {df['ptid'].nunique()}")

        print(f"{'='*60}\n")

        # Assertions
        assert count > 0, "Expected at least some records from report"
        assert "ptid" in df.columns, "Expected 'ptid' column in report data"
        assert "redcap_event_name" in df.columns, "Expected 'redcap_event_name' column"

        # Expected ~70 records based on requirements
        assert count >= 50, f"Expected ~70 records, got {count}"
        assert count <= 200, f"Expected ~70 records, got {count} (too many?)"
