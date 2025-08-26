"""
Unit tests for core data processing functions.

Tests the refactored data processing functions from pipeline/core/data_processing.py
to ensure proper functionality, error handling, and data integrity.
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json

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


class TestBuildVariableMaps:
    """Test build_variable_maps function."""
    
    def test_basic_variable_map_creation(self):
        """Test creating variable maps from instrument list."""
        instruments = ['a1', 'b3', 'c2']
        variable_map, instrument_map = build_variable_maps(instruments)
        
        # Should create mappings for each instrument
        assert len(variable_map) > 0
        assert len(instrument_map) > 0
        
        # Check that instruments are included
        for instrument in instruments:
            assert instrument in instrument_map
    
    def test_empty_instrument_list(self):
        """Test handling of empty instrument list."""
        instruments = []
        variable_map, instrument_map = build_variable_maps(instruments)
        
        # Should return empty maps
        assert variable_map == {}
        assert instrument_map == {}
    
    def test_duplicate_instruments(self):
        """Test handling of duplicate instruments."""
        instruments = ['a1', 'a1', 'b3']
        variable_map, instrument_map = build_variable_maps(instruments)
        
        # Should handle duplicates gracefully
        assert 'a1' in instrument_map
        assert 'b3' in instrument_map


class TestFilterDataframeByInstruments:
    """Test filter_dataframe_by_instruments function."""
    
    def test_filter_valid_instruments(self):
        """Test filtering dataframe by valid instruments."""
        # Create test dataframe with redcap_repeat_instrument column
        test_df = pd.DataFrame({
            'record_id': [1, 2, 3, 4],
            'redcap_repeat_instrument': ['a1', 'b3', 'a1', 'c2'],
            'value': ['x', 'y', 'z', 'w']
        })
        
        instruments = ['a1', 'b3']
        result_df = filter_dataframe_by_instruments(test_df, instruments)
        
        # Should only include rows with specified instruments
        assert len(result_df) == 3  # Two a1 rows and one b3 row
        assert set(result_df['redcap_repeat_instrument'].values) == {'a1', 'b3'}
    
    def test_filter_no_matching_instruments(self):
        """Test filtering when no instruments match."""
        test_df = pd.DataFrame({
            'record_id': [1, 2],
            'redcap_repeat_instrument': ['x1', 'y2'],
            'value': ['a', 'b']
        })
        
        instruments = ['a1', 'b3']
        result_df = filter_dataframe_by_instruments(test_df, instruments)
        
        # Should return empty dataframe
        assert len(result_df) == 0
    
    def test_filter_missing_instrument_column(self):
        """Test handling when redcap_repeat_instrument column is missing."""
        test_df = pd.DataFrame({
            'record_id': [1, 2],
            'value': ['a', 'b']
        })
        
        instruments = ['a1', 'b3']
        
        # Should handle missing column gracefully or raise appropriate error
        with pytest.raises((KeyError, ValueError)):
            filter_dataframe_by_instruments(test_df, instruments)


class TestApplyVariableMappings:
    """Test apply_variable_mappings function."""
    
    def test_simple_variable_mapping(self):
        """Test applying simple variable mappings."""
        test_df = pd.DataFrame({
            'old_var1': [1, 2, 3],
            'old_var2': ['a', 'b', 'c'],
            'unchanged': [10, 20, 30]
        })
        
        variable_map = {
            'old_var1': 'new_var1',
            'old_var2': 'new_var2'
        }
        
        result_df = apply_variable_mappings(test_df, variable_map)
        
        # Should rename mapped columns and keep unmapped ones
        assert 'new_var1' in result_df.columns
        assert 'new_var2' in result_df.columns
        assert 'unchanged' in result_df.columns
        assert 'old_var1' not in result_df.columns
        assert 'old_var2' not in result_df.columns
        
        # Data should be preserved
        assert list(result_df['new_var1']) == [1, 2, 3]
        assert list(result_df['new_var2']) == ['a', 'b', 'c']
    
    def test_empty_variable_mapping(self):
        """Test with empty variable mapping."""
        test_df = pd.DataFrame({
            'var1': [1, 2, 3],
            'var2': ['a', 'b', 'c']
        })
        
        variable_map = {}
        result_df = apply_variable_mappings(test_df, variable_map)
        
        # Should return dataframe unchanged
        pd.testing.assert_frame_equal(result_df, test_df)
    
    def test_mapping_nonexistent_columns(self):
        """Test mapping variables that don't exist in dataframe."""
        test_df = pd.DataFrame({
            'existing_var': [1, 2, 3]
        })
        
        variable_map = {
            'nonexistent_var': 'new_var',
            'existing_var': 'renamed_var'
        }
        
        result_df = apply_variable_mappings(test_df, variable_map)
        
        # Should handle missing columns gracefully
        assert 'renamed_var' in result_df.columns
        assert 'existing_var' not in result_df.columns
        # nonexistent_var should be ignored


