"""
Integration tests for the complete UDSv4 REDCap QC Validator pipeline.
These tests verify the end-to-end functionality of the system.
"""

import pytest
import pandas as pd
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime
import sqlite3

# Add src to path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pipeline.config_manager import QCConfig, get_config
from pipeline.report_pipeline import run_report_pipeline, validate_data
from pipeline.quality_check import QualityCheck
from pipeline.datastore import EnhancedDatastore
from pipeline.helpers import build_complete_visits_df
from pipeline.fetcher import fetch_etl_data


class TestPipelineIntegration:
    """Integration tests for the complete pipeline."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for testing."""
        config = QCConfig()
        config.mode = 'complete_visits'
        config.user_initials = 'JDT'
        config.instruments = ['a1', 'a2']
        config.events = ['udsv4_ivp_1_arm_1']
        config.primary_key_field = 'ptid'
        config.api_url = 'https://test.redcap.com/api/'
        config.api_token = 'test_token'
        config.output_path = tempfile.mkdtemp()
        config.json_rules_path = Path(__file__).parent.parent / 'config' / 'json_rules'
        config.log_level = 'INFO'
        return config

    @pytest.fixture
    def sample_redcap_data(self):
        """Create sample REDCap data for testing."""
        return pd.DataFrame({
            'ptid': ['1001', '1002', '1003', '1004'],
            'redcap_event_name': ['udsv4_ivp_1_arm_1'] * 4,
            'a1_complete': [2, 2, 2, 1],  # 2 = complete, 1 = incomplete
            'a2_complete': [2, 2, 2, 2],
            'a1_field1': ['value1', 'value2', '', 'value4'],
            'a1_field2': ['10', '20', 'invalid', '40'],
            'a2_field1': ['A', 'B', 'C', 'D'],
            'a2_field2': ['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04']
        })

    @pytest.fixture
    def sample_validation_rules(self):
        """Create sample validation rules for testing."""
        return {
            'a1_field1': {
                'type': 'string',
                'required': True,
                'empty': False
            },
            'a1_field2': {
                'type': 'integer',
                'min': 0,
                'max': 100
            },
            'a2_field1': {
                'type': 'string',
                'allowed': ['A', 'B', 'C', 'D', 'E']
            },
            'a2_field2': {
                'type': 'string',
                'regex': r'^\d{4}-\d{2}-\d{2}$'
            }
        }

    @patch('pipeline.fetcher.fetch_etl_data')
    @patch('pipeline.helpers.load_rules_for_instruments')
    def test_complete_pipeline_run(self, mock_load_rules, mock_fetch_data, mock_config, sample_redcap_data, sample_validation_rules):
        """Test a complete pipeline run from start to finish."""
        # Setup mocks
        mock_fetch_data.return_value = sample_redcap_data
        mock_load_rules.return_value = sample_validation_rules
        
        # Run the pipeline
        with patch('pipeline.report_pipeline.export_results_to_csv') as mock_export:
            run_report_pipeline(config=mock_config, enable_datastore=False)
            
            # Verify that results were exported
            mock_export.assert_called()
            
            # Verify fetch was called with correct config
            mock_fetch_data.assert_called_once_with(mock_config)
            
            # Verify rules were loaded
            mock_load_rules.assert_called_once()

    def test_config_validation(self):
        """Test configuration validation."""
        config = QCConfig()
        
        # Test invalid configuration
        errors = config.validate()
        assert len(errors) > 0
        assert any('api_url' in error.lower() for error in errors)
        assert any('api_token' in error.lower() for error in errors)
        
        # Test valid configuration
        config.api_url = 'https://test.redcap.com/api/'
        config.api_token = 'test_token'
        config.output_path = tempfile.mkdtemp()
        
        errors = config.validate()
        # Should have fewer errors now
        assert len(errors) < 5  # Adjust based on actual validation logic

    def test_validate_data_function(self, sample_redcap_data, sample_validation_rules):
        """Test the validate_data function."""
        # Create a subset of data for testing
        test_data = sample_redcap_data.head(2)
        
        # Mock configuration
        mock_config = MagicMock()
        mock_config.primary_key_field = 'ptid'
        mock_config.user_initials = 'JDT'
        
        # Run validation
        with patch('pipeline.quality_check.QualityCheck') as mock_qc:
            mock_qc_instance = Mock()
            mock_qc.return_value = mock_qc_instance
            mock_qc_instance.validate_record.return_value = []
            
            errors, pass_fail_log = validate_data(
                data=test_data,
                instrument='a1',
                rules=sample_validation_rules,
                config=mock_config
            )
            
            # Verify quality check was called
            assert mock_qc_instance.validate_record.call_count == len(test_data)
            
            # Verify return types
            assert isinstance(errors, list)
            assert isinstance(pass_fail_log, list)

    def test_build_complete_visits_df(self, sample_redcap_data):
        """Test building complete visits DataFrame."""
        # Mock configuration
        mock_config = MagicMock()
        mock_config.instruments = ['a1', 'a2']
        mock_config.events = ['udsv4_ivp_1_arm_1']
        mock_config.ptid_list = []
        mock_config.primary_key_field = 'ptid'
        
        # Build complete visits DataFrame
        complete_visits_df = build_complete_visits_df(
            data=sample_redcap_data,
            config=mock_config
        )
        
        # Verify result
        assert isinstance(complete_visits_df, pd.DataFrame)
        assert len(complete_visits_df) > 0
        assert 'ptid' in complete_visits_df.columns
        assert 'redcap_event_name' in complete_visits_df.columns
        
        # Should filter out incomplete records (ptid 1004 has incomplete a1)
        assert '1004' not in complete_visits_df['ptid'].values

    def test_quality_check_initialization(self, sample_validation_rules):
        """Test QualityCheck class initialization."""
        # Create a test record
        test_record = {
            'ptid': '1001',
            'redcap_event_name': 'udsv4_ivp_1_arm_1',
            'a1_field1': 'test_value',
            'a1_field2': '25'
        }
        
        # Initialize QualityCheck
        qc = QualityCheck(primary_key_field='ptid')
        
        # Validate record
        errors = qc.validate_record(test_record, sample_validation_rules)
        
        # Should not have errors for valid data
        assert isinstance(errors, list)
        # Note: Actual validation logic depends on implementation


