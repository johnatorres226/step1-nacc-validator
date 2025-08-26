"""
Performance tests for complete visits logic optimization.

Tests comparing the optimized vectorized version vs the legacy nested loops version
of build_complete_visits_df to verify performance improvements.
"""

import pytest
import pandas as pd
import numpy as np
import time
from typing import List, Tuple
from unittest.mock import patch

from src.pipeline.helpers import (
    build_complete_visits_df,
    build_complete_visits_df_legacy
)


class TestCompleteVisitsPerformance:
    """Performance comparison tests for complete visits logic."""
    
    @pytest.fixture
    def small_dataset(self):
        """Create a small dataset for basic functionality tests."""
        np.random.seed(42)  # For reproducible results
        
        data = {
            'ptid': ['001', '002', '003'] * 20,  # 60 records
            'redcap_event_name': ['v1', 'v2', 'v3'] * 20,
            'a1_complete': np.random.choice(['0', '1', '2'], size=60),
            'b1_complete': np.random.choice(['0', '1', '2'], size=60),
            'c1_complete': np.random.choice(['0', '1', '2'], size=60),
        }
        
        # Ensure some visits are complete for testing
        # Make the first 3 records (different ptids, same event) complete
        for i in range(3):
            data['a1_complete'][i] = '2'
            data['b1_complete'][i] = '2'
            data['c1_complete'][i] = '2'
        
        return pd.DataFrame(data)
    
    @pytest.fixture
    def medium_dataset(self):
        """Create a medium dataset for performance testing."""
        np.random.seed(42)
        
        n_subjects = 100
        n_events = 5
        n_records = n_subjects * n_events
        
        data = {
            'ptid': [f'{i:03d}' for i in range(n_subjects)] * n_events,
            'redcap_event_name': [f'v{j+1}' for j in range(n_events)] * n_subjects,
            'a1_complete': np.random.choice(['0', '1', '2'], size=n_records, p=[0.2, 0.3, 0.5]),
            'b1_complete': np.random.choice(['0', '1', '2'], size=n_records, p=[0.2, 0.3, 0.5]),
            'c1_complete': np.random.choice(['0', '1', '2'], size=n_records, p=[0.2, 0.3, 0.5]),
            'd1_complete': np.random.choice(['0', '1', '2'], size=n_records, p=[0.2, 0.3, 0.5]),
            'e1_complete': np.random.choice(['0', '1', '2'], size=n_records, p=[0.2, 0.3, 0.5]),
        }
        
        # Ensure some complete visits
        complete_indices = np.random.choice(n_records, size=n_records//10, replace=False)
        for col in ['a1_complete', 'b1_complete', 'c1_complete', 'd1_complete', 'e1_complete']:
            data[col] = np.array(data[col])
            data[col][complete_indices] = '2'
        
        return pd.DataFrame(data)
    
    @pytest.fixture
    def large_dataset(self):
        """Create a large dataset for stress testing."""
        np.random.seed(42)
        
        n_subjects = 1000
        n_events = 10
        n_records = n_subjects * n_events
        
        instruments = ['a1', 'b1', 'c1', 'd1', 'e1', 'f1', 'g1', 'h1', 'i1', 'j1']
        
        data = {
            'ptid': [f'{i:04d}' for i in range(n_subjects)] * n_events,
            'redcap_event_name': [f'event_{j+1}' for j in range(n_events)] * n_subjects,
        }
        
        # Add completion columns
        for instrument in instruments:
            data[f'{instrument}_complete'] = np.random.choice(
                ['0', '1', '2'], 
                size=n_records, 
                p=[0.3, 0.2, 0.5]
            ).tolist()
        
        # Ensure some complete visits
        complete_indices = np.random.choice(n_records, size=n_records//20, replace=False)
        for instrument in instruments:
            col = f'{instrument}_complete'
            col_array = np.array(data[col])
            col_array[complete_indices] = '2'
            data[col] = col_array.tolist()
        
        return pd.DataFrame(data), instruments
    
    @patch('src.pipeline.helpers.get_config')
    def test_functionality_equivalence_small(self, mock_get_config, small_dataset):
        """Test that optimized and legacy versions produce equivalent results on small data."""
        mock_config = type('Config', (), {'primary_key_field': 'ptid'})()
        mock_get_config.return_value = mock_config
        
        instruments = ['a1', 'b1', 'c1']
        
        # Run both versions
        optimized_df, optimized_tuples = build_complete_visits_df(small_dataset, instruments)
        legacy_df, legacy_tuples = build_complete_visits_df_legacy(small_dataset, instruments)
        
        # Compare results
        assert len(optimized_df) == len(legacy_df), "Different number of complete visits found"
        assert set(optimized_tuples) == set(legacy_tuples), "Different complete visit tuples found"
        
        # Compare DataFrame content (sorting for consistent comparison)
        if len(optimized_df) > 0 and len(legacy_df) > 0:
            optimized_sorted = optimized_df.sort_values(['ptid', 'redcap_event_name']).reset_index(drop=True)
            legacy_sorted = legacy_df.sort_values(['ptid', 'redcap_event_name']).reset_index(drop=True)
            
            pd.testing.assert_frame_equal(optimized_sorted, legacy_sorted)
        else:
            # Both should be empty
            assert len(optimized_df) == 0 and len(legacy_df) == 0
    
    @patch('src.pipeline.helpers.get_config')
    def test_functionality_equivalence_medium(self, mock_get_config, medium_dataset):
        """Test that optimized and legacy versions produce equivalent results on medium data."""
        mock_config = type('Config', (), {'primary_key_field': 'ptid'})()
        mock_get_config.return_value = mock_config
        
        instruments = ['a1', 'b1', 'c1', 'd1', 'e1']
        
        # Run both versions
        optimized_df, optimized_tuples = build_complete_visits_df(medium_dataset, instruments)
        legacy_df, legacy_tuples = build_complete_visits_df_legacy(medium_dataset, instruments)
        
        # Compare results
        assert len(optimized_df) == len(legacy_df)
        assert set(optimized_tuples) == set(legacy_tuples)
    
    @patch('src.pipeline.helpers.get_config')
    def test_performance_comparison_medium(self, mock_get_config, medium_dataset):
        """Compare performance on medium dataset."""
        mock_config = type('Config', (), {'primary_key_field': 'ptid'})()
        mock_get_config.return_value = mock_config
        
        instruments = ['a1', 'b1', 'c1', 'd1', 'e1']
        
        # Time optimized version
        start_time = time.time()
        optimized_df, optimized_tuples = build_complete_visits_df(medium_dataset, instruments)
        optimized_time = time.time() - start_time
        
        # Time legacy version
        start_time = time.time()
        legacy_df, legacy_tuples = build_complete_visits_df_legacy(medium_dataset, instruments)
        legacy_time = time.time() - start_time
        
        # Verify results are equivalent
        assert len(optimized_df) == len(legacy_df)
        assert set(optimized_tuples) == set(legacy_tuples)
        
        # Log performance comparison
        print(f"\\n--- Performance Comparison (Medium Dataset: {len(medium_dataset)} records) ---")
        print(f"Optimized version: {optimized_time:.4f} seconds")
        print(f"Legacy version: {legacy_time:.4f} seconds")
        print(f"Performance improvement: {legacy_time / optimized_time:.2f}x faster")
        
        # The optimized version should be faster (allowing some margin for small datasets)
        assert optimized_time <= legacy_time * 1.1, f"Optimized version should be faster: {optimized_time} vs {legacy_time}"
    
    @patch('src.pipeline.helpers.get_config')
    def test_performance_stress_test(self, mock_get_config, large_dataset):
        """Stress test performance on large dataset."""
        large_df, instruments = large_dataset
        mock_config = type('Config', (), {'primary_key_field': 'ptid'})()
        mock_get_config.return_value = mock_config
        
        print(f"\\n--- Stress Test (Large Dataset: {len(large_df)} records, {len(instruments)} instruments) ---")
        
        # Time optimized version
        start_time = time.time()
        optimized_df, optimized_tuples = build_complete_visits_df(large_df, instruments)
        optimized_time = time.time() - start_time
        
        print(f"Optimized version: {optimized_time:.4f} seconds")
        print(f"Complete visits found: {len(optimized_df)}")
        
        # For large datasets, we only test the optimized version due to performance
        # The legacy version would take too long for practical testing
        
        # Verify reasonable performance (should complete in under 5 seconds for 10k records)
        assert optimized_time < 5.0, f"Optimized version took too long: {optimized_time} seconds"
        
        # Verify results are reasonable
        assert isinstance(optimized_df, pd.DataFrame)
        assert isinstance(optimized_tuples, list)
        assert len(optimized_tuples) == len(optimized_df)
    
    @patch('src.pipeline.helpers.get_config')
    def test_edge_cases(self, mock_get_config):
        """Test edge cases for both versions."""
        mock_config = type('Config', (), {'primary_key_field': 'ptid'})()
        mock_get_config.return_value = mock_config
        
        # Empty DataFrame
        empty_df = pd.DataFrame()
        instruments = ['a1', 'b1']
        
        optimized_result = build_complete_visits_df(empty_df, instruments)
        legacy_result = build_complete_visits_df_legacy(empty_df, instruments)
        
        assert optimized_result == (pd.DataFrame().empty and [], [])
        assert legacy_result == (pd.DataFrame().empty and [], [])
        
        # DataFrame with no complete visits
        no_complete_df = pd.DataFrame({
            'ptid': ['001', '002'],
            'redcap_event_name': ['v1', 'v1'],
            'a1_complete': ['0', '1'],
            'b1_complete': ['1', '0']
        })
        
        optimized_df, optimized_tuples = build_complete_visits_df(no_complete_df, instruments)
        legacy_df, legacy_tuples = build_complete_visits_df_legacy(no_complete_df, instruments)
        
        assert len(optimized_df) == 0
        assert len(legacy_df) == 0
        assert optimized_tuples == []
        assert legacy_tuples == []
    
    @patch('src.pipeline.helpers.get_config')
    def test_missing_completion_columns(self, mock_get_config):
        """Test handling of missing completion columns."""
        mock_config = type('Config', (), {'primary_key_field': 'ptid'})()
        mock_get_config.return_value = mock_config
        
        # DataFrame missing some completion columns
        incomplete_df = pd.DataFrame({
            'ptid': ['001', '002'],
            'redcap_event_name': ['v1', 'v1'],
            'a1_complete': ['2', '2'],
            # Missing b1_complete column
        })
        
        instruments = ['a1', 'b1']
        
        # Both versions should handle this gracefully
        optimized_df, optimized_tuples = build_complete_visits_df(incomplete_df, instruments)
        legacy_df, legacy_tuples = build_complete_visits_df_legacy(incomplete_df, instruments)
        
        # Should find no complete visits (since b1_complete is missing/defaulted to '0')
        assert len(optimized_df) == 0
        assert len(legacy_df) == 0
        assert optimized_tuples == []
        assert legacy_tuples == []
    
    def test_benchmarking_report(self, small_dataset, medium_dataset):
        """Generate a benchmarking report for documentation."""
        mock_config = type('Config', (), {'primary_key_field': 'ptid'})()
        
        with patch('src.pipeline.helpers.get_config', return_value=mock_config):
            print("\\n" + "="*60)
            print("COMPLETE VISITS OPTIMIZATION BENCHMARKING REPORT")
            print("="*60)
            
            datasets = [
                ("Small (60 records)", small_dataset, ['a1', 'b1', 'c1']),
                ("Medium (500 records)", medium_dataset, ['a1', 'b1', 'c1', 'd1', 'e1'])
            ]
            
            for dataset_name, df, instruments in datasets:
                print(f"\\n{dataset_name}:")
                print(f"  Records: {len(df)}")
                print(f"  Instruments: {len(instruments)}")
                
                # Time optimized version
                start_time = time.time()
                opt_df, opt_tuples = build_complete_visits_df(df, instruments)
                opt_time = time.time() - start_time
                
                # Time legacy version
                start_time = time.time()
                leg_df, leg_tuples = build_complete_visits_df_legacy(df, instruments)
                leg_time = time.time() - start_time
                
                speedup = leg_time / opt_time if opt_time > 0 else float('inf')
                
                print(f"  Optimized: {opt_time:.6f}s")
                print(f"  Legacy:    {leg_time:.6f}s")
                print(f"  Speedup:   {speedup:.2f}x")
                print(f"  Complete visits found: {len(opt_df)}")
            
            print("\\n" + "="*60)
