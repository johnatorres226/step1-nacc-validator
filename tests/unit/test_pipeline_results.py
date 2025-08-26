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
    ReportGenerationResult,
    PipelineExecutionResult,
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
            success=True,
            data_df=test_df,
            records_processed=3,
            execution_time=1.5,
            memory_usage_mb=10.2,
            error=None
        )
        
        assert result.success is True
        assert len(result.data_df) == 3
        assert result.records_processed == 3
        assert result.execution_time == 1.5
        assert result.memory_usage_mb == 10.2
        assert result.error is None
        assert result.is_valid is True
    
    def test_failed_data_fetch_result(self):
        """Test creating a failed data fetch result."""
        error = DataFetchError("Connection failed")
        
        result = DataFetchResult(
            success=False,
            data_df=None,
            records_processed=0,
            execution_time=0.5,
            memory_usage_mb=0.0,
            error=error
        )
        
        assert result.success is False
        assert result.data_df is None
        assert result.records_processed == 0
        assert result.error == error
        assert result.is_valid is False
    
    def test_invalid_successful_result_empty_dataframe(self):
        """Test that successful result with empty dataframe is invalid."""
        result = DataFetchResult(
            success=True,
            data_df=pd.DataFrame(),  # Empty dataframe
            records_processed=0,
            execution_time=1.0,
            memory_usage_mb=5.0,
            error=None
        )
        
        assert result.success is True
        assert result.is_valid is False  # Should be invalid due to empty dataframe
    
    def test_get_summary(self):
        """Test result summary generation."""
        test_df = pd.DataFrame({'id': [1, 2]})
        result = DataFetchResult(
            success=True,
            data_df=test_df,
            records_processed=2,
            execution_time=1.0,
            memory_usage_mb=5.0,
            error=None
        )
        
        summary = result.get_summary()
        
        expected_keys = {
            'success', 'records_processed', 'execution_time', 
            'memory_usage_mb', 'error'
        }
        assert set(summary.keys()) == expected_keys
        assert summary['success'] is True
        assert summary['records_processed'] == 2
        assert summary['error'] is None


class TestRulesLoadingResult:
    """Test RulesLoadingResult dataclass."""
    
    def test_successful_rules_loading(self):
        """Test successful rules loading result."""
        test_rules = {
            'instrument1': {'rule1': 'value1'},
            'instrument2': {'rule2': 'value2'}
        }
        
        result = RulesLoadingResult(
            success=True,
            rules_cache=test_rules,
            instruments_loaded=['instrument1', 'instrument2'],
            failed_instruments=[],
            execution_time=0.5,
            error=None
        )
        
        assert result.success is True
        assert len(result.rules_cache) == 2
        assert len(result.instruments_loaded) == 2
        assert len(result.failed_instruments) == 0
        assert result.is_valid is True
    
    def test_partial_rules_loading_failure(self):
        """Test partial failure in rules loading."""
        test_rules = {'instrument1': {'rule1': 'value1'}}
        
        result = RulesLoadingResult(
            success=False,  # Overall failure due to some instruments failing
            rules_cache=test_rules,
            instruments_loaded=['instrument1'],
            failed_instruments=['instrument2'],
            execution_time=1.0,
            error=RulesLoadingError("Failed to load instrument2")
        )
        
        assert result.success is False
        assert len(result.rules_cache) == 1
        assert 'instrument2' in result.failed_instruments
        assert result.is_valid is False
    
    def test_complete_rules_loading_failure(self):
        """Test complete failure in rules loading."""
        result = RulesLoadingResult(
            success=False,
            rules_cache={},
            instruments_loaded=[],
            failed_instruments=['instrument1', 'instrument2'],
            execution_time=0.1,
            error=RulesLoadingError("All instruments failed to load")
        )
        
        assert result.success is False
        assert len(result.rules_cache) == 0
        assert len(result.failed_instruments) == 2
        assert result.is_valid is False


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
        
        result = ValidationResult(
            success=True,
            errors_df=errors_df,
            logs_df=logs_df,
            total_errors=2,
            total_warnings=0,
            records_validated=3,
            execution_time=2.0,
            error=None
        )
        
        assert result.success is True
        assert result.total_errors == 2
        assert result.records_validated == 3
        assert len(result.errors_df) == 2
        assert result.is_valid is True
    
    def test_validation_system_failure(self):
        """Test validation system failure."""
        result = ValidationResult(
            success=False,
            errors_df=None,
            logs_df=None,
            total_errors=0,
            total_warnings=0,
            records_validated=0,
            execution_time=0.5,
            error=ValidationError("Validation system crashed")
        )
        
        assert result.success is False
        assert result.total_errors == 0
        assert result.records_validated == 0
        assert result.is_valid is False


