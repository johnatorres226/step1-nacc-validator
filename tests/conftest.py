"""
Pytest configuration and shared fixtures for the test suite.

This module provides common fixtures, test utilities, and configuration
that can be used across all test modules in the project.
"""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from nacc_form_validator.models import ValidationResult

# Import project modules
from src.pipeline.config_manager import QCConfig


@pytest.fixture
def temp_directory():
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_config(temp_directory):
    """Provide a sample QCConfig for testing."""
    config = QCConfig(
        redcap_api_token='test_token_12345',
        redcap_api_url='https://test.redcap.example.com',
        project_id='test_project_123',
        output_path=str(temp_directory),
        instruments=['a1_participant_demographics', 'b1_vital_signs_and_anthropometrics']
    )
    return config


@pytest.fixture
def sample_validation_schema():
    """Provide a sample validation schema for testing."""
    return {
        'ptid': {
            'type': 'string',
            'required': True,
            'minlength': 3,
            'maxlength': 20
        },
        'redcap_event_name': {
            'type': 'string',
            'required': True
        },
        'a1_birthyr': {
            'type': 'integer',
            'min': 1900,
            'max': 2023
        },
        'a1_sex': {
            'type': 'integer',
            'allowed': [1, 2, 9]
        },
        'packet': {
            'type': 'string',
            'allowed': ['I', 'I4', 'F']
        }
    }


@pytest.fixture
def sample_valid_record():
    """Provide a sample valid record for testing."""
    return {
        'ptid': 'TEST001',
        'redcap_event_name': 'udsv4_ivp_1_arm_1',
        'a1_birthyr': 1950,
        'a1_sex': 1,
        'packet': 'I'
    }


@pytest.fixture
def sample_invalid_record():
    """Provide a sample invalid record for testing."""
    return {
        'ptid': 'T',  # Too short
        'redcap_event_name': 'udsv4_ivp_1_arm_1',
        'a1_birthyr': 2050,  # Future year
        'a1_sex': 5,  # Invalid value
        'packet': 'X'  # Invalid packet
    }


@pytest.fixture
def sample_dataframe():
    """Provide a sample DataFrame for testing."""
    return pd.DataFrame([
        {
            'ptid': 'TEST001',
            'redcap_event_name': 'udsv4_ivp_1_arm_1',
            'a1_birthyr': 1950,
            'a1_sex': 1,
            'packet': 'I'
        },
        {
            'ptid': 'TEST002',
            'redcap_event_name': 'udsv4_ivp_1_arm_1',
            'a1_birthyr': 1965,
            'a1_sex': 2,
            'packet': 'I4'
        },
        {
            'ptid': 'TEST003',
            'redcap_event_name': 'udsv4_ivp_1_arm_1',
            'a1_birthyr': 1970,
            'a1_sex': 1,
            'packet': 'F'
        }
    ])


@pytest.fixture
def sample_validation_result_passed():
    """Provide a sample passed ValidationResult."""
    return ValidationResult(
        passed=True,
        sys_failure=False,
        errors={},
        error_tree=None
    )


@pytest.fixture
def sample_validation_result_failed():
    """Provide a sample failed ValidationResult."""
    return ValidationResult(
        passed=False,
        sys_failure=False,
        errors={
            'a1_birthyr': ['Value is too high'],
            'a1_sex': ['Invalid value']
        },
        error_tree=None
    )


@pytest.fixture
def sample_validation_result_system_error():
    """Provide a sample system error ValidationResult."""
    return ValidationResult(
        passed=False,
        sys_failure=True,
        errors={'system': ['Database connection failed']},
        error_tree=None
    )


@pytest.fixture
def mock_redcap_api_response():
    """Provide a mock REDCap API response."""
    return [
        {
            'ptid': 'TEST001',
            'redcap_event_name': 'udsv4_ivp_1_arm_1',
            'a1_birthyr': '1950',
            'a1_sex': '1',
            'packet': 'I',
            'form_header_complete': '2'
        },
        {
            'ptid': 'TEST002',
            'redcap_event_name': 'udsv4_ivp_1_arm_1',
            'a1_birthyr': '1965',
            'a1_sex': '2',
            'packet': 'I4',
            'form_header_complete': '2'
        }
    ]


@pytest.fixture
def mock_validation_rules():
    """Provide mock validation rules for testing."""
    return {
        'I': {
            'a1_birthyr': {
                'type': 'integer',
                'min': 1900,
                'max': 2023
            },
            'a1_sex': {
                'type': 'integer',
                'allowed': [1, 2, 9]
            }
        },
        'I4': {
            'a1_birthyr': {
                'type': 'integer',
                'min': 1900,
                'max': 2023
            },
            'a1_sex': {
                'type': 'integer',
                'allowed': [1, 2, 9]
            }
        },
        'F': {
            'a1_birthyr': {
                'type': 'integer',
                'min': 1900,
                'max': 2023
            },
            'a1_sex': {
                'type': 'integer',
                'allowed': [1, 2, 9]
            }
        }
    }


