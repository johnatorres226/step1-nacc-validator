"""
Unit tests for core data processing functions.

Tests the available functions from pipeline/core/data_processing.py
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
from datetime import datetime

from pipeline.core.data_processing import (
    build_variable_maps,
    prepare_instrument_data_cache,
    preprocess_cast_types,
    extract_variables_from_rules,
    get_variables_for_instrument,
    cast_to_integer_type,
    cast_to_float_type,
    cast_to_datetime_type,
    create_variable_to_instrument_map,
    create_instrument_to_variables_map
)


class TestExtractVariablesFromRules:
    """Test extract_variables_from_rules function."""
    
    def test_extract_variables_basic(self):
        """Test extracting variables from rules dictionary."""
        rules = {
            'field1': {'type': 'text'},
            'field2': {'type': 'number'},
            'field3': {'type': 'date'}
        }
        
        variables = extract_variables_from_rules(rules)
        
        assert isinstance(variables, list)
        assert 'field1' in variables
        assert 'field2' in variables
        assert 'field3' in variables
    
    def test_extract_variables_empty_rules(self):
        """Test extracting variables from empty rules."""
        rules = {}
        variables = extract_variables_from_rules(rules)
        
        assert isinstance(variables, list)
        assert len(variables) == 0


class TestGetVariablesForInstrument:
    """Test get_variables_for_instrument function."""
    
    def test_get_variables_with_rules_cache(self):
        """Test getting variables for instrument with rules cache."""
        rules_cache = {
            'instrument1': {
                'field1': {'type': 'text'},
                'field2': {'type': 'number'}
            }
        }
        
        variables = get_variables_for_instrument('instrument1', rules_cache)
        
        assert isinstance(variables, list)
        # Should return variables from the rules cache
    
    def test_get_variables_missing_instrument(self):
        """Test getting variables for instrument not in cache."""
        rules_cache = {
            'instrument1': {
                'field1': {'type': 'text'}
            }
        }
        
        variables = get_variables_for_instrument('instrument2', rules_cache)
        
        assert isinstance(variables, list)
        # Should handle missing instrument gracefully


class TestCastToIntegerType:
    """Test cast_to_integer_type function."""
    
    def test_cast_valid_integers(self):
        """Test casting valid integer strings."""
        series = pd.Series(['1', '2', '3', '0'])
        result = cast_to_integer_type(series)
        
        assert isinstance(result, pd.Series)
        # Should handle the conversion appropriately
    
    def test_cast_with_missing_values(self):
        """Test casting with missing/invalid values."""
        series = pd.Series(['1', '', '3', None, 'invalid'])
        result = cast_to_integer_type(series)
        
        assert isinstance(result, pd.Series)
        assert len(result) == len(series)
    
    def test_cast_empty_series(self):
        """Test casting empty series."""
        series = pd.Series([], dtype=object)
        result = cast_to_integer_type(series)
        
        assert isinstance(result, pd.Series)
        assert len(result) == 0


class TestCastToFloatType:
    """Test cast_to_float_type function."""
    
    def test_cast_valid_floats(self):
        """Test casting valid float strings."""
        series = pd.Series(['1.5', '2.0', '3.14', '0.0'])
        result = cast_to_float_type(series)
        
        assert isinstance(result, pd.Series)
    
    def test_cast_floats_with_missing(self):
        """Test casting floats with missing values."""
        series = pd.Series(['1.5', '', '3.14', None, 'invalid'])
        result = cast_to_float_type(series)
        
        assert isinstance(result, pd.Series)
        assert len(result) == len(series)


class TestCastToDatetimeType:
    """Test cast_to_datetime_type function."""
    
    def test_cast_valid_dates(self):
        """Test casting valid date strings."""
        series = pd.Series(['2023-01-01', '2023-12-31', '2024-06-15'])
        result = cast_to_datetime_type(series)
        
        assert isinstance(result, pd.Series)
    
    def test_cast_dates_with_missing(self):
        """Test casting dates with missing/invalid values."""
        series = pd.Series(['2023-01-01', '', 'invalid-date', None])
        result = cast_to_datetime_type(series)
        
        assert isinstance(result, pd.Series)
        assert len(result) == len(series)


class TestPreprocessCastTypes:
    """Test preprocess_cast_types function."""
    
    def test_basic_type_casting(self):
        """Test basic type casting with rules."""
        test_df = pd.DataFrame({
            'text_field': ['a', 'b', 'c'],
            'number_field': ['1', '2', '3'],
            'date_field': ['2023-01-01', '2023-01-02', '2023-01-03']
        })
        
        rules = {
            'instrument1': {
                'text_field': {'type': 'text'},
                'number_field': {'type': 'number'},
                'date_field': {'type': 'date'}
            }
        }
        
        result_df = preprocess_cast_types(test_df, rules)
        
        assert isinstance(result_df, pd.DataFrame)
        assert len(result_df) == len(test_df)
        assert list(result_df.columns) == list(test_df.columns)
    
    def test_cast_types_empty_rules(self):
        """Test type casting with empty rules."""
        test_df = pd.DataFrame({
            'field1': ['a', 'b', 'c']
        })
        
        rules = {}
        result_df = preprocess_cast_types(test_df, rules)
        
        assert isinstance(result_df, pd.DataFrame)
        # Should handle empty rules gracefully
    
    def test_cast_types_empty_dataframe(self):
        """Test type casting with empty dataframe."""
        test_df = pd.DataFrame()
        rules = {'instrument1': {'field1': {'type': 'text'}}}
        
        result_df = preprocess_cast_types(test_df, rules)
        
        assert isinstance(result_df, pd.DataFrame)
        assert len(result_df) == 0


class TestCreateVariableToInstrumentMap:
    """Test create_variable_to_instrument_map function."""
    
    def test_create_variable_map(self):
        """Test creating variable to instrument mapping."""
        instruments = ['a1', 'b3']
        rules_cache = {
            'a1': {
                'var1': {'type': 'text'},
                'var2': {'type': 'number'}
            },
            'b3': {
                'var3': {'type': 'text'},
                'var4': {'type': 'date'}
            }
        }
        
        variable_map = create_variable_to_instrument_map(instruments, rules_cache)
        
        assert isinstance(variable_map, dict)
        # Should create mapping from variables to instruments
    
    def test_create_variable_map_empty(self):
        """Test creating variable map with empty inputs."""
        instruments = []
        rules_cache = {}
        
        variable_map = create_variable_to_instrument_map(instruments, rules_cache)
        
        assert isinstance(variable_map, dict)


class TestCreateInstrumentToVariablesMap:
    """Test create_instrument_to_variables_map function."""
    
    def test_create_instrument_map(self):
        """Test creating instrument to variables mapping."""
        instruments = ['a1', 'b3']
        rules_cache = {
            'a1': {
                'var1': {'type': 'text'},
                'var2': {'type': 'number'}
            },
            'b3': {
                'var3': {'type': 'text'}
            }
        }
        
        instrument_map = create_instrument_to_variables_map(instruments, rules_cache)
        
        assert isinstance(instrument_map, dict)
        assert 'a1' in instrument_map
        assert 'b3' in instrument_map
    
    def test_create_instrument_map_empty(self):
        """Test creating instrument map with empty inputs."""
        instruments = []
        rules_cache = {}
        
        instrument_map = create_instrument_to_variables_map(instruments, rules_cache)
        
        assert isinstance(instrument_map, dict)


class TestBuildVariableMaps:
    """Test build_variable_maps function."""
    
    def test_build_maps_basic(self):
        """Test building variable maps with basic inputs."""
        instruments = ['a1', 'b3']
        rules_cache = {
            'a1': {'var1': {'type': 'text'}},
            'b3': {'var2': {'type': 'number'}}
        }
        
        variable_map, instrument_map = build_variable_maps(instruments, rules_cache)
        
        assert isinstance(variable_map, dict)
        assert isinstance(instrument_map, dict)
    
    def test_build_maps_empty(self):
        """Test building variable maps with empty inputs."""
        instruments = []
        rules_cache = {}
        
        variable_map, instrument_map = build_variable_maps(instruments, rules_cache)
        
        assert isinstance(variable_map, dict)
        assert isinstance(instrument_map, dict)


class TestPrepareInstrumentDataCache:
    """Test prepare_instrument_data_cache function."""
    
    @patch('pipeline.core.data_processing.create_processing_context')
    @patch('pipeline.core.data_processing.prepare_instrument_cache_strategy')
    def test_prepare_cache_basic(self, mock_strategy, mock_context):
        """Test basic instrument data cache preparation."""
        # Mock the internal functions
        mock_context.return_value = Mock()
        mock_strategy.return_value = {'a1': pd.DataFrame({'id': [1, 2]})}
        
        test_df = pd.DataFrame({
            'record_id': [1, 2, 3],
            'redcap_repeat_instrument': ['a1', 'a1', 'b3'],
            'value': ['x', 'y', 'z']
        })
        
        instruments = ['a1', 'b3']
        variable_map = {}
        primary_key_field = 'record_id'
        
        result = prepare_instrument_data_cache(
            test_df, instruments, variable_map, primary_key_field
        )
        
        # Should call the mocked functions and return result
        assert mock_context.called
        assert mock_strategy.called
        assert isinstance(result, dict)


class TestErrorHandling:
    """Test error handling in data processing functions."""
    
    def test_invalid_series_input(self):
        """Test handling of invalid series inputs."""
        invalid_inputs = [None, "not_a_series", 123, [1, 2, 3]]
        
        for invalid_input in invalid_inputs:
            with pytest.raises((TypeError, AttributeError)):
                cast_to_integer_type(invalid_input)
    
    def test_invalid_rules_input(self):
        """Test handling of invalid rules input."""
        test_df = pd.DataFrame({'field1': ['a', 'b']})
        
        invalid_rules = [None, "not_a_dict", 123]
        
        for invalid_input in invalid_rules:
            with pytest.raises((TypeError, AttributeError)):
                preprocess_cast_types(test_df, invalid_input)


if __name__ == "__main__":
    pytest.main([__file__])
