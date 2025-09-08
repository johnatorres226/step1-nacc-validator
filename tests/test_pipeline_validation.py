"""
Essential tests for pipeline validation functionality.

This module tests the core validation logic, quality checks, and validation result 
handling components that are fundamental to the application's data validation process.
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path

# Import the modules we're testing
from nacc_form_validator.quality_check import QualityCheck, QualityCheckException
from nacc_form_validator.models import ValidationResult
from nacc_form_validator.nacc_validator import NACCValidator, ValidationException
from src.pipeline.config_manager import QCConfig


class TestQualityCheckInitialization:
    """Test QualityCheck initialization and setup."""

    def test_quality_check_creation_with_valid_schema(self):
        """Test QualityCheck creation with valid schema."""
        schema = {
            'test_field': {
                'type': 'string',
                'required': True
            }
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        assert qc.pk_field == pk_field
        assert qc.schema == schema
        assert qc.datastore is None
        assert isinstance(qc.validator, NACCValidator)

    def test_quality_check_creation_with_datastore(self):
        """Test QualityCheck creation with datastore."""
        schema = {
            'test_field': {
                'type': 'string',
                'required': True
            }
        }
        pk_field = 'ptid'

        # Mock datastore
        mock_datastore = Mock()
        mock_datastore.pk_field = pk_field

        qc = QualityCheck(schema=schema, pk_field=pk_field, datastore=mock_datastore)

        assert qc.datastore == mock_datastore

    def test_quality_check_creation_with_invalid_schema(self):
        """Test QualityCheck creation with invalid schema."""
        invalid_schema = {
            'test_field': {
                'type': 'invalid_type',  # Invalid type
                'required': True
            }
        }
        pk_field = 'ptid'

        # Should raise QualityCheckException during initialization
        with pytest.raises(QualityCheckException):
            QualityCheck(schema=invalid_schema, pk_field=pk_field)

    def test_quality_check_creation_with_mismatched_datastore_pk(self):
        """Test QualityCheck creation with mismatched datastore primary key."""
        schema = {
            'test_field': {
                'type': 'string',
                'required': True
            }
        }
        pk_field = 'ptid'

        # Mock datastore with different pk_field
        mock_datastore = Mock()
        mock_datastore.pk_field = 'different_pk'

        with pytest.raises(QualityCheckException) as excinfo:
            QualityCheck(schema=schema, pk_field=pk_field, datastore=mock_datastore)

        assert "mismatched primary key" in str(excinfo.value).lower()


class TestValidationExecution:
    """Test validation execution functionality."""

    def test_validate_record_success(self):
        """Test successful record validation."""
        schema = {
            'ptid': {
                'type': 'string',
                'required': True
            },
            'age': {
                'type': 'integer',
                'min': 0,
                'max': 120
            }
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        valid_record = {
            'ptid': 'TEST001',
            'age': 65
        }

        result = qc.validate_record(valid_record)

        assert isinstance(result, ValidationResult)
        assert result.passed is True
        assert result.sys_failure is False
        assert len(result.errors) == 0

    def test_validate_record_with_errors(self):
        """Test record validation with validation errors."""
        schema = {
            'ptid': {
                'type': 'string',
                'required': True
            },
            'age': {
                'type': 'integer',
                'min': 0,
                'max': 120
            }
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        invalid_record = {
            'ptid': 'TEST001',
            'age': 150  # Invalid age > 120
        }

        result = qc.validate_record(invalid_record)

        assert isinstance(result, ValidationResult)
        assert result.passed is False
        assert result.sys_failure is False
        assert len(result.errors) > 0
        assert 'age' in result.errors

    def test_validate_record_with_missing_required_field(self):
        """Test record validation with missing required field."""
        schema = {
            'ptid': {
                'type': 'string',
                'required': True
            },
            'required_field': {
                'type': 'string',
                'required': True
            }
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        incomplete_record = {
            'ptid': 'TEST001'
            # Missing required_field
        }

        result = qc.validate_record(incomplete_record)

        assert isinstance(result, ValidationResult)
        assert result.passed is False
        assert 'required_field' in result.errors

    def test_validate_record_with_system_error(self):
        """Test record validation with system error."""
        schema = {
            'ptid': {
                'type': 'string',
                'required': True
            }
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        # Mock validator to raise an exception
        with patch.object(qc.validator, 'validate', side_effect=Exception("System error")):
            record = {'ptid': 'TEST001'}

            # The quality check should catch the exception and handle it gracefully
            # or the exception should propagate
            try:
                result = qc.validate_record(record)
                assert isinstance(result, ValidationResult)
                assert result.sys_failure is True
            except Exception as e:
                # If exception propagates, it should be the expected system error
                assert "System error" in str(e)


class TestValidationResult:
    """Test ValidationResult data structure."""

    def test_validation_result_creation(self):
        """Test ValidationResult creation."""
        errors = {'field1': ['error1'], 'field2': ['error2']}

        result = ValidationResult(
            passed=False,
            errors=errors,
            sys_failure=False,
            error_tree=None
        )

        assert result.passed is False
        assert result.errors == errors
        assert result.sys_failure is False

    def test_validation_result_passed_state(self):
        """Test ValidationResult in passed state."""
        result = ValidationResult(
            passed=True,
            errors={},
            sys_failure=False,
            error_tree=None
        )

        assert result.passed is True
        assert len(result.errors) == 0
        assert result.sys_failure is False

    def test_validation_result_system_failure_state(self):
        """Test ValidationResult in system failure state."""
        result = ValidationResult(
            passed=False,
            errors={},
            sys_failure=True,
            error_tree=None
        )

        assert result.passed is False
        assert result.sys_failure is True


class TestNACCValidator:
    """Test NACC Validator functionality."""

    def test_nacc_validator_initialization(self):
        """Test NACC validator initialization."""
        schema = {
            'test_field': {
                'type': 'string',
                'required': True
            }
        }

        validator = NACCValidator(schema)

        # Check that the validator has the schema (it's stored in parent class)
        assert hasattr(validator, 'schema')
        assert hasattr(validator, 'dtypes')
        assert isinstance(validator.dtypes, dict)

    def test_nacc_validator_data_type_mapping(self):
        """Test NACC validator data type mapping."""
        schema = {
            'string_field': {'type': 'string'},
            'integer_field': {'type': 'integer'},
            'float_field': {'type': 'float'},
            'boolean_field': {'type': 'boolean'},
            'date_field': {'type': 'date'},
            'datetime_field': {'type': 'datetime'}
        }

        validator = NACCValidator(schema)

        expected_mappings = {
            'string_field': 'str',
            'integer_field': 'int',
            'float_field': 'float',
            'boolean_field': 'bool',
            'date_field': 'date',
            'datetime_field': 'datetime'
        }

        for field, expected_type in expected_mappings.items():
            assert validator.dtypes.get(field) == expected_type

    def test_nacc_validator_with_primary_key(self):
        """Test NACC validator with primary key configuration."""
        schema = {
            'ptid': {'type': 'string', 'required': True},
            'test_field': {'type': 'string'}
        }

        validator = NACCValidator(schema)
        validator.primary_key = 'ptid'

        assert validator.primary_key == 'ptid'

    def test_nacc_validator_with_datastore(self):
        """Test NACC validator with datastore configuration."""
        schema = {
            'ptid': {'type': 'string', 'required': True},
            'test_field': {'type': 'string'}
        }

        mock_datastore = Mock()
        mock_datastore.pk_field = 'ptid'

        validator = NACCValidator(schema)
        validator.datastore = mock_datastore

        assert validator.datastore == mock_datastore


class TestValidationRules:
    """Test various validation rules and scenarios."""

    def test_string_validation_rules(self):
        """Test string validation rules."""
        schema = {
            'ptid': {
                'type': 'string',
                'required': True,
                'minlength': 3,
                'maxlength': 10
            }
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        # Valid string
        valid_record = {'ptid': 'TEST001'}
        result = qc.validate_record(valid_record)
        assert result.passed is True

        # Too short
        short_record = {'ptid': 'AB'}
        result = qc.validate_record(short_record)
        assert result.passed is False

        # Too long
        long_record = {'ptid': 'VERYLONGPTID123'}
        result = qc.validate_record(long_record)
        assert result.passed is False

    def test_integer_validation_rules(self):
        """Test integer validation rules."""
        schema = {
            'ptid': {'type': 'string', 'required': True},
            'age': {
                'type': 'integer',
                'min': 0,
                'max': 120
            }
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        # Valid integer
        valid_record = {'ptid': 'TEST001', 'age': 65}
        result = qc.validate_record(valid_record)
        assert result.passed is True

        # Below minimum
        below_min_record = {'ptid': 'TEST001', 'age': -1}
        result = qc.validate_record(below_min_record)
        assert result.passed is False

        # Above maximum
        above_max_record = {'ptid': 'TEST001', 'age': 150}
        result = qc.validate_record(above_max_record)
        assert result.passed is False

    def test_allowed_values_validation(self):
        """Test allowed values validation."""
        schema = {
            'ptid': {'type': 'string', 'required': True},
            'status': {
                'type': 'string',
                'allowed': ['active', 'inactive', 'pending']
            }
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        # Valid value
        valid_record = {'ptid': 'TEST001', 'status': 'active'}
        result = qc.validate_record(valid_record)
        assert result.passed is True

        # Invalid value
        invalid_record = {'ptid': 'TEST001', 'status': 'invalid_status'}
        result = qc.validate_record(invalid_record)
        assert result.passed is False


class TestValidationWithDataframes:
    """Test validation with pandas DataFrames."""

    def test_dataframe_validation_success(self):
        """Test validation of DataFrame with valid data."""
        schema = {
            'ptid': {'type': 'string', 'required': True},
            'age': {'type': 'integer', 'min': 0, 'max': 120}
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        # Create test DataFrame
        data = pd.DataFrame([
            {'ptid': 'TEST001', 'age': 65},
            {'ptid': 'TEST002', 'age': 45},
            {'ptid': 'TEST003', 'age': 78}
        ])

        # Validate each record
        all_passed = True
        for _, record in data.iterrows():
            record_dict = record.to_dict()
            result = qc.validate_record(record_dict)
            if not result.passed:
                all_passed = False
                break

        assert all_passed is True

    def test_dataframe_validation_with_errors(self):
        """Test validation of DataFrame with invalid data."""
        schema = {
            'ptid': {'type': 'string', 'required': True},
            'age': {'type': 'integer', 'min': 0, 'max': 120}
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        # Create test DataFrame with invalid data
        data = pd.DataFrame([
            {'ptid': 'TEST001', 'age': 65},   # Valid
            {'ptid': 'TEST002', 'age': 150},  # Invalid age
            {'ptid': 'TEST003', 'age': -5}    # Invalid age
        ])

        # Validate each record and collect results
        results = []
        for _, record in data.iterrows():
            record_dict = record.to_dict()
            result = qc.validate_record(record_dict)
            results.append(result)

        assert results[0].passed is True   # First record should pass
        assert results[1].passed is False  # Second record should fail
        assert results[2].passed is False  # Third record should fail


class TestValidationRobustness:
    """Test validation robustness and error handling."""

    def test_validation_with_empty_record(self):
        """Test validation with empty record."""
        schema = {
            'ptid': {'type': 'string', 'required': True}
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        empty_record = {}
        result = qc.validate_record(empty_record)

        assert result.passed is False
        assert 'ptid' in result.errors

    def test_validation_with_none_values(self):
        """Test validation with None values."""
        schema = {
            'ptid': {'type': 'string', 'required': True},
            'optional_field': {'type': 'string', 'nullable': True}
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        record_with_none = {
            'ptid': 'TEST001',
            'optional_field': None
        }

        result = qc.validate_record(record_with_none)

        # Should handle None values appropriately based on schema
        assert isinstance(result, ValidationResult)

    def test_validation_with_unexpected_fields(self):
        """Test validation with unexpected fields."""
        schema = {
            'ptid': {'type': 'string', 'required': True}
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field, strict=False)

        record_with_extra = {
            'ptid': 'TEST001',
            'unexpected_field': 'some_value'
        }

        result = qc.validate_record(record_with_extra)

        # Should handle unexpected fields based on strict mode
        assert isinstance(result, ValidationResult)

    def test_validation_with_malformed_data_types(self):
        """Test validation with malformed data types."""
        schema = {
            'ptid': {'type': 'string', 'required': True},
            'age': {'type': 'integer'}
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        malformed_record = {
            'ptid': 'TEST001',
            'age': 'not_a_number'
        }

        result = qc.validate_record(malformed_record)

        assert result.passed is False
        assert 'age' in result.errors


class TestValidationIntegration:
    """Test validation integration with pipeline components."""

    @patch('nacc_form_validator.quality_check.QualityCheck.validate_record')
    def test_validation_pipeline_integration(self, mock_validate):
        """Test validation integration within pipeline."""
        # Mock validation result
        mock_result = ValidationResult(
            passed=True,
            errors={},
            sys_failure=False,
            error_tree=None
        )
        mock_validate.return_value = mock_result

        schema = {
            'ptid': {'type': 'string', 'required': True}
        }
        pk_field = 'ptid'

        qc = QualityCheck(schema=schema, pk_field=pk_field)

        test_record = {'ptid': 'TEST001'}
        result = qc.validate_record(test_record)

        assert result == mock_result
        mock_validate.assert_called_once_with(test_record)


if __name__ == '__main__':
    pytest.main([__file__])
