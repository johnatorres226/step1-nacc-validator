# tests/test_quality_check.py

import pytest
from unittest.mock import MagicMock, patch
from pipeline.quality_check import QualityCheck, QualityCheckException
from pipeline.datastore import Datastore
from pipeline.nacc_validator import ValidationException

# Mock data and schemas for testing
VALID_SCHEMA = {
    'field1': {'type': 'string'},
    'field2': {'type': 'integer'}
}
INVALID_SCHEMA = {
    'field1': {'type': 'invalid_type'}
}
PK_FIELD = 'field1'

@pytest.fixture
def mock_datastore():
    """Fixture for a mocked Datastore."""
    ds = MagicMock(spec=Datastore)
    ds.pk_field = PK_FIELD
    return ds

def test_initialization_success(mock_datastore):
    """Test successful initialization of QualityCheck."""
    qc = QualityCheck(pk_field=PK_FIELD, schema=VALID_SCHEMA, datastore=mock_datastore)
    assert qc.pk_field == PK_FIELD
    assert qc.schema == VALID_SCHEMA
    assert qc.validator is not None

def test_initialization_invalid_schema():
    """Test initialization with an invalid schema."""
    with pytest.raises(QualityCheckException, match="Schema Error"):
        QualityCheck(pk_field=PK_FIELD, schema=INVALID_SCHEMA)

def test_initialization_pk_mismatch(mock_datastore):
    """Test initialization with mismatched primary keys."""
    mock_datastore.pk_field = 'wrong_pk'
    with pytest.raises(QualityCheckException, match="Mismatched primary key fields"):
        QualityCheck(pk_field=PK_FIELD, schema=VALID_SCHEMA, datastore=mock_datastore)

def test_validate_record_success(mock_datastore):
    """Test a successful record validation."""
    qc = QualityCheck(pk_field=PK_FIELD, schema=VALID_SCHEMA, datastore=mock_datastore)
    record = {'field1': 'value1', 'field2': 123}
    result = qc.validate_record(record)
    assert result.passed is True
    assert result.sys_failure is False
    assert not result.errors

def test_validate_record_failure(mock_datastore):
    """Test a failed record validation."""
    qc = QualityCheck(pk_field=PK_FIELD, schema=VALID_SCHEMA, datastore=mock_datastore)
    record = {'field1': 'value1', 'field2': 'not-an-integer'}
    result = qc.validate_record(record)
    assert result.passed is False
    assert result.sys_failure is False
    assert 'field2' in result.errors

@patch('pipeline.nacc_validator.NACCValidator.validate')
def test_validate_record_system_failure(mock_validate, mock_datastore):
    """Test a validation that results in a system failure."""
    mock_validate.side_effect = ValidationException("Something broke")
    qc = QualityCheck(pk_field=PK_FIELD, schema=VALID_SCHEMA, datastore=mock_datastore)
    record = {'field1': 'value1', 'field2': 123}
    result = qc.validate_record(record)
    assert result.passed is False
    assert result.sys_failure is True
    assert result.errors is not None # Should contain sys_errors

def test_strict_mode_on(mock_datastore):
    """Test strict mode disallowing unknown fields."""
    qc = QualityCheck(pk_field=PK_FIELD, schema=VALID_SCHEMA, strict=True, datastore=mock_datastore)
    record = {'field1': 'value1', 'field2': 123, 'unknown_field': 'extra'}
    result = qc.validate_record(record)
    assert result.passed is False
    assert 'unknown_field' in result.errors

def test_strict_mode_off(mock_datastore):
    """Test non-strict mode allowing unknown fields."""
    qc = QualityCheck(pk_field=PK_FIELD, schema=VALID_SCHEMA, strict=False, datastore=mock_datastore)
    record = {'field1': 'value1', 'field2': 123, 'unknown_field': 'extra'}
    result = qc.validate_record(record)
    assert result.passed is True
    assert not result.errors

def test_validator_not_initialized():
    """Test calling validate_record without a validator."""
    qc = QualityCheck(pk_field=PK_FIELD, schema=VALID_SCHEMA)
    qc.validator = None  # type: ignore # Manually set validator to None
    with pytest.raises(QualityCheckException, match="Validator is not initialized."):
        qc.validate_record({'field1': 'a', 'field2': 1})