class TestValidateRequiredColumns:
    """Test validate_required_columns function."""
    
    def test_all_required_columns_present(self):
        """Test validation when all required columns are present."""
        test_df = pd.DataFrame({
            'record_id': [1, 2, 3],
            'redcap_repeat_instrument': ['a1', 'b3', 'a1'],
            'value': ['x', 'y', 'z']
        })
        
        required_columns = ['record_id', 'redcap_repeat_instrument']
        
        # Should not raise any exception
        validate_required_columns(test_df, required_columns)
    
    def test_missing_required_columns(self):
        """Test validation when required columns are missing."""
        test_df = pd.DataFrame({
            'record_id': [1, 2, 3],
            'value': ['x', 'y', 'z']
        })
        
        required_columns = ['record_id', 'redcap_repeat_instrument', 'missing_col']
        
        # Should raise appropriate error
        with pytest.raises((ValueError, KeyError)):
            validate_required_columns(test_df, required_columns)
    
    def test_empty_dataframe_validation(self):
        """Test validation with empty dataframe."""
        test_df = pd.DataFrame()
        required_columns = ['record_id']
        
        # Should raise appropriate error for empty dataframe
        with pytest.raises((ValueError, KeyError)):
            validate_required_columns(test_df, required_columns)


class TestPreprocessCastTypes:
    """Test preprocess_cast_types function."""
    
    def test_basic_type_casting(self):
        """Test basic type casting functionality."""
        test_df = pd.DataFrame({
            'numeric_col': ['1', '2', '3'],
            'text_col': ['a', 'b', 'c'],
            'date_col': ['2023-01-01', '2023-01-02', '2023-01-03']
        })
        
        result_df = preprocess_cast_types(test_df)
        
        # Should return a dataframe (exact types depend on implementation)
        assert isinstance(result_df, pd.DataFrame)
        assert len(result_df) == len(test_df)
        assert list(result_df.columns) == list(test_df.columns)
    
    def test_handle_missing_values(self):
        """Test handling of missing values during type casting."""
        test_df = pd.DataFrame({
            'numeric_col': ['1', '', '3', None],
            'text_col': ['a', 'b', '', None]
        })
        
        result_df = preprocess_cast_types(test_df)
        
        # Should handle missing values gracefully
        assert isinstance(result_df, pd.DataFrame)
        assert len(result_df) == len(test_df)
    
    def test_empty_dataframe_casting(self):
        """Test type casting with empty dataframe."""
        test_df = pd.DataFrame()
        
        result_df = preprocess_cast_types(test_df)
        
        # Should handle empty dataframe
        assert isinstance(result_df, pd.DataFrame)
        assert len(result_df) == 0


class TestCacheInstrumentData:
    """Test cache_instrument_data function."""
    
    def test_basic_data_caching(self):
        """Test basic instrument data caching."""
        test_df = pd.DataFrame({
            'record_id': [1, 2, 3, 4],
            'redcap_repeat_instrument': ['a1', 'b3', 'a1', 'c2'],
            'value': ['w', 'x', 'y', 'z']
        })
        
        instruments = ['a1', 'b3', 'c2']
        cache = cache_instrument_data(test_df, instruments)
        
        # Should create cache with instrument dataframes
        assert isinstance(cache, dict)
        assert 'a1' in cache
        assert 'b3' in cache
        assert 'c2' in cache
        
        # Check individual instrument data
        assert len(cache['a1']) == 2  # Two a1 records
        assert len(cache['b3']) == 1  # One b3 record
        assert len(cache['c2']) == 1  # One c2 record
    
    def test_cache_with_no_data_for_instrument(self):
        """Test caching when some instruments have no data."""
        test_df = pd.DataFrame({
            'record_id': [1, 2],
            'redcap_repeat_instrument': ['a1', 'a1'],
            'value': ['x', 'y']
        })
        
        instruments = ['a1', 'b3', 'c2']  # b3 and c2 have no data
        cache = cache_instrument_data(test_df, instruments)
        
        # Should create cache entries even for instruments with no data
        assert 'a1' in cache
        assert 'b3' in cache
        assert 'c2' in cache
        
        # a1 should have data, others should be empty
        assert len(cache['a1']) == 2
        assert len(cache['b3']) == 0
        assert len(cache['c2']) == 0