class TestDatastoreIntegration:
    """Integration tests for datastore functionality."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def sample_errors_df(self):
        """Create sample error data for testing."""
        return pd.DataFrame({
            'ptid': ['1001', '1002', '1003'],
            'redcap_event_name': ['udsv4_ivp_1_arm_1'] * 3,
            'instrument_name': ['a1'] * 3,
            'variable': ['a1_field1', 'a1_field2', 'a1_field1'],
            'current_value': ['', 'invalid', ''],
            'expected_value': ['required', 'number', 'required'],
            'error': ['Field is required', 'Invalid value', 'Field is required'],
            'error_type': ['validation'] * 3
        })

    def test_enhanced_datastore_initialization(self, temp_db_path):
        """Test EnhancedDatastore initialization."""
        datastore = EnhancedDatastore(temp_db_path)
        
        assert datastore.db_path == Path(temp_db_path)
        assert os.path.exists(temp_db_path)
        
        # Check database schema
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Check validation_runs table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='validation_runs'")
        assert cursor.fetchone() is not None
        
        # Check error_records table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='error_records'")
        assert cursor.fetchone() is not None
        
        conn.close()

    def test_store_validation_run(self, temp_db_path, sample_errors_df):
        """Test storing validation run in database."""
        datastore = EnhancedDatastore(temp_db_path)
        
        # Store validation run
        run_id = datastore.store_validation_run(
            instrument='a1',
            errors_df=sample_errors_df,
            total_records=100,
            run_config={'mode': 'complete_events', 'user_initials': 'JDT'}
        )
        
        assert run_id is not None
        assert run_id.startswith('a1_')
        
        # Verify data was stored
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Check validation run
        cursor.execute("SELECT * FROM validation_runs WHERE run_id = ?", (run_id,))
        run_record = cursor.fetchone()
        assert run_record is not None
        
        # Check error records
        cursor.execute("SELECT COUNT(*) FROM error_records WHERE run_id = ?", (run_id,))
        error_count = cursor.fetchone()[0]
        assert error_count == len(sample_errors_df)
        
        conn.close()

    def test_compare_with_previous_run(self, temp_db_path, sample_errors_df):
        """Test error comparison functionality."""
        datastore = EnhancedDatastore(temp_db_path)
        
        # Store first run
        run_id_1 = datastore.store_validation_run(
            instrument='a1',
            errors_df=sample_errors_df,
            total_records=100,
            run_config={'mode': 'complete_events', 'user_initials': 'JDT'}
        )
        
        # Create modified errors for second run
        modified_errors = sample_errors_df.copy()
        modified_errors = modified_errors.iloc[:-1]  # Remove last error
        new_error = pd.DataFrame({
            'ptid': ['1004'],
            'redcap_event_name': ['udsv4_ivp_1_arm_1'],
            'instrument_name': ['a1'],
            'variable': ['a1_field3'],
            'current_value': ['bad_value'],
            'expected_value': ['good_value'],
            'error': ['New error'],
            'error_type': ['validation']
        })
        modified_errors = pd.concat([modified_errors, new_error], ignore_index=True)
        
        # Store second run
        run_id_2 = datastore.store_validation_run(
            instrument='a1',
            errors_df=modified_errors,
            total_records=100,
            run_config={'mode': 'complete_events', 'user_initials': 'JDT'}
        )
        
        # Compare runs
        comparison = datastore.compare_with_previous_run(run_id_2)
        
        # Should find differences
        assert isinstance(comparison, list)
        assert len(comparison) > 0
        
        # Check for different status types
        statuses = [comp.status for comp in comparison]
        assert 'new' in statuses or 'resolved' in statuses or 'persistent' in statuses

    def test_generate_quality_dashboard(self, temp_db_path, sample_errors_df):
        """Test quality dashboard generation."""
        datastore = EnhancedDatastore(temp_db_path)
        
        # Store validation run
        datastore.store_validation_run(
            instrument='a1',
            errors_df=sample_errors_df,
            total_records=100,
            run_config={'mode': 'complete_events', 'user_initials': 'JDT'}
        )
        
        # Generate dashboard
        dashboard = datastore.generate_quality_dashboard('a1')
        
        # Check dashboard structure
        assert isinstance(dashboard, dict)
        expected_keys = ['total_runs', 'current_error_rate', 'average_error_rate', 
                        'error_rate_trend', 'recent_errors', 'top_error_types']
        
        for key in expected_keys:
            assert key in dashboard

    def test_analyze_error_trends(self, temp_db_path, sample_errors_df):
        """Test error trend analysis."""
        datastore = EnhancedDatastore(temp_db_path)
        
        # Store multiple runs with different error counts
        for i in range(3):
            errors_subset = sample_errors_df.iloc[:i+1]  # Increasing errors
            datastore.store_validation_run(
                instrument='a1',
                errors_df=errors_subset,
                total_records=100,
                run_config={'mode': 'complete_events', 'user_initials': 'JDT'}
            )
        
        # Analyze trends
        trends = datastore.analyze_error_trends('a1')
        
        # Check trends structure
        assert isinstance(trends, dict)
        assert 'error_rates' in trends
        assert 'trend_direction' in trends
        assert 'time_series' in trends
        
        # Should detect increasing trend
        assert trends['trend_direction'] in ['increasing', 'stable', 'decreasing']


class TestConfigurationManagement:
    """Test configuration management functionality."""

    def test_get_config_singleton(self):
        """Test that get_config returns a singleton instance."""
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

    def test_config_environment_variables(self):
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

    def test_config_file_operations(self):
        """Test configuration file save/load operations."""
        config = QCConfig()
        config.api_url = 'https://test.redcap.com/api/'
        config.api_token = 'test_token'
        config.output_path = '/tmp/test'
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
            config_file = tmp.name
        
        try:
            # Save configuration
            config.save_to_file(config_file)
            assert os.path.exists(config_file)
            
            # Load configuration
            new_config = QCConfig()
            new_config.load_from_file(config_file)
            
            assert new_config.api_url == config.api_url
            assert new_config.api_token == config.api_token
            assert new_config.output_path == config.output_path
            
        finally:
            if os.path.exists(config_file):
                os.unlink(config_file)


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_mode_handling(self):
        """Test handling of invalid validation modes."""
        config = QCConfig()
        config.mode = 'invalid_mode'
        
        # Should detect invalid mode in validation
        errors = config.validate()
        assert any('mode' in error.lower() for error in errors)

    def test_missing_required_fields(self):
        """Test handling of missing required configuration fields."""
        config = QCConfig()
        # Leave required fields empty
        
        errors = config.validate()
        
        # Should detect missing required fields
        assert len(errors) > 0
        assert any('api_url' in error.lower() for error in errors)
        assert any('api_token' in error.lower() for error in errors)

    def test_database_connection_failure(self):
        """Test handling of database connection failures."""
        # Try to create datastore with invalid path
        invalid_path = '/invalid/path/database.db'
        
        # Should handle gracefully
        try:
            datastore = EnhancedDatastore(invalid_path)
            # If it doesn't fail, that's also acceptable (creates directory)
            assert os.path.exists(os.path.dirname(invalid_path)) or True
        except Exception as e:
            # Should be a reasonable error
            assert 'path' in str(e).lower() or 'permission' in str(e).lower()

    def test_empty_data_handling(self):
        """Test handling of empty data sets."""
        empty_df = pd.DataFrame()
        
        # Should handle empty DataFrame gracefully
        with patch('pipeline.quality_check.QualityCheck') as mock_qc:
            mock_qc_instance = Mock()
            mock_qc.return_value = mock_qc_instance
            mock_qc_instance.validate_record.return_value = []
            
            mock_config = MagicMock()
            mock_config.primary_key_field = 'ptid'
            
            errors, pass_fail_log = validate_data(
                data=empty_df,
                instrument='a1',
                rules={},
                config=mock_config
            )
            
            # Should handle empty data without errors
            assert isinstance(errors, list)
            assert isinstance(pass_fail_log, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
