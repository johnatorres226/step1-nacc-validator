"""Tests for the simplified REDCap data fetcher."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.pipeline.config.config_manager import QCConfig
from src.pipeline.core.fetcher import (
    REQUIRED_FIELDS,
    _apply_ptid_filter,
    _build_api_payload,
    _validate_and_map,
    fetch_redcap_data,
)


class TestRequiredFields:
    """Verify required field constants."""

    def test_required_fields_defined(self):
        assert "ptid" in REQUIRED_FIELDS
        assert "redcap_event_name" in REQUIRED_FIELDS


class TestBuildApiPayload:
    """Test API payload construction."""

    def test_builds_payload_with_instruments_and_filter(self):
        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(api_token="tok123")
        payload = _build_api_payload(config, ["a1_demographics"], "some_filter")
        assert payload["token"] == "tok123"
        assert payload["forms"] == "a1_demographics"
        assert payload["filterLogic"] == "some_filter"

    def test_builds_payload_without_filter(self):
        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(api_token="tok")
        payload = _build_api_payload(config, ["inst"], filter_logic=None)
        assert "filterLogic" not in payload

    def test_builds_payload_with_events(self):
        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(api_token="tok", events=["ev1", "ev2"])
        payload = _build_api_payload(config, [], None)
        assert payload["events"] == "ev1,ev2"


class TestValidateAndMap:
    """Test raw data validation and column mapping."""

    def test_maps_record_id_to_ptid(self):
        raw = [{"record_id": "P1", "redcap_event_name": "ev"}]
        df = _validate_and_map(raw)
        assert "ptid" in df.columns
        assert df["ptid"].iloc[0] == "P1"

    def test_keeps_existing_ptid(self):
        raw = [{"ptid": "P1", "redcap_event_name": "ev"}]
        df = _validate_and_map(raw)
        assert df["ptid"].iloc[0] == "P1"

    def test_raises_on_missing_required(self):
        raw = [{"some_col": "val"}]
        with pytest.raises(ValueError, match="Missing required"):
            _validate_and_map(raw)


class TestPtidFilter:
    """Test PTID filtering."""

    def test_filter_returns_matching_rows(self):
        df = pd.DataFrame({"ptid": ["A", "B", "C"], "val": [1, 2, 3]})
        config = QCConfig(ptid_list=["A", "C"])
        out = _apply_ptid_filter(df, config)
        assert list(out["ptid"]) == ["A", "C"]

    def test_no_filter_when_empty_list(self):
        df = pd.DataFrame({"ptid": ["A", "B"]})
        config = QCConfig(ptid_list=[])
        out = _apply_ptid_filter(df, config)
        assert len(out) == 2


class TestFetchRedcapData:
    """Integration tests for the full fetch function."""

    def test_successful_fetch(self, requests_mock):
        mock_data = [
            {"ptid": "T1", "redcap_event_name": "ev1", "packet": "I"},
            {"ptid": "T2", "redcap_event_name": "ev1", "packet": "I4"},
        ]
        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(
                api_token="tok",
                api_url="https://test.redcap.url",
            )
        requests_mock.post("https://test.redcap.url", json=mock_data)

        df, n = fetch_redcap_data(config)
        assert n == 2
        assert list(df["ptid"]) == ["T1", "T2"]

    def test_empty_fetch(self, requests_mock):
        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(
                api_token="tok",
                api_url="https://test.redcap.url",
            )
        requests_mock.post("https://test.redcap.url", json=[])

        df, n = fetch_redcap_data(config)
        assert n == 0
        assert df.empty

    def test_api_error_handling(self, requests_mock):
        config = QCConfig(
            api_token="bad",
            api_url="https://test.redcap.url",
        )
        requests_mock.post("https://test.redcap.url", status_code=403, text="Forbidden")

        with pytest.raises(RuntimeError, match="Forbidden"):
            fetch_redcap_data(config)

    def test_saves_csv_when_output_path_given(self, requests_mock):
        mock_data = [{"ptid": "T1", "redcap_event_name": "ev1"}]
        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(
                api_token="tok",
                api_url="https://test.redcap.url",
            )
        requests_mock.post("https://test.redcap.url", json=mock_data)

        with tempfile.TemporaryDirectory() as tmp:
            df, _ = fetch_redcap_data(
                config,
                output_path=Path(tmp),
                date_tag="01JAN",
                time_tag="1200",
            )
            csv_files = list(Path(tmp).rglob("*.csv"))
            assert len(csv_files) == 1
            assert "ETL_ProcessedData" in csv_files[0].name
