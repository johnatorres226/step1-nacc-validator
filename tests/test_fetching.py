"""
Essential tests for data fetching functionality.

This module tests the REDCap data fetching, API client, ETL pipeline,
and data validation components that are fundamental to the application.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from src.pipeline.config.config_manager import QCConfig

# Import the modules we're testing
from src.pipeline.core.fetcher import (
    REQUIRED_FIELDS,
    ETLContext,
    ETLResult,
    RedcapETLPipeline,
    validate_required_fields,
)


class TestETLContext:
    """Test ETL context creation and management."""

    def test_etl_context_creation_with_defaults(self):
        """Test ETL context creation with automatic timestamps."""
        config = QCConfig()
        context = ETLContext.create(config)

        assert isinstance(context, ETLContext)
        assert context.config == config
        assert isinstance(context.run_date, str)
        assert isinstance(context.time_stamp, str)
        assert context.output_path is not None

    def test_etl_context_creation_with_custom_tags(self):
        """Test ETL context creation with custom date and time tags."""
        config = QCConfig()
        custom_date = "01JAN2025"
        custom_time = "120000"

        context = ETLContext.create(config, date_tag=custom_date, time_tag=custom_time)

        assert context.run_date == custom_date
        assert context.time_stamp == custom_time

    def test_etl_context_output_path_handling(self):
        """Test ETL context output path handling."""
        config = QCConfig()

        with tempfile.TemporaryDirectory() as temp_dir:
            context = ETLContext.create(config, output_path=temp_dir)

            assert context.output_path == Path(temp_dir)
            assert context.output_path.is_absolute()


class TestETLResult:
    """Test ETL result data structure."""

    def test_etl_result_creation(self):
        """Test ETL result creation."""
        test_data = pd.DataFrame({"test": [1, 2, 3]})

        result = ETLResult(
            data=test_data, records_processed=3, execution_time=1.5, saved_files=[Path("test.csv")]
        )

        assert not result.is_empty
        assert result.records_processed == 3
        assert result.execution_time == 1.5
        assert len(result.saved_files) == 1

    def test_etl_result_empty_detection(self):
        """Test ETL result empty detection."""
        empty_data = pd.DataFrame()

        result = ETLResult(data=empty_data, records_processed=0, execution_time=0.1, saved_files=[])

        assert result.is_empty


class TestDataContract:
    """Test data validation contracts."""

    def test_data_contract_required_fields(self):
        """Test that data contract defines required fields."""
        assert isinstance(REQUIRED_FIELDS, list)
        assert "ptid" in REQUIRED_FIELDS
        assert "redcap_event_name" in REQUIRED_FIELDS

    def test_data_contract_validation_method_exists(self):
        """Test that data contract has validation capabilities."""
        # Check if validation function exists
        assert callable(validate_required_fields)


class TestRedcapETLPipeline:
    """Test the main RedCap ETL Pipeline functionality."""

    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        config = QCConfig()
        pipeline = RedcapETLPipeline(config)

        assert pipeline.config == config
        assert pipeline.context is None  # Should be initialized in run()
        assert pipeline.api_client is None

    def test_pipeline_component_initialization(self):
        """Test pipeline component initialization."""
        config = QCConfig()
        pipeline = RedcapETLPipeline(config)

        # Test private method for component initialization
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline._initialize_components(temp_dir, "01JAN2025", "120000")  # noqa: SLF001

            assert pipeline.context is not None
            assert isinstance(pipeline.context, ETLContext)

    @patch("src.pipeline.core.fetcher.requests.post")
    def test_api_payload_building(self, _mock_post):
        """Test API payload building functionality."""
        # Create config with explicit token to avoid environment issues
        with patch.dict(os.environ, {}, clear=True):  # Clear environment
            config = QCConfig(
                api_token="test_token",
                redcap_api_token="test_token",
                redcap_api_url="https://test.redcap.url",
            )
            pipeline = RedcapETLPipeline(config)

            instruments = ["a1_participant_demographics"]
            filter_logic = "test_filter"

            payload = pipeline._build_api_payload(instruments, filter_logic)  # noqa: SLF001

            assert isinstance(payload, dict)
            assert "token" in payload
            assert "content" in payload
            assert "forms" in payload  # Changed from 'instrument' to 'forms'
            assert payload["token"] == "test_token"
            assert payload["content"] == "record"
            assert filter_logic in payload.get("filterLogic", "")


class TestDataFetching:
    """Test data fetching from REDCap API."""

    def test_successful_data_fetch(self, requests_mock):
        """Test successful data fetching from REDCap."""
        # Mock API response
        mock_response_data = [
            {
                "ptid": "TEST001",
                "redcap_event_name": "udsv4_ivp_1_arm_1",
                "a1_birthyr": "1950",
                "packet": "I",
            },
            {
                "ptid": "TEST002",
                "redcap_event_name": "udsv4_ivp_1_arm_1",
                "a1_birthyr": "1960",
                "packet": "I4",
            },
        ]

        # Create config with explicit URLs to avoid environment variables
        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(
                redcap_api_token="test_token", redcap_api_url="https://test.redcap.url"
            )

        # Mock both possible URLs (test URL and any environment URL)
        requests_mock.post("https://test.redcap.url", json=mock_response_data)
        requests_mock.post("https://hsc-ctsc-rc-api.health.unm.edu/api/", json=mock_response_data)

        pipeline = RedcapETLPipeline(config)

        # Initialize components before fetching
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline._initialize_components(temp_dir, "01JAN2025", "120000")  # noqa: SLF001

            # Test data fetching
            data = pipeline._fetch_data()  # noqa: SLF001

            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["ptid"] == "TEST001"
            assert data[1]["ptid"] == "TEST002"

    def test_empty_data_fetch(self, requests_mock):
        """Test handling of empty data response."""
        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(
                redcap_api_token="test_token", redcap_api_url="https://test.redcap.url"
            )

        # Mock both possible URLs
        requests_mock.post("https://test.redcap.url", json=[])
        requests_mock.post("https://hsc-ctsc-rc-api.health.unm.edu/api/", json=[])

        pipeline = RedcapETLPipeline(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline._initialize_components(temp_dir, "01JAN2025", "120000")  # noqa: SLF001

            data = pipeline._fetch_data()

            assert isinstance(data, list)
            assert len(data) == 0

    def test_api_error_handling(self, requests_mock):
        """Test handling of API errors."""
        config = QCConfig(
            redcap_api_token="invalid_token", redcap_api_url="https://test.redcap.url"
        )

        requests_mock.post("https://test.redcap.url", status_code=403, text="Forbidden")

        pipeline = RedcapETLPipeline(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline._initialize_components(temp_dir, "01JAN2025", "120000")

            # Should handle API errors gracefully
            # Might raise requests.HTTPError or custom exception
            with pytest.raises(Exception, match="Forbidden"):
                pipeline._fetch_data()  # noqa: SLF001


class TestETLPipelineRun:
    """Test the complete ETL pipeline run functionality."""

    @patch("src.pipeline.core.fetcher.RedcapETLPipeline._fetch_data")
    def test_pipeline_run_success(self, mock_fetch):
        """Test successful pipeline execution."""
        # Mock fetched data
        mock_fetch.return_value = [
            {"ptid": "TEST001", "redcap_event_name": "udsv4_ivp_1_arm_1", "a1_birthyr": "1950"}
        ]

        config = QCConfig()
        pipeline = RedcapETLPipeline(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = pipeline.run(output_path=temp_dir)

            assert isinstance(result, ETLResult)
            assert not result.is_empty
            assert result.records_processed > 0

    @patch("src.pipeline.core.fetcher.RedcapETLPipeline._fetch_data")
    def test_pipeline_run_with_empty_data(self, mock_fetch):
        """Test pipeline execution with empty data."""
        mock_fetch.return_value = []

        config = QCConfig()
        pipeline = RedcapETLPipeline(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = pipeline.run(output_path=temp_dir)

            assert isinstance(result, ETLResult)
            assert result.is_empty
            assert result.records_processed == 0


class TestDataValidation:
    """Test data validation within the ETL process."""

    def test_data_contract_validation(self):
        """Test data validation against contract requirements."""
        # Test valid data
        valid_record = {
            "ptid": "TEST001",
            "redcap_event_name": "udsv4_ivp_1_arm_1",
            "a1_birthyr": "1950",
        }

        # Check that required fields are present
        for field in REQUIRED_FIELDS:
            assert field in valid_record

    def test_data_contract_validation_missing_fields(self):
        """Test validation with missing required fields."""
        invalid_record = {
            "a1_birthyr": "1950"  # Missing ptid and redcap_event_name
        }

        # Check that required fields are missing
        missing_fields = [
            field for field in REQUIRED_FIELDS if field not in invalid_record
        ]

        assert len(missing_fields) > 0


class TestETLPipelineRobustness:
    """Test ETL pipeline robustness and error handling."""

    def test_pipeline_handles_invalid_config(self):
        """Test pipeline with invalid configuration."""
        # Empty config should still create pipeline but may fail during run
        config = QCConfig()
        pipeline = RedcapETLPipeline(config)

        assert pipeline.config == config

    @patch("src.pipeline.core.fetcher.RedcapETLPipeline._fetch_data")
    def test_pipeline_handles_fetch_failure(self, mock_fetch):
        """Test pipeline handling of fetch failures."""
        mock_fetch.side_effect = Exception("API Error")

        config = QCConfig()
        pipeline = RedcapETLPipeline(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Should either handle the error gracefully or raise appropriate exception
            with pytest.raises(Exception, match="API Error"):
                pipeline.run(output_path=temp_dir)

    def test_pipeline_with_invalid_output_path(self):
        """Test pipeline with invalid output path."""
        config = QCConfig()
        pipeline = RedcapETLPipeline(config)

        # Should handle invalid paths gracefully by returning empty result
        invalid_path = "/this/path/does/not/exist"

        # Mock _fetch_data to return empty data
        with patch("src.pipeline.core.fetcher.RedcapETLPipeline._fetch_data", return_value=[]):
            result = pipeline.run(output_path=invalid_path)
            # Should return empty result gracefully
            assert isinstance(result, ETLResult)
            assert result.is_empty


class TestETLPipelineIntegration:
    """Test ETL pipeline integration scenarios."""

    @patch("src.pipeline.core.data_processing.get_variables_for_instrument")
    def test_end_to_end_pipeline_simulation(self, mock_get_vars, requests_mock):
        """Test end-to-end pipeline simulation."""
        # Mock get_variables_for_instrument
        mock_get_vars.return_value = ["ptid", "redcap_event_name", "a1_birthyr"]

        # Mock API response
        mock_response_data = [
            {
                "ptid": "TEST001",
                "redcap_event_name": "udsv4_ivp_1_arm_1",
                "a1_birthyr": "1950",
                "packet": "I",
            }
        ]

        with patch.dict(os.environ, {}, clear=True):
            config = QCConfig(
                redcap_api_token="test_token",
                redcap_api_url="https://test.redcap.url",
                instruments=["a1_participant_demographics"],
            )

        # Mock both URLs
        requests_mock.post("https://test.redcap.url", json=mock_response_data)
        requests_mock.post("https://hsc-ctsc-rc-api.health.unm.edu/api/", json=mock_response_data)

        pipeline = RedcapETLPipeline(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = pipeline.run(output_path=temp_dir)

            # Verify the pipeline executed successfully
            assert isinstance(result, ETLResult)
            assert result.records_processed > 0
            assert result.execution_time > 0


if __name__ == "__main__":
    pytest.main([__file__])
