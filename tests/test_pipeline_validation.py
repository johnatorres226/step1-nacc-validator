"""
Essential tests for pipeline validation functionality.

Tests the core QualityCheck integration points our pipeline relies on:
initialization, record validation, boundary rules, and robustness.
"""

import pytest

from nacc_form_validator.nacc_validator import NACCValidator
from nacc_form_validator.quality_check import QualityCheck, QualityCheckException


class TestQualityCheckInitialization:
    """Test QualityCheck initialization and setup."""

    def test_quality_check_creation_with_valid_schema(self):
        """Test QualityCheck creation with valid schema."""
        schema = {"test_field": {"type": "string", "required": True}}
        pk_field = "ptid"

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        assert qc.pk_field == pk_field
        assert qc.schema == schema
        assert qc.validator.datastore is None
        assert isinstance(qc.validator, NACCValidator)

    def test_quality_check_creation_with_invalid_schema(self):
        """Test QualityCheck creation with invalid schema raises."""
        invalid_schema = {
            "test_field": {
                "type": "invalid_type",
                "required": True,
            }
        }
        pk_field = "ptid"

        with pytest.raises(QualityCheckException):
            QualityCheck(schema=invalid_schema, pk_field=pk_field)


class TestValidationExecution:
    """Test validation execution functionality."""

    def test_validate_record_success(self):
        """Test successful record validation."""
        schema = {
            "ptid": {"type": "string", "required": True},
            "age": {"type": "integer", "min": 0, "max": 120},
        }
        qc = QualityCheck(schema=schema, pk_field="ptid")

        passed, sys_failure, errors, error_tree = qc.validate_record({"ptid": "TEST001", "age": 65})

        assert passed is True
        assert sys_failure is False
        assert len(errors) == 0

    def test_validate_record_with_errors(self):
        """Test record validation with validation errors."""
        schema = {
            "ptid": {"type": "string", "required": True},
            "age": {"type": "integer", "min": 0, "max": 120},
        }
        qc = QualityCheck(schema=schema, pk_field="ptid")

        passed, sys_failure, errors, error_tree = qc.validate_record(
            {"ptid": "TEST001", "age": 150}
        )

        assert passed is False
        assert sys_failure is False
        assert "age" in errors


class TestValidationRules:
    """Test validation rules our pipeline relies on."""

    def test_integer_validation_rules(self):
        """Test integer min/max boundary validation."""
        schema = {
            "ptid": {"type": "string", "required": True},
            "age": {"type": "integer", "min": 0, "max": 120},
        }
        qc = QualityCheck(schema=schema, pk_field="ptid")

        # Valid value
        passed, _, _, _ = qc.validate_record({"ptid": "TEST001", "age": 65})
        assert passed is True

        # Below minimum
        passed, _, _, _ = qc.validate_record({"ptid": "TEST001", "age": -1})
        assert passed is False

        # Above maximum
        passed, _, _, _ = qc.validate_record({"ptid": "TEST001", "age": 150})
        assert passed is False


class TestValidationRobustness:
    """Test validation robustness and error handling."""

    def test_validation_with_empty_record(self):
        """Test validation with empty record flags missing required fields."""
        schema = {"ptid": {"type": "string", "required": True}}
        qc = QualityCheck(schema=schema, pk_field="ptid")

        passed, sys_failure, errors, error_tree = qc.validate_record({})

        assert passed is False
        assert "ptid" in errors

    def test_validation_with_malformed_data_types(self):
        """Test validation rejects type mismatches."""
        schema = {
            "ptid": {"type": "string", "required": True},
            "age": {"type": "integer"},
        }
        qc = QualityCheck(schema=schema, pk_field="ptid")

        passed, sys_failure, errors, error_tree = qc.validate_record(
            {"ptid": "TEST001", "age": "not_a_number"}
        )

        assert passed is False
        assert "age" in errors


if __name__ == "__main__":
    pytest.main([__file__])
