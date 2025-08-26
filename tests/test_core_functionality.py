"""
Focused test suite for core functionality of the UDSv4 REDCap QC Validator.
This test file focuses on testable functionality without making assumptions
about internal API details.
"""

import pytest
import pandas as pd
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime
import sqlite3
import json

# Add src to path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pipeline.config_manager import QCConfig, get_config
from pipeline.report_pipeline import run_report_pipeline
from pipeline.reports import ReportFactory
from pipeline.context import ProcessingContext, ExportConfiguration, ReportConfiguration
from pipeline.helpers import build_complete_visits_df


class TestConfigurationSystem:
    """Test the configuration management system."""

    def test_config_initialization(self):
        """Test basic configuration initialization."""
        config = QCConfig()
        
        # Check that config object is created
        assert isinstance(config, QCConfig)
        
        # Check that validation returns errors for empty config
        errors = config.validate()
        assert isinstance(errors, list)
        assert len(errors) > 0

    def test_config_singleton_pattern(self):
        """Test that get_config returns singleton instance."""
        config1 = get_config()
        config2 = get_config()
        
        # Should be the same instance
        assert config1 is config2

    def test_config_force_reload(self):
        """Test force reloading configuration."""
        config1 = get_config()
        config2 = get_config(force_reload=True)
        
        # Should be different instances after force reload
        assert config1 is not config2

    def test_config_environment_loading(self):
        """Test configuration loading from environment variables."""
        test_env = {
            'REDCAP_API_URL': 'https://test.redcap.com/api/',
            'REDCAP_API_TOKEN': 'test_token_123',
            'OUTPUT_PATH': '/tmp/test_output',
            'LOG_LEVEL': 'DEBUG'
        }
        
        with patch.dict(os.environ, test_env):
            config = QCConfig()
            
            assert config.api_url == 'https://test.redcap.com/api/'
            assert config.api_token == 'test_token_123'
            assert config.output_path == '/tmp/test_output'
            assert config.log_level == 'DEBUG'

    def test_config_validation_required_fields(self):
        """Test configuration validation for required fields."""
        config = QCConfig()
        
        # Test with missing required fields
        errors = config.validate()
        assert len(errors) > 0
        
        # Add required fields
        config.api_url = 'https://test.redcap.com/api/'
        config.api_token = 'test_token'
        
        # Should have fewer errors
        new_errors = config.validate()
        assert len(new_errors) < len(errors)

    def test_config_mode_validation(self):
        """Test validation of configuration mode."""
        config = QCConfig()
        config.api_url = 'https://test.redcap.com/api/'
        config.api_token = 'test_token'
        
        # Test valid modes
        valid_modes = ['complete_visits', 'all_incomplete_visits', 'custom']
        for mode in valid_modes:
            config.mode = mode
            errors = config.validate()
            # Should not have mode-related errors
            mode_errors = [e for e in errors if 'mode' in e.lower()]
            assert len(mode_errors) == 0

        # Test invalid mode
        config.mode = 'invalid_mode'
        errors = config.validate()
        # Should have mode-related error
        mode_errors = [e for e in errors if 'mode' in e.lower()]
        assert len(mode_errors) > 0


