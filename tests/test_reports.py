"""
Tests for the reports module - ReportFactory and unified report generation.
"""

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from tempfile import TemporaryDirectory

from src.pipeline.reports import (
    ReportFactory,
    ReportMetadata,
    create_legacy_export_results_to_csv
)
from src.pipeline.context import ProcessingContext, ExportConfiguration, ReportConfiguration


class TestReportMetadata:
    """Test ReportMetadata dataclass."""
    
    def test_report_metadata_creation(self):
        """Test creating report metadata."""
        from datetime import datetime
        
        metadata = ReportMetadata(
            report_type="error_dataset",
            filename="test_errors.csv",
            rows_exported=100,
            file_size_mb=0.5,
            export_timestamp=datetime.now()
        )
        
        assert metadata.report_type == "error_dataset"
        assert metadata.filename == "test_errors.csv"
        assert metadata.rows_exported == 100
        assert metadata.file_size_mb == 0.5


class TestReportFactory:
    """Test ReportFactory functionality."""
    
    @pytest.fixture
    def processing_context(self):
        """Mock processing context for testing."""
        return Mock(spec=ProcessingContext)
    
    @pytest.fixture
    def export_config(self):
        """Export configuration for testing."""
        with TemporaryDirectory() as tmp_dir:
            yield ExportConfiguration(
                output_dir=Path(tmp_dir),
                date_tag="20250826",
                time_tag="120000",
                include_logs=True,
                include_passed=True
            )
    
    @pytest.fixture
    def report_config(self):
        """Report configuration for testing."""
        return ReportConfiguration(
            qc_run_by="test_user",
            primary_key_field="ptid",
            instruments=['a1', 'a2']
        )
    
    @pytest.fixture
    def sample_error_data(self):
        """Sample error DataFrame."""
        return pd.DataFrame({
            'ptid': ['001', '002', '003'],
            'redcap_event_name': ['v1', 'v1', 'v2'],
            'instrument': ['a1', 'a2', 'a1'],
            'field': ['var1', 'var2', 'var1'],
            'error_message': ['Error 1', 'Error 2', 'Error 3']
        })
    
    @pytest.fixture
    def sample_logs_data(self):
        """Sample logs DataFrame."""
        return pd.DataFrame({
            'ptid': ['001', '002'],
            'redcap_event_name': ['v1', 'v1'],
            'instrument': ['a1', 'a2'],
            'validation_status': ['pass', 'fail'],
            'timestamp': ['2025-08-26 12:00:00', '2025-08-26 12:01:00']
        })
    
    @pytest.fixture
    def sample_all_records(self):
        """Sample all records DataFrame."""
        return pd.DataFrame({
            'ptid': ['001', '002', '003'],
            'redcap_event_name': ['v1', 'v1', 'v2']
        })
    
    def test_factory_initialization(self, processing_context):
        """Test factory initialization."""
        factory = ReportFactory(processing_context)
        
        assert factory.context == processing_context
        assert factory._generated_reports == []
    
    def test_generate_error_report_success(self, processing_context, export_config, sample_error_data):
        """Test successful error report generation."""
        factory = ReportFactory(processing_context)
        
        result_path = factory.generate_error_report(sample_error_data, export_config)
        
        assert result_path is not None
        assert result_path.exists()
        assert result_path.name.startswith("qc_errors_dataset_")
        assert result_path.suffix == ".csv"
        
        # Check metadata tracking
        assert len(factory._generated_reports) == 1
        metadata = factory._generated_reports[0]
        assert metadata.report_type == "error_dataset"
        assert metadata.rows_exported == 3
    
    def test_generate_error_report_empty_data(self, processing_context, export_config):
        """Test error report generation with empty data."""
        factory = ReportFactory(processing_context)
        empty_df = pd.DataFrame()
        
        result_path = factory.generate_error_report(empty_df, export_config)
        
        assert result_path is None
        assert len(factory._generated_reports) == 0
    
    def test_generate_validation_logs_report(self, processing_context, export_config, sample_logs_data):
        """Test validation logs report generation."""
        factory = ReportFactory(processing_context)
        
        result_path = factory.generate_validation_logs_report(sample_logs_data, export_config)
        
        assert result_path is not None
        assert result_path.exists()
        assert "validation_logs" in result_path.name
        
        # Verify content
        generated_df = pd.read_csv(result_path)
        assert len(generated_df) == 2
        assert list(generated_df.columns) == list(sample_logs_data.columns)
    
    def test_generate_passed_validations_report_disabled(self, processing_context, sample_logs_data):
        """Test passed validations report when disabled."""
        export_config = ExportConfiguration(
            output_dir=Path("/tmp"),
            date_tag="20250826",
            time_tag="120000",
            include_passed=False  # Disabled
        )
        
        factory = ReportFactory(processing_context)
        result_path = factory.generate_passed_validations_report(sample_logs_data, export_config)
        
        assert result_path is None
    
    def test_generate_aggregate_error_report(self, processing_context, export_config, 
                                           report_config, sample_error_data, sample_all_records):
        """Test aggregate error report generation."""
        processing_context.instrument_list = ['a1', 'a2']
        factory = ReportFactory(processing_context)
        
        result_path = factory.generate_aggregate_error_report(
            sample_error_data, sample_all_records, export_config, report_config
        )
        
        assert result_path is not None
        assert result_path.exists()
        assert "aggregate_error_counts" in result_path.name
        
        # Verify aggregate data
        generated_df = pd.read_csv(result_path)
        assert len(generated_df) == 3  # 3 unique ptid/event combinations
        assert 'error_count' in generated_df.columns
        assert 'total_instruments' in generated_df.columns
        assert generated_df['total_instruments'].iloc[0] == 2
    
    def test_generate_status_report(self, processing_context, export_config, report_config, 
                                  sample_all_records):
        """Test status report generation."""
        processing_context.instrument_list = ['a1', 'a2']
        factory = ReportFactory(processing_context)
        
        complete_visits_df = pd.DataFrame({'ptid': ['001'], 'redcap_event_name': ['v1']})
        validation_logs_df = pd.DataFrame({'log_entry': ['test']})
        
        result_path = factory.generate_status_report(
            sample_all_records, complete_visits_df, validation_logs_df,
            export_config, report_config
        )
        
        assert result_path is not None
        assert result_path.exists()
        assert "tool_status" in result_path.name
        
        # Verify status metrics
        generated_df = pd.read_csv(result_path)
        metrics = generated_df['metric'].tolist()
        assert 'total_records_processed' in metrics
        assert 'complete_visits_found' in metrics
        assert 'instruments_validated' in metrics
    
    def test_export_all_reports(self, processing_context, export_config, report_config,
                               sample_error_data, sample_logs_data, sample_all_records):
        """Test exporting all reports together."""
        processing_context.instrument_list = ['a1', 'a2']
        factory = ReportFactory(processing_context)
        
        df_passed = pd.DataFrame({'validation': ['passed']})
        complete_visits_df = pd.DataFrame({'ptid': ['001'], 'redcap_event_name': ['v1']})
        validation_logs_df = pd.DataFrame({'log_entry': ['test']})
        
        generated_files = factory.export_all_reports(
            sample_error_data, sample_logs_data, df_passed, sample_all_records,
            complete_visits_df, validation_logs_df, export_config, report_config
        )
        
        # Should generate 5 reports: errors, logs, passed, aggregate, status
        assert len(generated_files) == 5
        
        # All files should exist
        for file_path in generated_files:
            assert file_path.exists()
        
        # Check that metadata was tracked
        assert len(factory._generated_reports) == 5
        
        # Verify generation summary was created
        summary_file = export_config.output_dir / f"qc_generation_summary_{export_config.date_tag}_{export_config.time_tag}.csv"
        assert summary_file.exists()
    
    def test_get_report_statistics(self, processing_context, export_config, sample_error_data):
        """Test getting report statistics."""
        factory = ReportFactory(processing_context)
        
        # Initially no reports
        stats = factory.get_report_statistics()
        assert stats['total_reports'] == 0
        assert stats['total_rows'] == 0
        
        # Generate a report
        factory.generate_error_report(sample_error_data, export_config)
        
        # Check updated statistics
        stats = factory.get_report_statistics()
        assert stats['total_reports'] == 1
        assert stats['total_rows'] == 3
        assert 'error_dataset' in stats['report_types']
    
    def test_directory_creation(self, processing_context, export_config, sample_error_data):
        """Test that required directories are created automatically."""
        factory = ReportFactory(processing_context)
        
        # Generate report in subdirectory
        result_path = factory.generate_error_report(sample_error_data, export_config)
        
        # Verify path and parent directory were created
        assert result_path is not None
        assert result_path.exists()
        assert result_path.parent.exists()
        assert result_path.parent.name == "error_reports"


