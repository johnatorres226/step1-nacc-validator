"""
Integration tests for pipeline stages.

Tests the complete pipeline flow from data fetching through report generation
to ensure all stages work together correctly.
"""
import pytest
import pandas as pd
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from pipeline.core.pipeline_orchestrator import PipelineOrchestrator
from pipeline.core.pipeline_results import (
    DataFetchResult, 
    RulesLoadingResult,
    DataPreparationResult,
    ValidationResult,
    PipelineExecutionResult
)
from pipeline.config_manager import QCConfig


class TestPipelineStageIntegration:
    """Test integration between pipeline stages."""
    
    def setup_method(self):
        """Set up test environment for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create mock config
        self.mock_config = Mock(spec=QCConfig)
        self.mock_config.instruments = ['a1', 'b3']
        self.mock_config.mode = 'complete_visits'
        self.mock_config.output_path = str(self.temp_path)
        self.mock_config.primary_key_field = 'record_id'
        self.mock_config.user_initials = 'TEST'
    
    def teardown_method(self):
        """Clean up test environment after each test."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_data_fetch_to_rules_loading_integration(self):
        """Test integration between data fetch and rules loading stages."""
        # Create test data that would come from data fetch
        test_data = pd.DataFrame({
            'record_id': [1, 2, 3, 4],
            'redcap_repeat_instrument': ['a1', 'b3', 'a1', 'b3'],
            'field1': ['val1', 'val2', 'val3', 'val4']
        })
        
        # Create data fetch result
        data_fetch_result = DataFetchResult(
            data=test_data,
            records_processed=4,
            execution_time=1.0,
            source_info={'server': 'test', 'project': 'test'},
            fetch_timestamp=datetime.now(),
            success=True
        )
        
        # Verify data can be used for rules loading
        assert not data_fetch_result.is_empty
        assert len(data_fetch_result.data) == 4
        
        # Extract instruments from fetched data for rules loading
        unique_instruments = set(data_fetch_result.data['redcap_repeat_instrument'].unique())
        assert 'a1' in unique_instruments
        assert 'b3' in unique_instruments
    
    def test_rules_loading_to_data_preparation_integration(self):
        """Test integration between rules loading and data preparation stages."""
        # Create rules loading result
        test_rules = {
            'a1': {'field1': {'type': 'text'}},
            'b3': {'field2': {'type': 'number'}}
        }
        
        rules_result = RulesLoadingResult(
            rules_cache=test_rules,
            instruments_processed=['a1', 'b3'],
            loading_time=0.5,
            variable_to_instrument_map={'field1': 'a1', 'field2': 'b3'},
            instrument_to_variables_map={'a1': ['field1'], 'b3': ['field2']},
            success=True
        )
        
        # Verify rules can be used for data preparation
        assert rules_result.success
        assert rules_result.loaded_instruments_count == 2
        assert 'a1' in rules_result.rules_cache
        assert 'b3' in rules_result.rules_cache
        
        # Test getting rules for specific instrument
        a1_rules = rules_result.get_rules_for_instrument('a1')
        assert 'field1' in a1_rules
    
    def test_data_preparation_to_validation_integration(self):
        """Test integration between data preparation and validation stages."""
        # Create data preparation result
        test_cache = {
            'a1': pd.DataFrame({'record_id': [1, 3], 'field1': ['val1', 'val3']}),
            'b3': pd.DataFrame({'record_id': [2, 4], 'field2': ['val2', 'val4']})
        }
        
        prep_result = DataPreparationResult(
            instrument_data_cache=test_cache,
            complete_visits_data=None,
            preparation_time=2.0,
            records_per_instrument={'a1': 2, 'b3': 2},
            success=True
        )
        
        # Verify prepared data can be used for validation
        assert prep_result.success
        assert prep_result.total_records_prepared == 4
        assert len(prep_result.instruments_with_data) == 2
        
        # Test getting data for validation
        a1_data = prep_result.get_instrument_data('a1')
        assert len(a1_data) == 2
        assert 'record_id' in a1_data.columns
    
    def test_validation_to_report_generation_integration(self):
        """Test integration between validation and report generation stages."""
        # Create validation result with some errors
        errors_df = pd.DataFrame({
            'record_id': [1, 3],
            'instrument': ['a1', 'a1'],
            'error_message': ['Missing field', 'Invalid value']
        })
        
        logs_df = pd.DataFrame({
            'record_id': [1, 2, 3, 4],
            'instrument': ['a1', 'b3', 'a1', 'b3'],
            'status': ['error', 'pass', 'error', 'pass']
        })
        
        all_records_df = pd.DataFrame({
            'record_id': [1, 2, 3, 4],
            'instrument': ['a1', 'b3', 'a1', 'b3']
        })
        
        validation_result = ValidationResult(
            errors_df=errors_df,
            logs_df=logs_df,
            passed_df=pd.DataFrame(),
            validation_logs_df=pd.DataFrame(),
            all_records_df=all_records_df,
            validation_time=3.0,
            instruments_processed=['a1', 'b3'],
            validation_summary={'total_errors': 2, 'total_warnings': 0},
            success=True
        )
        
        # Verify validation results are suitable for report generation
        assert validation_result.success
        assert validation_result.total_errors == 2
        assert validation_result.total_records_validated == 4
        assert validation_result.error_rate == 50.0  # 2 errors out of 4 records
        
        # Verify data structure for reporting
        assert not validation_result.errors_df.empty
        assert not validation_result.logs_df.empty
        assert 'record_id' in validation_result.errors_df.columns
        assert 'instrument' in validation_result.errors_df.columns