class TestGetUniqueInstrumentsFromDataframe:
    """Test get_unique_instruments_from_dataframe function."""
    
    def test_get_unique_instruments(self):
        """Test getting unique instruments from dataframe."""
        test_df = pd.DataFrame({
            'record_id': [1, 2, 3, 4, 5],
            'redcap_repeat_instrument': ['a1', 'b3', 'a1', 'c2', 'b3'],
            'value': ['v', 'w', 'x', 'y', 'z']
        })
        
        unique_instruments = get_unique_instruments_from_dataframe(test_df)
        
        # Should return unique instruments
        assert isinstance(unique_instruments, (list, set))
        unique_set = set(unique_instruments)
        assert unique_set == {'a1', 'b3', 'c2'}
    
    def test_empty_dataframe_instruments(self):
        """Test getting instruments from empty dataframe."""
        test_df = pd.DataFrame()
        
        unique_instruments = get_unique_instruments_from_dataframe(test_df)
        
        # Should handle empty dataframe
        assert isinstance(unique_instruments, (list, set))
        assert len(unique_instruments) == 0
    
    def test_missing_instrument_column(self):
        """Test handling when instrument column is missing."""
        test_df = pd.DataFrame({
            'record_id': [1, 2, 3],
            'value': ['a', 'b', 'c']
        })
        
        # Should handle missing column gracefully or raise appropriate error
        with pytest.raises((KeyError, ValueError)):
            get_unique_instruments_from_dataframe(test_df)


class TestPrepareInstrumentDataCache:
    """Test prepare_instrument_data_cache integration function."""
    
    def test_full_preparation_workflow(self):
        """Test the complete instrument data preparation workflow."""
        # Create comprehensive test data
        test_df = pd.DataFrame({
            'record_id': [1, 2, 3, 4, 5],
            'redcap_repeat_instrument': ['a1', 'b3', 'a1', 'c2', 'b3'],
            'old_var': ['val1', 'val2', 'val3', 'val4', 'val5'],
            'unchanged_var': [10, 20, 30, 40, 50]
        })
        
        instruments = ['a1', 'b3']
        variable_map = {'old_var': 'new_var'}
        primary_key_field = 'record_id'
        
        # Should complete full workflow
        cache = prepare_instrument_data_cache(
            test_df, 
            instruments, 
            variable_map, 
            primary_key_field
        )
        
        # Should return instrument cache
        assert isinstance(cache, dict)
        assert 'a1' in cache
        assert 'b3' in cache
        
        # Check that variable mapping was applied
        if len(cache['a1']) > 0:
            assert 'new_var' in cache['a1'].columns
            assert 'old_var' not in cache['a1'].columns
    
    def test_preparation_with_empty_data(self):
        """Test preparation workflow with empty data."""
        test_df = pd.DataFrame()
        instruments = ['a1', 'b3']
        variable_map = {}
        primary_key_field = 'record_id'
        
        # Should handle empty data gracefully
        cache = prepare_instrument_data_cache(
            test_df, 
            instruments, 
            variable_map, 
            primary_key_field
        )
        
        # Should return empty cache or handle appropriately
        assert isinstance(cache, dict)


class TestErrorHandling:
    """Test error handling in data processing functions."""
    
    def test_invalid_dataframe_input(self):
        """Test handling of invalid dataframe inputs."""
        invalid_inputs = [None, "not_a_dataframe", 123, [1, 2, 3]]
        
        for invalid_input in invalid_inputs:
            with pytest.raises((TypeError, AttributeError)):
                filter_dataframe_by_instruments(invalid_input, ['a1'])
    
    def test_invalid_instruments_input(self):
        """Test handling of invalid instruments input."""
        test_df = pd.DataFrame({'redcap_repeat_instrument': ['a1']})
        
        invalid_instruments = [None, "not_a_list", 123]
        
        for invalid_input in invalid_instruments:
            with pytest.raises((TypeError, AttributeError)):
                filter_dataframe_by_instruments(test_df, invalid_input)


if __name__ == "__main__":
    pytest.main([__file__])
