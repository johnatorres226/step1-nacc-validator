"""
Unit tests for pipeline result objects.

Tests all result dataclasses created in Task 3 to ensure proper validation,
error handling, and data integrity.
"""
import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import Mock

from pipeline.core.pipeline_results import (
    DataFetchResult,
    RulesLoadingResult, 
    DataPreparationResult,
    ValidationResult,
    PipelineStageError,
    DataFetchError,
    RulesLoadingError,
    DataPreparationError,
    ValidationError,
    ReportGenerationError
)


class TestDataFetchResult:
    """Test DataFetchResult dataclass."""
    
    def test_successful_data_fetch_result(self):
        """Test creating a successful data fetch result."""
        test_df = pd.DataFrame({'id': [1, 2, 3], 'value': ['a', 'b', 'c']})
        
        result = DataFetchResult(
            data=test_df,
            records_processed=3,
            execution_time=1.5,
            source_info={'server': 'redcap', 'project': 'test'},
            fetch_timestamp=datetime.now(),
            success=True,
            error_message=None
        )
        
        assert result.success is True
        assert len(result.data) == 3
        assert result.records_processed == 3
        assert result.execution_time == 1.5
        assert result.error_message is None
        assert result.is_empty is False
    
    def test_failed_data_fetch_result(self):
        """Test creating a failed data fetch result."""
        result = DataFetchResult(
            data=pd.DataFrame(),
            records_processed=0,
            execution_time=0.5,
            source_info={'server': 'redcap', 'error': 'connection_failed'},
            fetch_timestamp=datetime.now(),
            success=False,
            error_message="Connection failed"
        )
        
        assert result.success is False
        assert result.is_empty is True
        assert result.records_processed == 0
        assert result.error_message == "Connection failed"
    
    def test_data_fetch_validation(self):
        """Test data fetch result validation."""
        # Test invalid failed result (no error message)
        result = DataFetchResult(
            data=pd.DataFrame(),
            records_processed=0,
            execution_time=0.5,
            source_info={},
            fetch_timestamp=datetime.now(),
            success=False,
            error_message=None  # This should be invalid
        )
        
        with pytest.raises(ValueError, match="Failed fetch result must have error message"):
            result.validate()


class TestRulesLoadingResult:
    """Test RulesLoadingResult dataclass."""
    
    def test_successful_rules_loading(self):
        """Test successful rules loading result."""
        test_rules = {
            'instrument1': {'rule1': 'value1'},
            'instrument2': {'rule2': 'value2'}
        }
        
        result = RulesLoadingResult(
            rules_cache=test_rules,
            instruments_processed=['instrument1', 'instrument2'],
            loading_time=0.5,
            variable_to_instrument_map={'var1': 'instrument1', 'var2': 'instrument2'},
            instrument_to_variables_map={'instrument1': ['var1'], 'instrument2': ['var2']},
            success=True,
            failed_instruments=[],
            error_messages={}
        )
        
        assert result.success is True
        assert len(result.rules_cache) == 2
        assert result.loaded_instruments_count == 2
        assert len(result.failed_instruments) == 0
    
    def test_partial_rules_loading_failure(self):
        """Test partial failure in rules loading."""
        test_rules = {'instrument1': {'rule1': 'value1'}}
        
        result = RulesLoadingResult(
            rules_cache=test_rules,
            instruments_processed=['instrument1', 'instrument2'],
            loading_time=1.0,
            variable_to_instrument_map={'var1': 'instrument1'},
            instrument_to_variables_map={'instrument1': ['var1']},
            success=False,
            failed_instruments=['instrument2'],
            error_messages={'instrument2': 'File not found'}
        )
        
        assert result.success is False
        assert len(result.rules_cache) == 1
        assert 'instrument2' in result.failed_instruments
        assert result.loaded_instruments_count == 1
    
    def test_get_rules_for_instrument(self):
        """Test getting rules for specific instrument."""
        test_rules = {'instrument1': {'rule1': 'value1'}}
        
        result = RulesLoadingResult(
            rules_cache=test_rules,
            instruments_processed=['instrument1'],
            loading_time=0.5,
            variable_to_instrument_map={'var1': 'instrument1'},
            instrument_to_variables_map={'instrument1': ['var1']},
            success=True
        )
        
        rules = result.get_rules_for_instrument('instrument1')
        assert rules == {'rule1': 'value1'}
        
        # Test non-existent instrument
        empty_rules = result.get_rules_for_instrument('nonexistent')
        assert empty_rules == {}


