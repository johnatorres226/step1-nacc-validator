"""Tests for REDCap data fetcher internal utilities.

This module tests the internal utility functions used by the report-based
fetcher (validation, mapping, filtering).
"""

import pandas as pd
import pytest

from src.pipeline.config.config_manager import QCConfig
from src.pipeline.core.fetcher import (
    REQUIRED_FIELDS,
    _apply_ptid_filter,
    _validate_and_map,
)


class TestRequiredFields:
    """Verify required field constants."""

    def test_required_fields_defined(self):
        assert "ptid" in REQUIRED_FIELDS
        assert "redcap_event_name" in REQUIRED_FIELDS


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