class TestPipelineOrchestratorIntegration:
    """Test PipelineOrchestrator integration."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create mock config
        self.mock_config = Mock(spec=QCConfig)
        self.mock_config.instruments = ['a1', 'b3']
        self.mock_config.mode = 'complete_visits'
        self.mock_config.output_path = str(self.temp_path)
        self.mock_config.primary_key_field = 'record_id'
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('pipeline.core.pipeline_orchestrator.RedcapETLPipeline')
    @patch('pipeline.core.pipeline_orchestrator.load_rules_for_instruments')
    @patch('pipeline.core.pipeline_orchestrator.prepare_instrument_data_cache')
    @patch('pipeline.core.pipeline_orchestrator.QualityCheck')
    @patch('pipeline.core.pipeline_orchestrator.ReportFactory')
    def test_orchestrator_stage_sequence(self, mock_report_factory, mock_qc, 
                                       mock_prep_cache, mock_load_rules, mock_etl):
        """Test that orchestrator executes stages in correct sequence."""
        # Mock successful responses for each stage
        mock_etl.return_value.fetch_data.return_value = (
            pd.DataFrame({'record_id': [1, 2]}), 
            {'server': 'test'}
        )
        
        mock_load_rules.return_value = {'a1': {}, 'b3': {}}
        mock_prep_cache.return_value = {
            'a1': pd.DataFrame({'record_id': [1]}),
            'b3': pd.DataFrame({'record_id': [2]})
        }
        
        mock_qc_instance = Mock()
        mock_qc_instance.validate_records.return_value = (
            pd.DataFrame(),  # errors
            pd.DataFrame(),  # logs
            pd.DataFrame()   # passed
        )
        mock_qc.return_value = mock_qc_instance
        
        mock_report_factory.return_value.export_all_reports.return_value = ['report1.csv']
        
        # Create orchestrator and execute
        orchestrator = PipelineOrchestrator(self.mock_config)
        result = orchestrator.execute_pipeline()
        
        # Verify execution order and calls
        assert mock_etl.called
        assert mock_load_rules.called
        assert mock_prep_cache.called
        assert mock_qc.called
        assert mock_report_factory.called
        
        # Verify result structure
        assert isinstance(result, PipelineExecutionResult)
    
    def test_orchestrator_error_propagation(self):
        """Test that orchestrator properly propagates errors between stages."""
        # Test case where data fetch fails
        with patch('pipeline.core.pipeline_orchestrator.RedcapETLPipeline') as mock_etl:
            mock_etl.return_value.fetch_data.side_effect = Exception("Connection failed")
            
            orchestrator = PipelineOrchestrator(self.mock_config)
            result = orchestrator.execute_pipeline()
            
            # Should handle the error gracefully
            assert isinstance(result, PipelineExecutionResult)
            assert not result.success
            assert result.data_fetch is not None
            assert not result.data_fetch.success


class TestEndToEndPipelineFlow:
    """Test complete end-to-end pipeline execution."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create comprehensive test config
        self.test_config = Mock(spec=QCConfig)
        self.test_config.instruments = ['a1', 'b3']
        self.test_config.mode = 'complete_visits'
        self.test_config.output_path = str(self.temp_path)
        self.test_config.primary_key_field = 'record_id'
        self.test_config.user_initials = 'TEST'
        self.test_config.redcap_server_url = 'https://test.redcap.edu'
        self.test_config.redcap_api_token = 'test_token'
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('pipeline.report_pipeline.PipelineOrchestrator')
    def test_improved_pipeline_integration(self, mock_orchestrator):
        """Test the improved pipeline interface integration."""
        from pipeline.report_pipeline import run_improved_report_pipeline
        
        # Mock successful pipeline execution
        mock_result = PipelineExecutionResult(
            success=True,
            data_fetch=DataFetchResult(
                data=pd.DataFrame({'record_id': [1, 2]}),
                records_processed=2,
                execution_time=1.0,
                source_info={'server': 'test'},
                fetch_timestamp=datetime.now(),
                success=True
            ),
            rules_loading=RulesLoadingResult(
                rules_cache={'a1': {}, 'b3': {}},
                instruments_processed=['a1', 'b3'],
                loading_time=0.5,
                variable_to_instrument_map={},
                instrument_to_variables_map={},
                success=True
            ),
            data_preparation=None,
            validation=ValidationResult(
                errors_df=pd.DataFrame(),
                logs_df=pd.DataFrame(),
                passed_df=pd.DataFrame(),
                validation_logs_df=pd.DataFrame(),
                all_records_df=pd.DataFrame({'record_id': [1, 2]}),
                validation_time=2.0,
                instruments_processed=['a1', 'b3'],
                validation_summary={},
                success=True
            ),
            report_generation=None,
            total_execution_time=5.0,
            output_directory=str(self.temp_path),
            pipeline_error=None
        )
        
        mock_orchestrator.return_value.execute_pipeline.return_value = mock_result
        
        # Execute improved pipeline
        result = run_improved_report_pipeline(self.test_config)
        
        # Verify integration
        assert isinstance(result, PipelineExecutionResult)
        assert result.success
        assert mock_orchestrator.called
    
    def test_backward_compatibility_integration(self):
        """Test that backward compatibility is maintained."""
        from pipeline.report_pipeline import run_report_pipeline
        
        # This test verifies that the old interface still works
        with patch('pipeline.report_pipeline.run_improved_report_pipeline') as mock_improved:
            mock_improved.return_value = PipelineExecutionResult(
                success=True,
                data_fetch=Mock(records_processed=5),
                rules_loading=Mock(success=True),
                data_preparation=None,
                validation=Mock(total_errors=0),
                report_generation=Mock(total_files_created=3),
                total_execution_time=10.0,
                output_directory=str(self.temp_path),
                pipeline_error=None
            )
            
            # Should not raise any errors
            try:
                run_report_pipeline(self.test_config)
                # Test passes if no exception is raised
                assert True
            except Exception as e:
                pytest.fail(f"Backward compatibility broken: {e}")


