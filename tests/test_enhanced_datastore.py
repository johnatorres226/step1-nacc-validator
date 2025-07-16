"""
Test suite for enhanced datastore functionality and database integration.
This test file covers the enhanced datastore features including error tracking,
trend analysis, and pattern detection.
"""

import pytest
import pandas as pd
import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timedelta

# Add src to path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pipeline.datastore import EnhancedDatastore, ErrorComparison
from pipeline.report_pipeline import (
    run_enhanced_report_pipeline,
    generate_datastore_analysis_report,
    get_datastore_path,
    _store_validation_in_database
)
from pipeline.config_manager import QCConfig


class TestEnhancedDatastore:
    """Test suite for the EnhancedDatastore class."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        yield db_path
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def enhanced_datastore(self, temp_db_path):
        """Create an EnhancedDatastore instance with temporary database."""
        return EnhancedDatastore(temp_db_path)

    @pytest.fixture
    def sample_error_data(self):
        """Sample error data for testing."""
        return pd.DataFrame({
            'ptid': ['1001', '1002', '1003'],
            'redcap_event_name': ['udsv4_ivp_1_arm_1', 'udsv4_ivp_1_arm_1', 'udsv4_ivp_1_arm_1'],
            'field_name': ['a1_field1', 'a1_field2', 'a1_field1'],
            'error_type': ['Missing', 'Invalid', 'Missing'],
            'error_message': ['Field is required', 'Invalid value', 'Field is required'],
            'field_value': ['', 'invalid', '']
        })

    @pytest.fixture
    def sample_run_data(self):
        """Sample run data for testing."""
        return {
            'run_id': 'a1_20250716_123456',
            'instrument': 'a1',
            'timestamp': datetime.now().isoformat(),
            'total_records': 100,
            'error_count': 5,
            'mode': 'complete_events',
            'user_initials': 'JDT'
        }

    def test_datastore_initialization(self, enhanced_datastore, temp_db_path):
        """Test datastore initialization and database creation."""
        assert enhanced_datastore.db_path == temp_db_path
        assert os.path.exists(temp_db_path)
        
        # Check that tables were created
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Check validation_runs table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='validation_runs'")
        assert cursor.fetchone() is not None
        
        # Check error_records table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='error_records'")
        assert cursor.fetchone() is not None
        
        conn.close()

    def test_store_validation_run(self, enhanced_datastore, sample_run_data, sample_error_data):
        """Test storing validation run data."""
        # Store run data
        enhanced_datastore.store_validation_run(sample_run_data, sample_error_data)
        
        # Verify run was stored
        conn = sqlite3.connect(enhanced_datastore.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM validation_runs WHERE run_id = ?", (sample_run_data['run_id'],))
        run_record = cursor.fetchone()
        assert run_record is not None
        assert run_record[1] == sample_run_data['instrument']
        assert run_record[3] == sample_run_data['total_records']
        assert run_record[4] == sample_run_data['error_count']
        
        # Verify errors were stored
        cursor.execute("SELECT COUNT(*) FROM error_records WHERE run_id = ?", (sample_run_data['run_id'],))
        error_count = cursor.fetchone()[0]
        assert error_count == len(sample_error_data)
        
        conn.close()

    def test_compare_with_previous_run(self, enhanced_datastore, sample_run_data, sample_error_data):
        """Test error comparison with previous runs."""
        # Store initial run
        enhanced_datastore.store_validation_run(sample_run_data, sample_error_data)
        
        # Create second run with some different errors
        new_run_data = sample_run_data.copy()
        new_run_data['run_id'] = 'a1_20250716_234567'
        new_run_data['timestamp'] = (datetime.now() + timedelta(days=1)).isoformat()
        
        new_error_data = sample_error_data.copy()
        # Add a new error and remove one
        new_error_data = new_error_data.iloc[:-1]  # Remove last error
        new_error_data = pd.concat([new_error_data, pd.DataFrame({
            'ptid': ['1004'],
            'redcap_event_name': ['udsv4_ivp_1_arm_1'],
            'field_name': ['a1_field3'],
            'error_type': ['Invalid'],
            'error_message': ['New error'],
            'field_value': ['bad_value']
        })], ignore_index=True)
        
        # Store second run
        enhanced_datastore.store_validation_run(new_run_data, new_error_data)
        
        # Compare runs
        comparison = enhanced_datastore.compare_with_previous_run(new_run_data['run_id'])
        
        assert isinstance(comparison, ErrorComparison)
        assert len(comparison.new_errors) > 0
        assert len(comparison.resolved_errors) > 0
        assert len(comparison.persistent_errors) > 0

    def test_generate_quality_dashboard(self, enhanced_datastore, sample_run_data, sample_error_data):
        """Test quality dashboard generation."""
        # Store some run data
        enhanced_datastore.store_validation_run(sample_run_data, sample_error_data)
        
        # Generate dashboard
        dashboard = enhanced_datastore.generate_quality_dashboard(sample_run_data['instrument'])
        
        assert 'summary' in dashboard
        assert 'trends' in dashboard
        assert 'patterns' in dashboard
        assert 'recent_runs' in dashboard
        
        # Check summary data
        summary = dashboard['summary']
        assert 'total_runs' in summary
        assert 'current_error_rate' in summary
        assert 'average_error_rate' in summary

    def test_analyze_error_trends(self, enhanced_datastore, sample_run_data, sample_error_data):
        """Test error trend analysis."""
        # Store multiple runs with different timestamps
        for i in range(5):
            run_data = sample_run_data.copy()
            run_data['run_id'] = f"a1_20250716_{i:06d}"
            run_data['timestamp'] = (datetime.now() - timedelta(days=i)).isoformat()
            run_data['error_count'] = 5 - i  # Decreasing errors
            
            enhanced_datastore.store_validation_run(run_data, sample_error_data)
        
        # Analyze trends
        trends = enhanced_datastore.analyze_error_trends(sample_run_data['instrument'])
        
        assert 'error_rates' in trends
        assert 'trend_direction' in trends
        assert 'time_series' in trends

    def test_detect_error_patterns(self, enhanced_datastore, sample_run_data):
        """Test error pattern detection."""
        # Create error data with patterns
        pattern_errors = pd.DataFrame({
            'ptid': ['1001', '1001', '1002', '1002', '1003'],
            'redcap_event_name': ['udsv4_ivp_1_arm_1'] * 5,
            'field_name': ['a1_field1', 'a1_field1', 'a1_field1', 'a1_field2', 'a1_field1'],
            'error_type': ['Missing', 'Missing', 'Missing', 'Invalid', 'Missing'],
            'error_message': ['Field is required'] * 3 + ['Invalid value', 'Field is required'],
            'field_value': [''] * 3 + ['bad', '']
        })
        
        # Store run with pattern data
        enhanced_datastore.store_validation_run(sample_run_data, pattern_errors)
        
        # Detect patterns
        patterns = enhanced_datastore.detect_error_patterns(sample_run_data['instrument'])
        
        assert 'repeated_patterns' in patterns
        assert 'error_clusters' in patterns
        assert 'systematic_issues' in patterns


class TestDatastoreIntegration:
    """Test suite for datastore integration with the main pipeline."""

    @pytest.fixture
    def mock_config(self):
        """Mock QCConfig for testing."""
        config = MagicMock(spec=QCConfig)
        config.mode = 'complete_events'
        config.user_initials = 'JDT'
        config.instruments = ['a1', 'a2']
        config.output_path = '/tmp/test_output'
        config.validate.return_value = []
        return config

    @pytest.fixture
    def sample_validation_data(self):
        """Sample validation data for testing."""
        return pd.DataFrame({
            'ptid': ['1001', '1002', '1003'],
            'redcap_event_name': ['udsv4_ivp_1_arm_1'] * 3,
            'instrument_name': ['a1'] * 3,
            'field_name': ['a1_field1', 'a1_field2', 'a1_field1'],
            'error_type': ['Missing', 'Invalid', 'Missing'],
            'error_message': ['Field is required', 'Invalid value', 'Field is required'],
            'field_value': ['', 'invalid', '']
        })

    @patch('pipeline.report_pipeline.fetch_etl_data')
    @patch('pipeline.report_pipeline.process_instruments_etl')
    @patch('pipeline.report_pipeline.Path.mkdir')
    def test_run_enhanced_report_pipeline(self, mock_mkdir, mock_process, mock_fetch, mock_config):
        """Test enhanced report pipeline with datastore integration."""
        # Mock data
        mock_fetch.return_value = pd.DataFrame({'ptid': ['1001'], 'redcap_event_name': ['udsv4_ivp_1_arm_1']})
        mock_process.return_value = (
            pd.DataFrame({'ptid': ['1001']}),  # processed_records
            pd.DataFrame({'ptid': ['1001'], 'error': ['Test error']}),  # errors
            []  # pass_fail_log
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_config.output_path = tmp_dir
            
            # This should not raise an exception
            run_enhanced_report_pipeline(mock_config, enable_datastore=True)
            
            # Verify mocks were called
            mock_fetch.assert_called_once()
            mock_process.assert_called_once()

    def test_get_datastore_path(self):
        """Test datastore path resolution."""
        # Test with environment variable
        with patch.dict(os.environ, {'VALIDATION_HISTORY_DB_PATH': '/custom/path/db.db'}):
            path = get_datastore_path()
            assert path == '/custom/path/db.db'
        
        # Test with default path
        with patch.dict(os.environ, {}, clear=True):
            path = get_datastore_path()
            assert 'data/validation_history.db' in path

    def test_store_validation_in_database(self, sample_validation_data):
        """Test storing validation data in database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            # Store validation data
            _store_validation_in_database(
                df_errors=sample_validation_data,
                processed_records_count=100,
                config=MagicMock(mode='complete_events', user_initials='JDT'),
                instruments=['a1'],
                output_path='/tmp/test',
                datastore_path=db_path
            )
            
            # Verify data was stored
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM validation_runs")
            run_count = cursor.fetchone()[0]
            assert run_count > 0
            
            cursor.execute("SELECT COUNT(*) FROM error_records")
            error_count = cursor.fetchone()[0]
            assert error_count == len(sample_validation_data)
            
            conn.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_generate_datastore_analysis_report(self):
        """Test datastore analysis report generation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
                db_path = tmp_db.name
            
            try:
                # Create and populate test database
                datastore = EnhancedDatastore(db_path)
                sample_run = {
                    'run_id': 'a1_20250716_123456',
                    'instrument': 'a1',
                    'timestamp': datetime.now().isoformat(),
                    'total_records': 100,
                    'error_count': 5,
                    'mode': 'complete_events',
                    'user_initials': 'JDT'
                }
                sample_errors = pd.DataFrame({
                    'ptid': ['1001'],
                    'redcap_event_name': ['udsv4_ivp_1_arm_1'],
                    'field_name': ['a1_field1'],
                    'error_type': ['Missing'],
                    'error_message': ['Field is required'],
                    'field_value': ['']
                })
                datastore.store_validation_run(sample_run, sample_errors)
                
                # Generate analysis report
                report_path = generate_datastore_analysis_report(
                    instrument='a1',
                    output_path=tmp_dir,
                    datastore_path=db_path
                )
                
                # Verify report was created
                assert os.path.exists(report_path)
                assert report_path.endswith('.txt')
                
                # Check report content
                with open(report_path, 'r') as f:
                    content = f.read()
                    assert 'Datastore Analysis Report' in content
                    assert 'a1' in content
                    
            finally:
                if os.path.exists(db_path):
                    os.unlink(db_path)


class TestErrorComparison:
    """Test suite for ErrorComparison functionality."""

    def test_error_comparison_initialization(self):
        """Test ErrorComparison initialization."""
        comparison = ErrorComparison(
            new_errors=pd.DataFrame({'error': ['new']}),
            resolved_errors=pd.DataFrame({'error': ['resolved']}),
            persistent_errors=pd.DataFrame({'error': ['persistent']}),
            run_id='test_run',
            previous_run_id='prev_run'
        )
        
        assert len(comparison.new_errors) == 1
        assert len(comparison.resolved_errors) == 1
        assert len(comparison.persistent_errors) == 1
        assert comparison.run_id == 'test_run'
        assert comparison.previous_run_id == 'prev_run'

    def test_error_comparison_summary(self):
        """Test ErrorComparison summary generation."""
        comparison = ErrorComparison(
            new_errors=pd.DataFrame({'error': ['new1', 'new2']}),
            resolved_errors=pd.DataFrame({'error': ['resolved1']}),
            persistent_errors=pd.DataFrame({'error': ['persistent1', 'persistent2', 'persistent3']}),
            run_id='test_run',
            previous_run_id='prev_run'
        )
        
        summary = comparison.get_summary()
        
        assert summary['new_error_count'] == 2
        assert summary['resolved_error_count'] == 1
        assert summary['persistent_error_count'] == 3
        assert summary['total_changes'] == 3  # new + resolved


class TestDatabaseSchema:
    """Test suite for database schema validation."""

    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        yield db_path
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_database_schema_creation(self, temp_db_path):
        """Test that database schema is created correctly."""
        datastore = EnhancedDatastore(temp_db_path)
        
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Check validation_runs table structure
        cursor.execute("PRAGMA table_info(validation_runs)")
        columns = [row[1] for row in cursor.fetchall()]
        expected_columns = ['id', 'instrument', 'timestamp', 'total_records', 'error_count', 'mode', 'user_initials']
        for col in expected_columns:
            assert col in columns
        
        # Check error_records table structure
        cursor.execute("PRAGMA table_info(error_records)")
        columns = [row[1] for row in cursor.fetchall()]
        expected_columns = ['id', 'run_id', 'ptid', 'event_name', 'field_name', 'error_type', 'error_message', 'field_value']
        for col in expected_columns:
            assert col in columns
        
        conn.close()

    def test_database_constraints(self, temp_db_path):
        """Test database constraints and foreign keys."""
        datastore = EnhancedDatastore(temp_db_path)
        
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        # Test foreign key constraint
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Try to insert error record without corresponding run (should fail)
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO error_records (run_id, ptid, event_name, field_name, error_type, error_message, field_value)
                VALUES ('nonexistent_run', '1001', 'event', 'field', 'error', 'message', 'value')
            """)
        
        conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