class TestDataPreparationResult:
    """Test DataPreparationResult dataclass."""
    
    def test_successful_data_preparation(self):
        """Test successful data preparation result."""
        test_cache = {
            'instrument1': pd.DataFrame({'id': [1, 2]}),
            'instrument2': pd.DataFrame({'id': [3, 4, 5]})
        }
        
        result = DataPreparationResult(
            instrument_data_cache=test_cache,
            complete_visits_data=None,
            preparation_time=2.0,
            records_per_instrument={'instrument1': 2, 'instrument2': 3},
            success=True,
            error_message=None
        )
        
        assert result.success is True
        assert result.total_records_prepared == 5
        assert len(result.instruments_with_data) == 2
        assert 'instrument1' in result.instruments_with_data
        assert 'instrument2' in result.instruments_with_data
    
    def test_get_instrument_data(self):
        """Test getting data for specific instrument."""
        test_cache = {'instrument1': pd.DataFrame({'id': [1, 2]})}
        
        result = DataPreparationResult(
            instrument_data_cache=test_cache,
            complete_visits_data=None,
            preparation_time=1.0,
            records_per_instrument={'instrument1': 2},
            success=True
        )
        
        data = result.get_instrument_data('instrument1')
        assert len(data) == 2
        
        # Test non-existent instrument
        empty_data = result.get_instrument_data('nonexistent')
        assert empty_data.empty


class TestValidationResult:
    """Test ValidationResult dataclass."""
    
    def test_successful_validation_with_errors(self):
        """Test validation that succeeds but finds errors in data."""
        errors_df = pd.DataFrame({
            'record_id': [1, 2],
            'error_message': ['Missing value', 'Invalid format']
        })
        logs_df = pd.DataFrame({
            'record_id': [1, 2, 3],
            'status': ['error', 'error', 'pass']
        })
        all_records_df = pd.DataFrame({
            'record_id': [1, 2, 3],
            'instrument': ['inst1', 'inst1', 'inst2']
        })
        
        result = ValidationResult(
            errors_df=errors_df,
            logs_df=logs_df,
            passed_df=pd.DataFrame(),
            validation_logs_df=pd.DataFrame(),
            all_records_df=all_records_df,
            validation_time=2.0,
            instruments_processed=['inst1', 'inst2'],
            validation_summary={'total_errors': 2, 'total_warnings': 0},
            success=True,
            error_message=None
        )
        
        assert result.success is True
        assert result.total_errors == 2
        assert result.total_records_validated == 3
        assert result.error_rate == (2/3) * 100  # 66.67%
    
    def test_validation_system_failure(self):
        """Test validation system failure."""
        result = ValidationResult(
            errors_df=pd.DataFrame(),
            logs_df=pd.DataFrame(),
            passed_df=pd.DataFrame(),
            validation_logs_df=pd.DataFrame(),
            all_records_df=pd.DataFrame(),
            validation_time=0.5,
            instruments_processed=[],
            validation_summary={},
            success=False,
            error_message="Validation system crashed"
        )
        
        assert result.success is False
        assert result.total_errors == 0
        assert result.total_records_validated == 0
        assert result.error_message == "Validation system crashed"


class TestCustomExceptions:
    """Test custom exception hierarchy."""
    
    def test_pipeline_stage_error_inheritance(self):
        """Test that all custom exceptions inherit from PipelineStageError."""
        assert issubclass(DataFetchError, PipelineStageError)
        assert issubclass(RulesLoadingError, PipelineStageError)
        assert issubclass(DataPreparationError, PipelineStageError)
        assert issubclass(ValidationError, PipelineStageError)
        assert issubclass(ReportGenerationError, PipelineStageError)
    
    def test_exception_creation_with_context(self):
        """Test creating exceptions with additional context."""
        error = DataFetchError("Connection failed")
        
        assert "data_fetch" in str(error)
        assert "Connection failed" in str(error)
    
    def test_exception_with_original_error(self):
        """Test creating exceptions with original error context."""
        original_error = ConnectionError("Network timeout")
        error = DataFetchError("Connection failed", original_error)
        
        assert error.original_error == original_error
        assert error.stage == "data_fetch"


class TestResultObjectIntegration:
    """Test integration between different result objects."""
    
    def test_result_object_chaining(self):
        """Test that result objects can be chained through pipeline stages."""
        # Data fetch result
        data_result = DataFetchResult(
            data=pd.DataFrame({'id': [1, 2, 3]}),
            records_processed=3,
            execution_time=1.0,
            source_info={'server': 'redcap'},
            fetch_timestamp=datetime.now(),
            success=True
        )
        
        # Use data from previous stage in validation
        validation_result = ValidationResult(
            errors_df=pd.DataFrame(),
            logs_df=pd.DataFrame(),
            passed_df=pd.DataFrame(),
            validation_logs_df=pd.DataFrame(),
            all_records_df=data_result.data,  # Chain the data
            validation_time=2.0,
            instruments_processed=['inst1'],
            validation_summary={},
            success=True
        )
        
        assert validation_result.total_records_validated == data_result.records_processed
        assert both_stages_successful(data_result, validation_result)


def both_stages_successful(stage1_result, stage2_result) -> bool:
    """Helper function to check if both stages succeeded."""
    return stage1_result.success and stage2_result.success


if __name__ == "__main__":
    pytest.main([__file__])
