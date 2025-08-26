#!/usr/bin/env python3
"""
Tests for the strategy pattern instrument processors and configuration objects.

This module tests the new structure improvements implemented in Phase 2.
"""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.pipeline.context import ProcessingContext, ExportConfiguration, ValidationContext, ReportConfiguration
from src.pipeline.instrument_processors import (
    InstrumentDataProcessor, StandardInstrumentDataProcessor, 
    DynamicInstrumentDataProcessor, InstrumentDataCache
)


class TestConfigurationObjects:
    """Test cases for configuration dataclasses."""

    def test_processing_context_basic(self):
        """Test basic ProcessingContext functionality."""
        sample_df = pd.DataFrame({'ptid': ['001', '002'], 'data': [1, 2]})
        rules_cache = {'instrument1': {'var1': {'type': 'integer'}}}
        
        context = ProcessingContext(
            data_df=sample_df,
            instrument_list=['instrument1'],
            rules_cache=rules_cache,
            primary_key_field='ptid',
            config=MagicMock()
        )
        
        assert not context.is_empty
        assert context.get_instrument_variables('instrument1') == ['var1']
        assert context.get_instrument_variables('unknown') == []

    def test_processing_context_empty_data(self):
        """Test ProcessingContext with empty data."""
        empty_df = pd.DataFrame()
        
        context = ProcessingContext(
            data_df=empty_df,
            instrument_list=[],
            rules_cache={},
            primary_key_field='ptid',
            config=MagicMock()
        )
        
        assert context.is_empty

    def test_processing_context_filter(self):
        """Test filtering ProcessingContext to specific instruments."""
        sample_df = pd.DataFrame({'ptid': ['001'], 'data': [1]})
        rules_cache = {
            'instrument1': {'var1': {}},
            'instrument2': {'var2': {}},
            'instrument3': {'var3': {}}
        }
        
        context = ProcessingContext(
            data_df=sample_df,
            instrument_list=['instrument1', 'instrument2', 'instrument3'],
            rules_cache=rules_cache,
            primary_key_field='ptid',
            config=MagicMock()
        )
        
        filtered = context.filter_to_instruments(['instrument1', 'instrument3'])
        
        assert set(filtered.instrument_list) == {'instrument1', 'instrument3'}
        assert set(filtered.rules_cache.keys()) == {'instrument1', 'instrument3'}
        assert filtered.primary_key_field == 'ptid'

    def test_export_configuration(self):
        """Test ExportConfiguration functionality."""
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            export_config = ExportConfiguration(
                output_dir=Path(temp_dir),
                date_tag="26AUG2025",
                time_tag="120000"
            )
            
            assert export_config.file_suffix == "26AUG2025_120000"
            assert export_config.get_report_filename("ErrorReport") == "QC_ErrorReport_26AUG2025_120000.csv"
            
            logs_dir = export_config.get_validation_logs_dir()
            assert logs_dir.name == "Validation_Logs"
            assert logs_dir.exists()

    def test_validation_context(self):
        """Test ValidationContext functionality."""
        # Mock the imports in the ValidationContext methods
        with patch.object(ValidationContext, 'is_dynamic_instrument', property(lambda self: True)), \
             patch.object(ValidationContext, 'get_discriminant_variable', lambda self: 'variant_field'):
            
            context = ValidationContext(
                instrument_name='dynamic_instrument',
                primary_key_field='ptid',
                validation_rules={'var1': {'type': 'integer'}}
            )
            
            assert context.is_dynamic_instrument
            assert context.get_discriminant_variable() == 'variant_field'

    def test_report_configuration(self):
        """Test ReportConfiguration functionality."""
        export_config = ExportConfiguration(
            output_dir=Path("/test"),
            date_tag="test",
            time_tag="123"
        )
        
        config = ReportConfiguration(
            qc_run_by="test_user",
            primary_key_field="ptid",
            instruments=["inst1", "inst2"],
            export_config=export_config
        )
        
        status_cols = config.get_status_columns()
        expected_cols = [
            "ptid", "redcap_event_name", "qc_status_complete", 
            "qc_run_by", "qc_last_run", "qc_status", "quality_control_check_complete"
        ]
        assert status_cols == expected_cols


