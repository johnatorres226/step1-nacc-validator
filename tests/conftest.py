"""
Pytest configuration and shared fixtures for the test suite.

This module provides common fixtures, test utilities, and configuration
that can be used across all test modules in the project.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

# Import project modules
from src.pipeline.config.config_manager import QCConfig


@pytest.fixture
def temp_directory():
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_config(temp_directory):
    """Provide a sample QCConfig for testing."""
    config = QCConfig(
        redcap_api_token="test_token_12345",
        redcap_api_url="https://test.redcap.example.com",
        project_id="test_project_123",
        output_path=str(temp_directory),
        instruments=["a1_participant_demographics", "b1_vital_signs_and_anthropometrics"],
    )
    return config


@pytest.fixture
def sample_dataframe():
    """Provide a sample DataFrame for testing."""
    return pd.DataFrame(
        [
            {
                "ptid": "TEST001",
                "redcap_event_name": "udsv4_ivp_1_arm_1",
                "a1_birthyr": 1950,
                "a1_sex": 1,
                "packet": "I",
            },
            {
                "ptid": "TEST002",
                "redcap_event_name": "udsv4_ivp_1_arm_1",
                "a1_birthyr": 1965,
                "a1_sex": 2,
                "packet": "I4",
            },
            {
                "ptid": "TEST003",
                "redcap_event_name": "udsv4_ivp_1_arm_1",
                "a1_birthyr": 1970,
                "a1_sex": 1,
                "packet": "F",
            },
        ]
    )


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