@pytest.fixture
def mock_environment_variables():
    """Provide mock environment variables for testing."""
    env_vars = {
        'REDCAP_API_TOKEN': 'mock_token_12345',
        'REDCAP_API_URL': 'https://mock.redcap.url',
        'PROJECT_ID': 'mock_project_123',
        'OUTPUT_PATH': '/tmp/mock_output',
        'JSON_RULES_PATH_I': '/mock/rules/I',
        'JSON_RULES_PATH_I4': '/mock/rules/I4',
        'JSON_RULES_PATH_F': '/mock/rules/F'
    }

    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def sample_error_data():
    """Provide sample error data for testing reports."""
    return [
        {
            'ptid': 'TEST001',
            'instrument_name': 'a1_participant_demographics',
            'variable': 'a1_birthyr',
            'error_message': 'Value is too high',
            'current_value': '2050',
            'packet': 'I',
            'redcap_event_name': 'udsv4_ivp_1_arm_1'
        },
        {
            'ptid': 'TEST002',
            'instrument_name': 'a1_participant_demographics',
            'variable': 'a1_sex',
            'error_message': 'Invalid value',
            'current_value': '5',
            'packet': 'I4',
            'redcap_event_name': 'udsv4_ivp_1_arm_1'
        }
    ]


@pytest.fixture
def sample_passed_data():
    """Provide sample passed validation data for testing reports."""
    return [
        {
            'ptid': 'TEST001',
            'variable': 'a1_birthyr',
            'current_value': '1950',
            'json_rule': '{"type": "integer", "min": 1900, "max": 2023}',
            'rule_file': 'a1_rules.json',
            'packet': 'I',
            'redcap_event_name': 'udsv4_ivp_1_arm_1',
            'instrument_name': 'a1_participant_demographics'
        },
        {
            'ptid': 'TEST003',
            'variable': 'a1_sex',
            'current_value': '2',
            'json_rule': '{"type": "integer", "allowed": [1, 2, 9]}',
            'rule_file': 'a1_rules.json',
            'packet': 'F',
            'redcap_event_name': 'udsv4_ivp_1_arm_1',
            'instrument_name': 'a1_participant_demographics'
        }
    ]


@pytest.fixture
def sample_log_data():
    """Provide sample log data for testing reports."""
    return [
        {
            'ptid': 'TEST001',
            'instrument_name': 'a1_participant_demographics',
            'validation_status': 'PASSED',
            'error_count': 0,
            'redcap_event_name': 'udsv4_ivp_1_arm_1',
            'packet': 'I'
        },
        {
            'ptid': 'TEST002',
            'instrument_name': 'a1_participant_demographics',
            'validation_status': 'FAILED',
            'error_count': 2,
            'redcap_event_name': 'udsv4_ivp_1_arm_1',
            'packet': 'I4'
        }
    ]


# Test utilities
class TestUtils:
    """Utility functions for tests."""

    @staticmethod
    def create_mock_datastore(pk_field: str = 'ptid'):
        """Create a mock datastore for testing."""
        mock_datastore = Mock()
        mock_datastore.pk_field = pk_field
        mock_datastore.get_previous_record.return_value = None
        return mock_datastore

    @staticmethod
    def create_temp_json_file(data: Dict[str, Any], temp_dir: Path) -> Path:
        """Create a temporary JSON file with test data."""
        import json
        temp_file = temp_dir / "test_rules.json"
        with open(temp_file, 'w') as f:
            json.dump(data, f, indent=2)
        return temp_file

    @staticmethod
    def create_temp_csv_file(data: pd.DataFrame, temp_dir: Path, filename: str = "test_data.csv") -> Path:
        """Create a temporary CSV file with test data."""
        temp_file = temp_dir / filename
        data.to_csv(temp_file, index=False)
        return temp_file

    @staticmethod
    def assert_file_exists_and_not_empty(file_path: Path):
        """Assert that a file exists and is not empty."""
        assert file_path.exists(), f"File does not exist: {file_path}"
        assert file_path.stat().st_size > 0, f"File is empty: {file_path}"

    @staticmethod
    def assert_csv_has_expected_columns(csv_path: Path, expected_columns: list):
        """Assert that a CSV file has the expected columns."""
        df = pd.read_csv(csv_path)
        assert list(df.columns) == expected_columns, f"Columns mismatch in {csv_path}"


@pytest.fixture
def test_utils():
    """Provide test utilities."""
    return TestUtils


# Pytest hooks for better test reporting
def pytest_configure(config):
    """Configure pytest."""
    # Add markers
    config.addinivalue_line("markers", "config: Configuration tests")
    config.addinivalue_line("markers", "fetching: Data fetching tests")
    config.addinivalue_line("markers", "routing: Data routing tests")
    config.addinivalue_line("markers", "validation: Pipeline validation tests")
    config.addinivalue_line("markers", "output: Output generation tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add markers based on test file names
        if "test_configuration" in item.nodeid:
            item.add_marker(pytest.mark.config)
        elif "test_fetching" in item.nodeid:
            item.add_marker(pytest.mark.fetching)
        elif "test_data_routing" in item.nodeid:
            item.add_marker(pytest.mark.routing)
        elif "test_pipeline_validation" in item.nodeid:
            item.add_marker(pytest.mark.validation)
        elif "test_outputs" in item.nodeid:
            item.add_marker(pytest.mark.output)


def pytest_report_header(config):
    """Add custom header to pytest report."""
    return [
        "UDSv4 REDCap QC Validator - Essential Test Suite",
        f"Testing configuration, fetching, routing, validation, and outputs",
        f"Python version: {config.getoption('--version') if hasattr(config, 'getoption') else 'Unknown'}"
    ]