class TestReportGeneration:
    """Test report generation functionality."""

    @pytest.fixture
    def sample_processed_records(self):
        """Create sample processed records for testing."""
        return pd.DataFrame({
            'ptid': ['1001', '1002', '1003'],
            'redcap_event_name': ['udsv4_ivp_1_arm_1'] * 3,
            'instrument_name': ['a1'] * 3,
            'status': ['complete', 'complete', 'complete']
        })

    @pytest.fixture
    def sample_errors_df(self):
        """Create sample errors DataFrame for testing."""
        return pd.DataFrame({
            'ptid': ['1001', '1002'],
            'redcap_event_name': ['udsv4_ivp_1_arm_1'] * 2,
            'instrument_name': ['a1'] * 2,
            'error': ['Error 1', 'Error 2'],
            'error_type': ['validation'] * 2
        })

    def test_report_factory_status_reports(self, sample_processed_records, sample_errors_df):
        """Test tool status report generation using ReportFactory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up contexts
            processing_context = ProcessingContext(
                data_df=sample_processed_records,
                instrument_list=['a1'],
                rules_cache={},
                primary_key_field='ptid',
                config=None
            )
            
            export_config = ExportConfiguration(
                output_dir=Path(temp_dir),
                date_tag='26AUG2025',
                time_tag='140000'
            )
            
            report_config = ReportConfiguration(
                qc_run_by='tester',
                primary_key_field='ptid',
                instruments=['a1']
            )
            
            # Generate tool status reports using ReportFactory
            factory = ReportFactory(processing_context)
            status_path = factory.generate_status_report(
                all_records_df=sample_processed_records,
                complete_visits_df=pd.DataFrame(),
                detailed_validation_logs_df=pd.DataFrame(),
                export_config=export_config,
                report_config=report_config
            )
            
            # Check that report file was created
            assert status_path.exists()
            
            # Check report content
            report_df = pd.read_csv(status_path)
            assert 'metric' in report_df.columns
            assert status_path.stat().st_size > 0

    def test_report_factory_aggregate_error_report(self, sample_errors_df):
        """Test aggregate error count report generation using ReportFactory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock data for required parameters
            all_records_df = pd.DataFrame({'ptid': ['TEST001', 'TEST002']})
            
            # Set up contexts
            processing_context = ProcessingContext(
                data_df=all_records_df,
                instrument_list=['a1', 'a2'],
                rules_cache={},
                primary_key_field='ptid',
                config=None
            )
            
            export_config = ExportConfiguration(
                output_dir=Path(temp_dir),
                date_tag='26AUG2025',
                time_tag='140000'
            )
            
            report_config = ReportConfiguration(
                qc_run_by='tester',
                primary_key_field='ptid',
                instruments=['a1', 'a2']
            )
            
            # Generate aggregate error count report using ReportFactory
            factory = ReportFactory(processing_context)
            aggregate_path = factory.generate_aggregate_error_report(
                df_errors=sample_errors_df,
                all_records_df=all_records_df,
                export_config=export_config,
                report_config=report_config
            )
            
            # Check that report file was created
            assert aggregate_path.exists()
            
            # Check report content
            report_df = pd.read_csv(aggregate_path)
            assert 'ptid' in report_df.columns
            assert aggregate_path.stat().st_size > 0


class TestPipelineIntegration:
    """Test pipeline integration with mocked dependencies."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for testing."""
        config = QCConfig()
        config.mode = 'complete_visits'
        config.user_initials = 'JDT'
        config.instruments = ['a1']
        config.events = ['udsv4_ivp_1_arm_1']
        config.primary_key_field = 'ptid'
        config.api_url = 'https://test.redcap.com/api/'
        config.api_token = 'test_token'
        config.output_path = tempfile.mkdtemp()
        config.json_rules_path = str(Path(__file__).parent.parent / 'config' / 'json_rules')
        config.log_level = 'INFO'
        return config

    @pytest.fixture
    def sample_redcap_data(self):
        """Create sample REDCap data for testing."""
        return pd.DataFrame({
            'ptid': ['1001', '1002', '1003'],
            'redcap_event_name': ['udsv4_ivp_1_arm_1'] * 3,
            'a1_complete': [2, 2, 2],  # 2 = complete
            'a1_field1': ['value1', 'value2', 'value3'],
            'a1_field2': ['10', '20', '30']
        })

    @patch('pipeline.fetcher.RedcapETLPipeline.run')
    @patch('pipeline.helpers.load_rules_for_instruments')
    @patch('pipeline.report_pipeline.process_instruments_etl')
    def test_run_report_pipeline_basic(self, mock_process, mock_load_rules, mock_pipeline_run, 
                                      mock_config, sample_redcap_data):
        """Test basic pipeline run without datastore."""
        # Setup mocks
        from pipeline.fetcher import ETLResult
        mock_pipeline_run.return_value = ETLResult(
            data=sample_redcap_data,
            records_processed=len(sample_redcap_data),
            execution_time=1.0,
            saved_files=[]
        )
        mock_load_rules.return_value = {}
        mock_process.return_value = (
            sample_redcap_data,  # processed_records
            pd.DataFrame(),  # errors
            []  # pass_fail_log
        )
        
        # Run pipeline without datastore
        with patch('pipeline.report_pipeline.ReportFactory') as mock_factory:
            mock_factory_instance = mock_factory.return_value
            mock_factory_instance.export_all_reports.return_value = []
            
            run_report_pipeline(config=mock_config)
            
            # Verify that components were called
            mock_pipeline_run.assert_called_once()
            mock_process.assert_called_once()
            mock_factory.assert_called()

    @patch('pipeline.fetcher.RedcapETLPipeline.run')
    @patch('pipeline.helpers.load_rules_for_instruments')
    @patch('pipeline.report_pipeline.process_instruments_etl')
    @patch('pipeline.report_pipeline._store_validation_in_database')
    def test_run_report_pipeline_with_datastore(self, mock_store_db, mock_process, 
                                               mock_load_rules, mock_pipeline_run, 
                                               mock_config, sample_redcap_data):
        """Test pipeline run with datastore enabled."""
        # Setup mocks
        from pipeline.fetcher import ETLResult
        mock_pipeline_run.return_value = ETLResult(
            data=sample_redcap_data,
            records_processed=len(sample_redcap_data),
            execution_time=1.0,
            saved_files=[]
        )
        mock_load_rules.return_value = {}
        mock_process.return_value = (
            sample_redcap_data,  # processed_records
            pd.DataFrame(),  # errors
            []  # pass_fail_log
        )
        mock_store_db.return_value = {'status': 'success'}
        
        # Set mode to complete_visits for datastore compatibility
        mock_config.mode = 'complete_visits'
        
        # Run pipeline with datastore
        with patch('pipeline.report_pipeline.ReportFactory') as mock_factory:
            mock_factory_instance = mock_factory.return_value
            mock_factory_instance.export_all_reports.return_value = []
            
            run_report_pipeline(config=mock_config)
            
            # Verify that components were called
            mock_pipeline_run.assert_called_once()
            mock_process.assert_called_once()
            mock_factory.assert_called()
            mock_store_db.assert_called_once()


