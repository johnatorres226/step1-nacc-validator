"""
Smoke tests for our QualityCheck integration boundary.

Verifies that the nacc_form_validator QualityCheck behaves as our pipeline
expects at the specific contract points we depend on: valid records pass,
invalid records fail with the correct field names in errors.
"""

import pytest

from nacc_form_validator.quality_check import QualityCheck, QualityCheckException

_SCHEMA = {
    "ptid": {"type": "string", "required": True},
    "age": {"type": "integer", "min": 0, "max": 120},
}


def test_valid_record_passes():
    qc = QualityCheck(schema=_SCHEMA, pk_field="ptid")
    passed, sys_failure, errors, _ = qc.validate_record({"ptid": "P001", "age": 65})
    assert passed is True
    assert sys_failure is False
    assert len(errors) == 0


def test_out_of_range_value_fails_with_field_name():
    qc = QualityCheck(schema=_SCHEMA, pk_field="ptid")
    passed, _, errors, _ = qc.validate_record({"ptid": "P001", "age": 150})
    assert passed is False
    assert "age" in errors


def test_invalid_schema_type_raises():
    with pytest.raises(QualityCheckException):
        QualityCheck(schema={"f": {"type": "not_a_real_type"}}, pk_field="ptid")
