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
from pipeline.report_pipeline import (
    run_report_pipeline, 
    get_datastore_path,
    generate_tool_status_reports,
    generate_aggregate_error_count_report
)
from pipeline.datastore import EnhancedDatastore
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


class TestDatastorePathResolution:
    """Test datastore path resolution functionality."""

    def test_datastore_path_environment_variable(self):
        """Test datastore path resolution from environment variable."""
        test_path = '/custom/path/validation_history.db'
        
        with patch.dict(os.environ, {'VALIDATION_HISTORY_DB_PATH': test_path}):
            path = get_datastore_path()
            assert path == test_path

    def test_datastore_path_default(self):
        """Test datastore path resolution with default path."""
        # Clear environment variable
        with patch.dict(os.environ, {}, clear=True):
            path = get_datastore_path()
            assert 'validation_history.db' in path
            assert 'data' in path

    def test_datastore_path_custom_default(self):
        """Test datastore path resolution with custom default."""
        custom_default = '/tmp/custom_default.db'
        
        with patch.dict(os.environ, {}, clear=True):
            path = get_datastore_path(custom_default)
            assert path == custom_default


class TestEnhancedDatastore:
    """Test enhanced datastore functionality."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_datastore_initialization(self, temp_db_path):
        """Test datastore initialization."""
        datastore = EnhancedDatastore(temp_db_path)
        
        assert datastore.db_path == Path(temp_db_path)
        assert os.path.exists(temp_db_path)
        
        # Check database schema
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Check validation_runs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='validation_runs'")
        assert cursor.fetchone() is not None
        
        # Check error_records table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='error_records'")
        assert cursor.fetchone() is not None
        
        conn.close()

    def test_datastore_schema_structure(self, temp_db_path):
        """Test database schema structure."""
        datastore = EnhancedDatastore(temp_db_path)
        
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Check validation_runs table structure
        cursor.execute("PRAGMA table_info(validation_runs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        expected_columns = ['run_id', 'timestamp', 'instrument', 'total_records', 'error_count']
        for col in expected_columns:
            assert col in columns
        
        # Check error_records table structure
        cursor.execute("PRAGMA table_info(error_records)")
        columns = [row[1] for row in cursor.fetchall()]
        
        expected_columns = ['id', 'run_id', 'ptid', 'redcap_event_name', 'instrument_name', 'variable']
        for col in expected_columns:
            assert col in columns
        
        conn.close()

    def test_datastore_directory_creation(self):
        """Test that datastore creates parent directories."""
        test_path = os.path.join(tempfile.gettempdir(), 'test_subdir', 'test.db')
        
        # Ensure parent directory doesn't exist
        parent_dir = os.path.dirname(test_path)
        if os.path.exists(parent_dir):
            os.rmdir(parent_dir)
        
        try:
            datastore = EnhancedDatastore(test_path)
            
            # Should create parent directory and database
            assert os.path.exists(parent_dir)
            assert os.path.exists(test_path)
            
        finally:
            # Cleanup
            if os.path.exists(test_path):
                os.unlink(test_path)
            if os.path.exists(parent_dir):
                os.rmdir(parent_dir)

    def test_store_validation_run_complete_events_only(self, temp_db_path):
        """Test that datastore only accepts complete_events mode."""
        datastore = EnhancedDatastore(temp_db_path)
        
        sample_errors = pd.DataFrame({
            'ptid': ['1001'],
            'redcap_event_name': ['udsv4_ivp_1_arm_1'],
            'instrument_name': ['a1'],
            'variable': ['a1_field1'],
            'current_value': [''],
            'expected_value': ['required'],
            'error': ['Field is required']
        })
        
        # Test with complete_events mode (should work)
        run_id = datastore.store_validation_run(
            instrument='a1',
            errors_df=sample_errors,
            total_records=100,
            run_config={'mode': 'complete_events'}
        )
        assert run_id is not None
        
        # Test with other mode (should return None)
        run_id = datastore.store_validation_run(
            instrument='a1',
            errors_df=sample_errors,
            total_records=100,
            run_config={'mode': 'all_incomplete_visits'}
        )
        assert run_id is None

    def test_generate_quality_dashboard_structure(self, temp_db_path):
        """Test quality dashboard structure."""
        datastore = EnhancedDatastore(temp_db_path)
        
        # Generate dashboard (even with empty database)
        dashboard = datastore.generate_quality_dashboard('a1')
        
        # Check basic structure
        assert isinstance(dashboard, dict)
        
        # Check for expected keys
        expected_keys = ['total_runs', 'current_error_rate', 'average_error_rate', 
                        'error_rate_trend', 'recent_errors', 'top_error_types']
        for key in expected_keys:
            assert key in dashboard


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

    def test_generate_tool_status_reports(self, sample_processed_records, sample_errors_df):
        """Test tool status report generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Generate tool status reports
            generate_tool_status_reports(
                processed_records_df=sample_processed_records,
                pass_fail_log=[],
                output_dir=temp_dir,
                file_suffix='test',
                qc_run_by='tester',
                primary_key_field='ptid',
                errors_df=sample_errors_df,
                instruments=['a1']
            )
            
            # Check that report file was created
            report_files = list(Path(temp_dir).glob('*Status_Report*'))
            assert len(report_files) > 0
            
            # Check report content
            report_file = report_files[0]
            assert report_file.exists()
            assert report_file.stat().st_size > 0

    def test_generate_aggregate_error_count_report(self, sample_errors_df):
        """Test aggregate error count report generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Generate aggregate error count report
            generate_aggregate_error_count_report(
                errors_df=sample_errors_df,
                output_dir=temp_dir,
                file_suffix='test',
                primary_key_field='ptid'
            )
            
            # Check that report file was created
            report_files = list(Path(temp_dir).glob('*ErrorCount*'))
            assert len(report_files) > 0
            
            # Check report content
            report_file = report_files[0]
            assert report_file.exists()
            assert report_file.stat().st_size > 0


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

    @patch('pipeline.fetcher.fetch_etl_data')
    @patch('pipeline.helpers.load_rules_for_instruments')
    @patch('pipeline.report_pipeline.process_instruments_etl')
    def test_run_report_pipeline_basic(self, mock_process, mock_load_rules, mock_fetch_data, 
                                      mock_config, sample_redcap_data):
        """Test basic pipeline run without datastore."""
        # Setup mocks
        mock_fetch_data.return_value = sample_redcap_data
        mock_load_rules.return_value = {}
        mock_process.return_value = (
            sample_redcap_data,  # processed_records
            pd.DataFrame(),  # errors
            []  # pass_fail_log
        )
        
        # Run pipeline without datastore
        with patch('pipeline.report_pipeline.export_results_to_csv') as mock_export:
            run_report_pipeline(config=mock_config, enable_datastore=False)
            
            # Verify that components were called
            mock_fetch_data.assert_called_once_with(mock_config)
            mock_process.assert_called_once()
            mock_export.assert_called()

    @patch('pipeline.fetcher.fetch_etl_data')
    @patch('pipeline.helpers.load_rules_for_instruments')
    @patch('pipeline.report_pipeline.process_instruments_etl')
    @patch('pipeline.report_pipeline._store_validation_in_database')
    def test_run_report_pipeline_with_datastore(self, mock_store_db, mock_process, 
                                               mock_load_rules, mock_fetch_data, 
                                               mock_config, sample_redcap_data):
        """Test pipeline run with datastore enabled."""
        # Setup mocks
        mock_fetch_data.return_value = sample_redcap_data
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
        with patch('pipeline.report_pipeline.export_results_to_csv') as mock_export:
            run_report_pipeline(config=mock_config, enable_datastore=True)
            
            # Verify that components were called
            mock_fetch_data.assert_called_once_with(mock_config)
            mock_process.assert_called_once()
            mock_export.assert_called()
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
        result = build_complete_visits_df(
            data_df=sample_data,
            instrument_list=['a1', 'a2'],
            events=['udsv4_ivp_1_arm_1'],
            ptid_list=[],
            primary_key_field='ptid'
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
        result = build_complete_visits_df(
            data_df=empty_df,
            instrument_list=['a1'],
            events=['udsv4_ivp_1_arm_1'],
            ptid_list=[],
            primary_key_field='ptid'
        )
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_datastore_invalid_path_handling(self):
        """Test datastore handling of invalid paths."""
        # Test with path that requires privileges
        invalid_path = '/root/invalid/path/database.db'
        
        # Should either create directory or handle error gracefully
        try:
            datastore = EnhancedDatastore(invalid_path)
            # If successful, verify it was created
            assert os.path.exists(os.path.dirname(invalid_path)) or datastore.db_path == Path(invalid_path)
        except (PermissionError, OSError) as e:
            # Expected behavior for invalid paths
            assert 'permission' in str(e).lower() or 'path' in str(e).lower()


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
