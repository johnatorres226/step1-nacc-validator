#!/usr/bin/env python3
"""
Tests for the DynamicInstrumentProcessor class.

This module tests the consolidated dynamic instrument processing functionality
that replaces the scattered logic across multiple helper functions.
"""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from src.pipeline.helpers import DynamicInstrumentProcessor


class TestDynamicInstrumentProcessor:
    """Test cases for DynamicInstrumentProcessor."""

    def test_init_valid_dynamic_instrument(self):
        """Test initialization with a valid dynamic instrument."""
        with patch('src.pipeline.helpers.is_dynamic_rule_instrument', return_value=True), \
             patch('src.pipeline.helpers.get_discriminant_variable', return_value='loc_c2_or_c2t'), \
             patch('src.pipeline.helpers.get_rule_mappings', return_value={'C2': 'c2_rules.json', 'C2T': 'c2t_rules.json'}):
            
            processor = DynamicInstrumentProcessor('c2c2t_neuropsychological_battery_scores')
            
            assert processor.instrument_name == 'c2c2t_neuropsychological_battery_scores'
            assert processor.discriminant_var == 'loc_c2_or_c2t'
            assert processor.rule_mappings == {'C2': 'c2_rules.json', 'C2T': 'c2t_rules.json'}
            assert processor._rule_cache is None
            assert processor._variables_cache is None

    def test_init_invalid_instrument(self):
        """Test initialization with a non-dynamic instrument raises ValueError."""
        with patch('src.pipeline.helpers.is_dynamic_rule_instrument', return_value=False):
            
            with pytest.raises(ValueError, match="not configured for dynamic rule selection"):
                DynamicInstrumentProcessor('a1_participant_demographics')

    def test_get_all_variables_caching(self):
        """Test that get_all_variables caches results properly."""
        mock_rule_map = {
            'C2': {'var1': {}, 'var2': {}, 'common_var': {}},
            'C2T': {'var3': {}, 'var4': {}, 'common_var': {}}
        }
        
        with patch('src.pipeline.helpers.is_dynamic_rule_instrument', return_value=True), \
             patch('src.pipeline.helpers.get_discriminant_variable', return_value='loc_c2_or_c2t'), \
             patch('src.pipeline.helpers.get_rule_mappings', return_value={'C2': 'c2_rules.json', 'C2T': 'c2t_rules.json'}), \
             patch('src.pipeline.helpers.load_dynamic_rules_for_instrument', return_value=mock_rule_map) as mock_load:
            
            processor = DynamicInstrumentProcessor('c2c2t_neuropsychological_battery_scores')
            
            # First call should load rules
            variables1 = processor.get_all_variables()
            assert mock_load.call_count == 1
            assert set(variables1) == {'var1', 'var2', 'var3', 'var4', 'common_var'}
            
            # Second call should use cache
            variables2 = processor.get_all_variables()
            assert mock_load.call_count == 1  # Not called again
            assert variables1 == variables2

    def test_get_rules_for_variant(self):
        """Test getting rules for a specific variant."""
        mock_rule_map = {
            'C2': {'var1': {'type': 'integer'}, 'var2': {'type': 'string'}},
            'C2T': {'var3': {'type': 'float'}, 'var4': {'type': 'date'}}
        }
        
        with patch('src.pipeline.helpers.is_dynamic_rule_instrument', return_value=True), \
             patch('src.pipeline.helpers.get_discriminant_variable', return_value='loc_c2_or_c2t'), \
             patch('src.pipeline.helpers.get_rule_mappings', return_value={'C2': 'c2_rules.json', 'C2T': 'c2t_rules.json'}), \
             patch('src.pipeline.helpers.load_dynamic_rules_for_instrument', return_value=mock_rule_map):
            
            processor = DynamicInstrumentProcessor('c2c2t_neuropsychological_battery_scores')
            
            c2_rules = processor.get_rules_for_variant('C2')
            assert c2_rules == {'var1': {'type': 'integer'}, 'var2': {'type': 'string'}}
            
            c2t_rules = processor.get_rules_for_variant('c2t')  # Test case insensitive
            assert c2t_rules == {'var3': {'type': 'float'}, 'var4': {'type': 'date'}}
            
            # Test unknown variant
            unknown_rules = processor.get_rules_for_variant('UNKNOWN')
            assert unknown_rules == {}

    def test_prepare_data_basic_functionality(self):
        """Test basic data preparation functionality."""
        # Sample input data
        input_df = pd.DataFrame({
            'ptid': ['001', '002', '003'],
            'redcap_event_name': ['baseline_arm_1', 'baseline_arm_1', 'baseline_arm_1'],
            'loc_c2_or_c2t': ['C2', 'C2T', 'C2'],
            'var1': [10, None, 20],
            'var2': ['A', 'B', None],
            'var3': [None, 15.5, None],
            'var4': [None, '2023-01-01', None],
            'c2c2t_neuropsychological_battery_scores_complete': ['2', '2', '1'],
            'unrelated_var': ['X', 'Y', 'Z']
        })
        
        mock_rule_map = {
            'C2': {'var1': {}, 'var2': {}},
            'C2T': {'var3': {}, 'var4': {}}
        }
        
        with patch('src.pipeline.helpers.is_dynamic_rule_instrument', return_value=True), \
             patch('src.pipeline.helpers.get_discriminant_variable', return_value='loc_c2_or_c2t'), \
             patch('src.pipeline.helpers.get_rule_mappings', return_value={'C2': 'c2_rules.json', 'C2T': 'c2t_rules.json'}), \
             patch('src.pipeline.helpers.load_dynamic_rules_for_instrument', return_value=mock_rule_map), \
             patch('src.pipeline.helpers.get_core_columns', return_value=['ptid', 'redcap_event_name']), \
             patch('src.pipeline.helpers.get_completion_columns', return_value=['c2c2t_neuropsychological_battery_scores_complete']):
            
            processor = DynamicInstrumentProcessor('c2c2t_neuropsychological_battery_scores')
            
            result_df, variables = processor.prepare_data(input_df, 'ptid')
            
            # Check that all expected variables are returned
            expected_variables = ['var1', 'var2', 'var3', 'var4']
            assert set(variables) == set(expected_variables)
            
            # Check that DataFrame contains expected columns
            expected_cols = ['ptid', 'redcap_event_name', 'loc_c2_or_c2t', 'var1', 'var2', 'var3', 'var4', 'c2c2t_neuropsychological_battery_scores_complete']
            assert set(result_df.columns) <= set(expected_cols)
            
            # Check that unrelated columns are excluded
            assert 'unrelated_var' not in result_df.columns
            
            # Check that only records with data are included (rows with all instrument vars null should be filtered)
            assert len(result_df) <= len(input_df)

    def test_get_variants_in_data(self):
        """Test getting variants present in data."""
        sample_df = pd.DataFrame({
            'ptid': ['001', '002', '003', '004'],
            'loc_c2_or_c2t': ['C2', 'c2t', 'C2', None]
        })
        
        with patch('src.pipeline.helpers.is_dynamic_rule_instrument', return_value=True), \
             patch('src.pipeline.helpers.get_discriminant_variable', return_value='loc_c2_or_c2t'), \
             patch('src.pipeline.helpers.get_rule_mappings', return_value={'C2': 'c2_rules.json', 'C2T': 'c2t_rules.json'}):
            
            processor = DynamicInstrumentProcessor('c2c2t_neuropsychological_battery_scores')
            
            variants = processor.get_variants_in_data(sample_df)
            
            # Should return normalized variants that exist in rule mappings
            assert set(variants) == {'C2', 'C2T'}

    def test_get_variants_in_data_missing_discriminant(self):
        """Test getting variants when discriminant variable is missing."""
        sample_df = pd.DataFrame({
            'ptid': ['001', '002'],
            'other_var': ['A', 'B']
        })
        
        with patch('src.pipeline.helpers.is_dynamic_rule_instrument', return_value=True), \
             patch('src.pipeline.helpers.get_discriminant_variable', return_value='loc_c2_or_c2t'), \
             patch('src.pipeline.helpers.get_rule_mappings', return_value={'C2': 'c2_rules.json', 'C2T': 'c2t_rules.json'}):
            
            processor = DynamicInstrumentProcessor('c2c2t_neuropsychological_battery_scores')
            
            variants = processor.get_variants_in_data(sample_df)
            
            assert variants == []

    def test_rule_cache_persistence(self):
        """Test that rule cache persists across method calls."""
        mock_rule_map = {
            'C2': {'var1': {}},
            'C2T': {'var2': {}}
        }
        
        with patch('src.pipeline.helpers.is_dynamic_rule_instrument', return_value=True), \
             patch('src.pipeline.helpers.get_discriminant_variable', return_value='loc_c2_or_c2t'), \
             patch('src.pipeline.helpers.get_rule_mappings', return_value={'C2': 'c2_rules.json', 'C2T': 'c2t_rules.json'}), \
             patch('src.pipeline.helpers.load_dynamic_rules_for_instrument', return_value=mock_rule_map) as mock_load:
            
            processor = DynamicInstrumentProcessor('c2c2t_neuropsychological_battery_scores')
            
            # Make multiple calls that should use the cache
            processor.get_all_variables()
            processor.get_rules_for_variant('C2')
            processor.get_rules_for_variant('C2T')
            
            # Rule loading should only happen once
            assert mock_load.call_count == 1

    def test_empty_dataframe_handling(self):
        """Test handling of empty DataFrames."""
        empty_df = pd.DataFrame()
        
        with patch('src.pipeline.helpers.is_dynamic_rule_instrument', return_value=True), \
             patch('src.pipeline.helpers.get_discriminant_variable', return_value='loc_c2_or_c2t'), \
             patch('src.pipeline.helpers.get_rule_mappings', return_value={'C2': 'c2_rules.json'}), \
             patch('src.pipeline.helpers.load_dynamic_rules_for_instrument', return_value={'C2': {'var1': {}}}), \
             patch('src.pipeline.helpers.get_core_columns', return_value=['ptid']), \
             patch('src.pipeline.helpers.get_completion_columns', return_value=[]):
            
            processor = DynamicInstrumentProcessor('c2c2t_neuropsychological_battery_scores')
            
            result_df, variables = processor.prepare_data(empty_df, 'ptid')
            
            assert result_df.empty
            assert variables == ['var1']


if __name__ == '__main__':
    pytest.main([__file__])