class TestPipelineExecutionResult:
    """Test PipelineExecutionResult dataclass."""
    
    def test_successful_pipeline_execution(self):
        """Test successful end-to-end pipeline execution."""
        # Create mock successful stage results
        data_fetch = DataFetchResult(
            success=True,
            data_df=pd.DataFrame({'id': [1, 2]}),
            records_processed=2,
            execution_time=1.0,
            memory_usage_mb=5.0,
            error=None
        )
        
        rules_loading = RulesLoadingResult(
            success=True,
            rules_cache={'inst1': {}},
            instruments_loaded=['inst1'],
            failed_instruments=[],
            execution_time=0.5,
            error=None
        )
        
        validation = ValidationResult(
            success=True,
            errors_df=pd.DataFrame(),
            logs_df=pd.DataFrame(),
            total_errors=0,
            total_warnings=0,
            records_validated=2,
            execution_time=1.5,
            error=None
        )
        
        pipeline_result = PipelineExecutionResult(
            success=True,
            data_fetch=data_fetch,
            rules_loading=rules_loading,
            data_preparation=None,  # Optional
            validation=validation,
            report_generation=None,  # Optional
            total_execution_time=3.0,
            output_directory="/test/output",
            pipeline_error=None
        )
        
        assert pipeline_result.success is True
        assert pipeline_result.total_execution_time == 3.0
        assert pipeline_result.data_fetch.success is True
        assert pipeline_result.validation.total_errors == 0
        assert pipeline_result.is_valid is True
    
    def test_pipeline_failure_due_to_stage_failure(self):
        """Test pipeline failure when one stage fails."""
        # Successful data fetch
        data_fetch = DataFetchResult(
            success=True,
            data_df=pd.DataFrame({'id': [1]}),
            records_processed=1,
            execution_time=1.0,
            memory_usage_mb=5.0,
            error=None
        )
        
        # Failed rules loading
        rules_loading = RulesLoadingResult(
            success=False,
            rules_cache={},
            instruments_loaded=[],
            failed_instruments=['inst1'],
            execution_time=0.5,
            error=RulesLoadingError("Failed to load rules")
        )
        
        pipeline_result = PipelineExecutionResult(
            success=False,
            data_fetch=data_fetch,
            rules_loading=rules_loading,
            data_preparation=None,
            validation=None,  # Never reached due to rules failure
            report_generation=None,
            total_execution_time=1.5,
            output_directory="/test/output",
            pipeline_error=PipelineError("Rules loading stage failed")
        )
        
        assert pipeline_result.success is False
        assert pipeline_result.data_fetch.success is True  # This stage succeeded
        assert pipeline_result.rules_loading.success is False  # This stage failed
        assert pipeline_result.validation is None  # Never reached
        assert pipeline_result.is_valid is False


class TestCustomExceptions:
    """Test custom exception hierarchy."""
    
    def test_pipeline_error_inheritance(self):
        """Test that all custom exceptions inherit from PipelineError."""
        assert issubclass(DataFetchError, PipelineError)
        assert issubclass(RulesLoadingError, PipelineError)
        assert issubclass(DataPreparationError, PipelineError)
        assert issubclass(ValidationError, PipelineError)
        assert issubclass(ReportGenerationError, PipelineError)
    
    def test_exception_creation_with_context(self):
        """Test creating exceptions with additional context."""
        error = DataFetchError("Connection failed", {"host": "localhost", "port": 5432})
        
        assert str(error) == "Connection failed"
        assert hasattr(error, 'args')
        assert error.args[0] == "Connection failed"


class TestResultObjectIntegration:
    """Test integration between different result objects."""
    
    def test_result_object_chaining(self):
        """Test that result objects can be chained through pipeline stages."""
        # Data fetch result
        data_result = DataFetchResult(
            success=True,
            data_df=pd.DataFrame({'id': [1, 2, 3]}),
            records_processed=3,
            execution_time=1.0,
            memory_usage_mb=10.0,
            error=None
        )
        
        # Use data from previous stage in validation
        validation_result = ValidationResult(
            success=True,
            errors_df=pd.DataFrame(),
            logs_df=pd.DataFrame(),
            total_errors=0,
            total_warnings=0,
            records_validated=data_result.records_processed,  # Chain the data
            execution_time=2.0,
            error=None
        )
        
        assert validation_result.records_validated == data_result.records_processed
        assert both_stages_successful(data_result, validation_result)


def both_stages_successful(stage1_result, stage2_result) -> bool:
    """Helper function to check if both stages succeeded."""
    return stage1_result.success and stage2_result.success


if __name__ == "__main__":
    pytest.main([__file__])