class TestLegacyCompatibility:
    """Test legacy compatibility functions."""
    
    @pytest.fixture
    def mock_processing_context(self):
        """Mock processing context."""
        context = Mock()
        context.instrument_list = ['a1', 'a2']
        return context
    
    @pytest.fixture
    def mock_report_config(self):
        """Mock report configuration."""
        config = Mock(spec=ReportConfiguration)
        config.primary_key_field = 'ptid'
        config.qc_run_by = 'test_user'
        return config
    
    def test_create_legacy_export_results_to_csv(self, mock_processing_context, mock_report_config):
        """Test legacy compatibility wrapper."""
        with TemporaryDirectory() as tmp_dir:
            # Create sample data with required columns
            df_errors = pd.DataFrame({
                'ptid': ['001'],
                'redcap_event_name': ['v1'],
                'error': ['test']
            })
            df_logs = pd.DataFrame({'log': ['test']})
            df_passed = pd.DataFrame({'passed': ['test']})
            all_records_df = pd.DataFrame({
                'ptid': ['001'],
                'redcap_event_name': ['v1']
            })
            complete_visits_df = pd.DataFrame({'visit': ['test']})
            detailed_logs_df = pd.DataFrame({'detail': ['test']})
            
            # Test legacy function
            result_paths = create_legacy_export_results_to_csv(
                df_errors, df_logs, df_passed, all_records_df,
                complete_visits_df, detailed_logs_df,
                Path(tmp_dir), "20250826", "120000",
                mock_processing_context, mock_report_config
            )
            
            # Should return list of paths
            assert isinstance(result_paths, list)
            # At minimum should have aggregate and status reports
            assert len(result_paths) >= 2
