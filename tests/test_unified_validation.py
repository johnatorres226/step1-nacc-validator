"""
Tests for cross-instrument bleed prevention in validate_data().

Root cause: get_rules_for_record() returns the full rule pool (all instruments),
not just the current instrument's rules. The fix in validate_data() filters
resolved_rules to only variables present in validation_rules (instrument-scoped),
eliminating false validation errors from foreign-instrument variables.
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.pipeline.config.config_manager import QCConfig
from src.pipeline.reports.report_pipeline import validate_data


@pytest.fixture
def mock_config():
    """Minimal QCConfig that satisfies validate_data() internals."""
    config = MagicMock(spec=QCConfig)
    config.get_rules_path_for_packet.return_value = "unknown"
    return config


def _make_record(**kwargs) -> dict:
    """Build a minimal record dict with required pipeline fields."""
    base = {"ptid": "TEST001", "packet": "I", "redcap_event_name": "udsv4_ivp_1_arm_1"}
    base.update(kwargs)
    return base


# ─── Cross-Instrument Bleed ──────────────────────────────────────────────────


class TestCrossInstrumentBleedPrevention:
    """Verify that rules from other instruments do not pollute a scoped validation."""

    # Pool returns vars from both instrument_a and instrument_b
    FULL_POOL = {
        # instrument_a variables
        "age": {"type": "integer", "min": 0, "max": 120},
        "sex": {"type": "integer", "allowed": [1, 2]},
        # instrument_b variables — absent from the record being validated
        "b_score": {"type": "integer", "min": 0, "max": 30},
        "b_result": {"type": "integer", "allowed": [0, 1]},
    }

    # validation_rules is scoped to instrument_a only
    INSTRUMENT_A_RULES = {
        "age": {"type": "integer", "min": 0, "max": 120},
        "sex": {"type": "integer", "allowed": [1, 2]},
    }

    def _run(self, mock_config, record_overrides: dict, rules=None):
        rules = rules if rules is not None else self.INSTRUMENT_A_RULES
        data = pd.DataFrame([_make_record(**record_overrides)])
        with patch("src.pipeline.reports.report_pipeline.get_config", return_value=mock_config):
            with patch(
                "src.pipeline.reports.report_pipeline.get_rules_for_record",
                return_value=self.FULL_POOL,
            ):
                return validate_data(
                    data=data,
                    validation_rules=rules,
                    instrument_name="instrument_a",
                    primary_key_field="ptid",
                )

    def test_valid_record_passes_despite_missing_foreign_vars(self, mock_config):
        """A valid instrument_a record must not fail because b_score/b_result are absent."""
        errors, logs, passed = self._run(mock_config, {"age": 65, "sex": 1})

        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(passed) == 1
        assert passed[0]["ptid"] == "TEST001"

    def test_foreign_variable_errors_not_reported(self, mock_config):
        """No error entry should reference instrument_b variables."""
        errors, _, _ = self._run(mock_config, {"age": 65, "sex": 1})

        foreign_vars = {"b_score", "b_result"}
        reported_vars = {e["variable"] for e in errors}
        assert reported_vars.isdisjoint(foreign_vars), (
            f"Foreign variables leaked into errors: {reported_vars & foreign_vars}"
        )

    def test_multiple_records_all_pass_without_bleed(self, mock_config):
        """All valid instrument_a records pass when pool contains foreign rules."""
        data = pd.DataFrame([
            _make_record(ptid="P001", age=45, sex=1),
            _make_record(ptid="P002", age=72, sex=2),
            _make_record(ptid="P003", age=30, sex=1),
        ])
        with patch("src.pipeline.reports.report_pipeline.get_config", return_value=mock_config):
            with patch(
                "src.pipeline.reports.report_pipeline.get_rules_for_record",
                return_value=self.FULL_POOL,
            ):
                errors, logs, passed = validate_data(
                    data=data,
                    validation_rules=self.INSTRUMENT_A_RULES,
                    instrument_name="instrument_a",
                    primary_key_field="ptid",
                )

        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(passed) == 3


# ─── In-Scope Errors Still Caught ───────────────────────────────────────────


class TestInScopeValidationIntact:
    """The bleed fix must not suppress real errors for in-scope variables."""

    FULL_POOL = {
        "age": {"type": "integer", "min": 0, "max": 120},
        "sex": {"type": "integer", "allowed": [1, 2]},
        "b_score": {"type": "integer", "min": 0, "max": 30},
    }

    INSTRUMENT_A_RULES = {
        "age": {"type": "integer", "min": 0, "max": 120},
        "sex": {"type": "integer", "allowed": [1, 2]},
    }

    def _run(self, mock_config, record_overrides: dict):
        data = pd.DataFrame([_make_record(**record_overrides)])
        with patch("src.pipeline.reports.report_pipeline.get_config", return_value=mock_config):
            with patch(
                "src.pipeline.reports.report_pipeline.get_rules_for_record",
                return_value=self.FULL_POOL,
            ):
                return validate_data(
                    data=data,
                    validation_rules=self.INSTRUMENT_A_RULES,
                    instrument_name="instrument_a",
                    primary_key_field="ptid",
                )

    def test_out_of_range_age_is_flagged(self, mock_config):
        """age=999 violates max=120 and must be reported as an error."""
        errors, _, passed = self._run(mock_config, {"age": 999, "sex": 1})

        assert len(errors) > 0
        assert any(e["variable"] == "age" for e in errors)
        assert len(passed) == 0

    def test_invalid_sex_value_is_flagged(self, mock_config):
        """sex=9 is not in allowed=[1,2] and must be reported as an error."""
        errors, _, passed = self._run(mock_config, {"age": 65, "sex": 9})

        assert len(errors) > 0
        assert any(e["variable"] == "sex" for e in errors)
        assert len(passed) == 0

    def test_multiple_in_scope_errors_all_reported(self, mock_config):
        """Both age and sex errors are reported when both are invalid."""
        errors, _, passed = self._run(mock_config, {"age": 999, "sex": 9})

        reported_vars = {e["variable"] for e in errors}
        assert "age" in reported_vars
        assert "sex" in reported_vars
        assert len(passed) == 0


# ─── Edge Cases ──────────────────────────────────────────────────────────────


class TestValidateDataEdgeCases:
    """Boundary behavior of the filtering logic."""

    def test_empty_validation_rules_falls_through_to_full_pool(self, mock_config):
        """When validation_rules is {}, the filter guard (if validation_rules:) is falsy —
        the full pool is used unfiltered, so a valid record still passes."""
        full_pool = {"age": {"type": "integer", "min": 0, "max": 120}}
        data = pd.DataFrame([_make_record(age=65)])

        with patch("src.pipeline.reports.report_pipeline.get_config", return_value=mock_config):
            with patch(
                "src.pipeline.reports.report_pipeline.get_rules_for_record",
                return_value=full_pool,
            ):
                errors, logs, passed = validate_data(
                    data=data,
                    validation_rules={},
                    instrument_name="instrument_a",
                    primary_key_field="ptid",
                )

        # Empty dict is falsy — filter is skipped, full pool applied, valid record passes
        assert len(errors) == 0
        assert len(passed) == 1

    def test_empty_dataframe_returns_empty_results(self, mock_config):
        """Empty input produces empty outputs without error."""
        data = pd.DataFrame(columns=["ptid", "age", "packet", "redcap_event_name"])
        rules = {"age": {"type": "integer", "min": 0, "max": 120}}

        with patch("src.pipeline.reports.report_pipeline.get_config", return_value=mock_config):
            with patch(
                "src.pipeline.reports.report_pipeline.get_rules_for_record",
                return_value=rules,
            ):
                errors, logs, passed = validate_data(
                    data=data,
                    validation_rules=rules,
                    instrument_name="instrument_a",
                    primary_key_field="ptid",
                )

        assert errors == []
        assert logs == []
        assert passed == []

    def test_error_record_metadata_is_complete(self, mock_config):
        """Error entries include all expected metadata fields."""
        full_pool = {
            "age": {"type": "integer", "min": 0, "max": 120},
            "b_score": {"type": "integer", "min": 0, "max": 30},
        }
        rules = {"age": {"type": "integer", "min": 0, "max": 120}}
        data = pd.DataFrame([_make_record(age=999)])

        with patch("src.pipeline.reports.report_pipeline.get_config", return_value=mock_config):
            with patch(
                "src.pipeline.reports.report_pipeline.get_rules_for_record",
                return_value=full_pool,
            ):
                errors, _, _ = validate_data(
                    data=data,
                    validation_rules=rules,
                    instrument_name="instrument_a",
                    primary_key_field="ptid",
                )

        assert len(errors) > 0
        err = errors[0]
        expected_keys = {
            "ptid", "instrument_name", "variable", "error_message",
            "current_value", "packet", "json_rule_path", "redcap_event_name", "discriminant",
        }
        assert expected_keys.issubset(err.keys())
        assert err["instrument_name"] == "instrument_a"