class TestInstrumentProcessors:
    """Test cases for strategy pattern instrument processors."""

    def test_processor_factory_standard(self):
        """Test factory creates standard processor for non-dynamic instruments."""
        with patch('src.pipeline.instrument_processors.is_dynamic_rule_instrument', return_value=False):
            processor = InstrumentDataProcessor.create_processor('standard_instrument')
            assert isinstance(processor, StandardInstrumentDataProcessor)

    def test_processor_factory_dynamic(self):
        """Test factory creates dynamic processor for dynamic instruments."""
        with patch('src.pipeline.instrument_processors.is_dynamic_rule_instrument', return_value=True), \
             patch('src.pipeline.instrument_processors.DynamicInstrumentDataProcessor') as mock_dynamic_proc:
            processor = InstrumentDataProcessor.create_processor('dynamic_instrument')
            mock_dynamic_proc.assert_called_once_with('dynamic_instrument')

    def test_standard_processor_get_variables(self):
        """Test standard processor variable retrieval."""
        rules_cache = {'test_instrument': {'var1': {}, 'var2': {}}}
        context = ProcessingContext(
            data_df=pd.DataFrame(),
            instrument_list=['test_instrument'],
            rules_cache=rules_cache,
            primary_key_field='ptid',
            config=MagicMock()
        )
        
        processor = StandardInstrumentDataProcessor('test_instrument')
        variables = processor.get_variables(context)
        
        assert set(variables) == {'var1', 'var2'}

    def test_standard_processor_prepare_data(self):
        """Test standard processor data preparation."""
        sample_df = pd.DataFrame({
            'ptid': ['001', '002', '003'],
            'redcap_event_name': ['baseline_arm_1', 'baseline_arm_1', 'baseline_arm_1'],
            'var1': [10, None, 20],
            'var2': ['A', None, 'C'],
            'unrelated_var': ['X', 'Y', 'Z']
        })
        
        rules_cache = {'test_instrument': {'var1': {}, 'var2': {}}}
        context = ProcessingContext(
            data_df=sample_df,
            instrument_list=['test_instrument'],
            rules_cache=rules_cache,
            primary_key_field='ptid',
            config=MagicMock()
        )
        
        with patch('src.pipeline.instrument_processors.get_core_columns', return_value=['ptid', 'redcap_event_name']), \
             patch('src.pipeline.instrument_processors.get_completion_columns', return_value=[]):
            
            processor = StandardInstrumentDataProcessor('test_instrument')
            result_df, variables = processor.prepare_data(context)
            
            # Should include core columns and instrument variables
            expected_cols = {'ptid', 'redcap_event_name', 'var1', 'var2'}
            assert set(result_df.columns) == expected_cols
            
            # Should exclude unrelated columns
            assert 'unrelated_var' not in result_df.columns
            
            # Should include records with data (records 1 and 3)
            assert len(result_df) == 2
            assert set(variables) == {'var1', 'var2'}

    def test_dynamic_processor_initialization(self):
        """Test dynamic processor initialization."""
        mock_dynamic_processor = MagicMock()
        
        with patch('src.pipeline.instrument_processors.DynamicInstrumentProcessor', return_value=mock_dynamic_processor):
            processor = DynamicInstrumentDataProcessor('dynamic_instrument')
            assert processor._processor == mock_dynamic_processor

    def test_dynamic_processor_methods(self):
        """Test dynamic processor method delegation."""
        mock_dynamic_processor = MagicMock()
        mock_dynamic_processor.get_all_variables.return_value = ['var1', 'var2']
        mock_dynamic_processor.prepare_data.return_value = (pd.DataFrame(), ['var1', 'var2'])
        mock_dynamic_processor.get_variants_in_data.return_value = ['C2', 'C2T']
        mock_dynamic_processor.get_rules_for_variant.return_value = {'var1': {}}
        
        with patch('src.pipeline.instrument_processors.DynamicInstrumentProcessor', return_value=mock_dynamic_processor):
            processor = DynamicInstrumentDataProcessor('dynamic_instrument')
            context = MagicMock()
            df = pd.DataFrame()
            
            # Test method delegation
            variables = processor.get_variables(context)
            assert variables == ['var1', 'var2']
            
            result_df, result_vars = processor.prepare_data(context)
            assert result_vars == ['var1', 'var2']
            
            variants = processor.get_variants_in_data(df)
            assert variants == ['C2', 'C2T']
            
            rules = processor.get_rules_for_variant('C2')
            assert rules == {'var1': {}}


class TestInstrumentDataCache:
    """Test cases for InstrumentDataCache."""

    def test_cache_initialization(self):
        """Test cache initialization."""
        context = ProcessingContext(
            data_df=pd.DataFrame(),
            instrument_list=['inst1', 'inst2'],
            rules_cache={},
            primary_key_field='ptid',
            config=MagicMock()
        )
        
        cache = InstrumentDataCache(context)
        assert cache.context == context
        assert cache.instrument_count == 0
        assert cache.total_records == 0

    def test_cache_prepare_instrument(self):
        """Test preparing individual instrument."""
        sample_df = pd.DataFrame({
            'ptid': ['001'],
            'var1': [10]
        })
        
        context = ProcessingContext(
            data_df=sample_df,
            instrument_list=['test_instrument'],
            rules_cache={'test_instrument': {'var1': {}}},
            primary_key_field='ptid',
            config=MagicMock()
        )
        
        with patch('src.pipeline.instrument_processors.InstrumentDataProcessor.create_processor') as mock_create:
            mock_processor = MagicMock()
            mock_processor.prepare_data.return_value = (sample_df, ['var1'])
            mock_create.return_value = mock_processor
            
            cache = InstrumentDataCache(context)
            result_df = cache.prepare_instrument('test_instrument')
            
            assert not result_df.empty
            assert cache.instrument_count == 1
            assert cache.get_instrument_variables('test_instrument') == ['var1']

    def test_cache_prepare_all(self):
        """Test preparing all instruments."""
        context = ProcessingContext(
            data_df=pd.DataFrame({'ptid': ['001']}),
            instrument_list=['inst1', 'inst2'],
            rules_cache={'inst1': {}, 'inst2': {}},
            primary_key_field='ptid',
            config=MagicMock()
        )
        
        with patch('src.pipeline.instrument_processors.InstrumentDataProcessor.create_processor') as mock_create:
            mock_processor = MagicMock()
            mock_processor.prepare_data.return_value = (pd.DataFrame({'ptid': ['001']}), [])
            mock_create.return_value = mock_processor
            
            cache = InstrumentDataCache(context)
            result = cache.prepare_all()
            
            assert len(result) == 2
            assert 'inst1' in result
            assert 'inst2' in result
            assert cache.instrument_count == 2

    def test_cache_get_methods(self):
        """Test cache getter methods."""
        context = ProcessingContext(
            data_df=pd.DataFrame(),
            instrument_list=[],
            rules_cache={},
            primary_key_field='ptid',
            config=MagicMock()
        )
        
        cache = InstrumentDataCache(context)
        
        # Test empty cache
        assert cache.get_instrument_data('unknown').empty
        assert cache.get_instrument_variables('unknown') == []
        assert cache.get_processor('unknown') is None


if __name__ == '__main__':
    pytest.main([__file__])