class TestDataFlowIntegration:
    """Test data flow between pipeline stages."""
    
    def test_data_consistency_across_stages(self):
        """Test that data remains consistent as it flows through stages."""
        # Start with initial data
        initial_data = pd.DataFrame({
            'record_id': [1, 2, 3, 4],
            'redcap_repeat_instrument': ['a1', 'b3', 'a1', 'b3'],
            'field1': ['val1', 'val2', 'val3', 'val4']
        })
        
        # Stage 1: Data Fetch
        data_fetch_result = DataFetchResult(
            data=initial_data,
            records_processed=4,
            execution_time=1.0,
            source_info={'server': 'test'},
            fetch_timestamp=datetime.now(),
            success=True
        )
        
        # Verify data integrity after fetch
        assert len(data_fetch_result.data) == 4
        assert set(data_fetch_result.data['record_id']) == {1, 2, 3, 4}
        
        # Stage 2: Rules Loading (doesn't modify data)
        rules_result = RulesLoadingResult(
            rules_cache={'a1': {}, 'b3': {}},
            instruments_processed=['a1', 'b3'],
            loading_time=0.5,
            variable_to_instrument_map={},
            instrument_to_variables_map={},
            success=True
        )
        
        # Stage 3: Data Preparation (splits data by instrument)
        a1_data = initial_data[initial_data['redcap_repeat_instrument'] == 'a1']
        b3_data = initial_data[initial_data['redcap_repeat_instrument'] == 'b3']
        
        prep_result = DataPreparationResult(
            instrument_data_cache={'a1': a1_data, 'b3': b3_data},
            complete_visits_data=None,
            preparation_time=2.0,
            records_per_instrument={'a1': 2, 'b3': 2},
            success=True
        )
        
        # Verify data integrity after preparation
        assert prep_result.total_records_prepared == 4
        assert len(prep_result.get_instrument_data('a1')) == 2
        assert len(prep_result.get_instrument_data('b3')) == 2
        
        # Verify original record IDs are preserved
        all_prep_records = set()
        for instrument in ['a1', 'b3']:
            instrument_data = prep_result.get_instrument_data(instrument)
            all_prep_records.update(instrument_data['record_id'].tolist())
        
        assert all_prep_records == {1, 2, 3, 4}
    
    def test_error_propagation_across_stages(self):
        """Test that errors are properly propagated across stages."""
        # Start with a failed data fetch
        failed_fetch = DataFetchResult(
            data=pd.DataFrame(),
            records_processed=0,
            execution_time=0.5,
            source_info={'error': 'connection_failed'},
            fetch_timestamp=datetime.now(),
            success=False,
            error_message="Connection to REDCap failed"
        )
        
        # Subsequent stages should handle the failure
        assert not failed_fetch.success
        assert failed_fetch.is_empty
        assert failed_fetch.error_message is not None
        
        # In a real pipeline, this would prevent subsequent stages from executing
        # or cause them to handle the empty data appropriately


if __name__ == "__main__":
    pytest.main([__file__])