class TestHelperFunctions:
    """Test helper functions."""

    def test_build_complete_visits_df_basic(self):
        """Test build_complete_visits_df with basic data."""
        sample_data = pd.DataFrame({
            'ptid': ['1001', '1002', '1003', '1004'],
            'redcap_event_name': ['udsv4_ivp_1_arm_1'] * 4,
            'a1_complete': [2, 2, 2, 1],  # 2 = complete, 1 = incomplete
            'a2_complete': [2, 2, 2, 2],
            'a1_field1': ['value1', 'value2', 'value3', 'value4'],
            'a2_field1': ['A', 'B', 'C', 'D']
        })
        
        # Test with instrument filter
        result, _ = build_complete_visits_df(
            data_df=sample_data,
            instrument_list=['a1', 'a2']
        )
        
        # Should filter out incomplete records
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3  # Should exclude ptid 1004 (incomplete a1)
        assert '1004' not in result['ptid'].values
        
        # Should include complete records
        assert '1001' in result['ptid'].values
        assert '1002' in result['ptid'].values
        assert '1003' in result['ptid'].values


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_missing_api_credentials(self):
        """Test handling of missing API credentials."""
        config = QCConfig()
        # Don't set api_url or api_token
        
        errors = config.validate()
        
        # Should detect missing credentials
        assert len(errors) > 0
        assert any('api_url' in error.lower() for error in errors)
        assert any('api_token' in error.lower() for error in errors)

    def test_invalid_output_directory(self):
        """Test handling of invalid output directory."""
        config = QCConfig()
        config.output_path = '/invalid/path/that/does/not/exist'
        
        # Should handle invalid path gracefully
        errors = config.validate()
        
        # Note: The actual behavior depends on implementation
        # This test checks that validation doesn't crash
        assert isinstance(errors, list)

    def test_empty_dataframe_handling(self):
        """Test handling of empty DataFrames."""
        empty_df = pd.DataFrame()
        
        # Should handle empty DataFrame without errors
        result, _ = build_complete_visits_df(
            data_df=empty_df,
            instrument_list=['a1']
        )
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestDataValidation:
    """Test data validation scenarios."""

    def test_valid_mode_values(self):
        """Test validation of mode values."""
        config = QCConfig()
        config.api_url = 'https://test.redcap.com/api/'
        config.api_token = 'test_token'
        
        valid_modes = ['complete_visits', 'all_incomplete_visits', 'custom']
        
        for mode in valid_modes:
            config.mode = mode
            errors = config.validate()
            
            # Should not have mode-specific errors
            mode_errors = [e for e in errors if 'mode' in e.lower()]
            assert len(mode_errors) == 0

    def test_invalid_mode_values(self):
        """Test validation of invalid mode values."""
        config = QCConfig()
        config.api_url = 'https://test.redcap.com/api/'
        config.api_token = 'test_token'
        
        invalid_modes = ['invalid', 'bad_mode', '', None]
        
        for mode in invalid_modes:
            config.mode = mode
            errors = config.validate()
            
            # Should have mode-specific errors
            mode_errors = [e for e in errors if 'mode' in e.lower()]
            assert len(mode_errors) > 0

    def test_required_field_validation(self):
        """Test validation of required fields."""
        config = QCConfig()
        
        # Test completely empty config
        errors = config.validate()
        assert len(errors) > 0
        
        # Add required fields one by one
        config.api_url = 'https://test.redcap.com/api/'
        errors_after_url = config.validate()
        assert len(errors_after_url) < len(errors)
        
        config.api_token = 'test_token'
        errors_after_token = config.validate()
        assert len(errors_after_token) < len(errors_after_url)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
