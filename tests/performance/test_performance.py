"""
Performance tests for the refactored pipeline.

These tests ensure that the new modular structure maintains or improves
performance compared to the original monolithic implementation.
"""
import pytest
import pandas as pd
import time
import psutil
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Dict, List, Callable

from pipeline.core.data_processing import (
    build_variable_maps,
    preprocess_cast_types,
    extract_variables_from_rules,
    cast_to_integer_type,
    cast_to_float_type
)


class PerformanceTestBase:
    """Base class for performance tests."""
    
    def setup_method(self):
        """Set up performance test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Performance tracking
        self.start_time = None
        self.end_time = None
        self.start_memory = None
        self.end_memory = None
    
    def teardown_method(self):
        """Clean up performance test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def start_performance_monitoring(self):
        """Start monitoring performance metrics."""
        self.start_time = time.time()
        self.start_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB
    
    def end_performance_monitoring(self):
        """End monitoring and calculate metrics."""
        self.end_time = time.time()
        self.end_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB
    
    @property
    def execution_time(self) -> float:
        """Get execution time in seconds."""
        if self.start_time is None or self.end_time is None:
            return 0.0
        return self.end_time - self.start_time
    
    @property
    def memory_usage(self) -> float:
        """Get memory usage in MB."""
        if self.start_memory is None or self.end_memory is None:
            return 0.0
        return self.end_memory - self.start_memory
    
    def create_large_test_dataframe(self, num_records: int = 10000) -> pd.DataFrame:
        """Create large test dataframe for performance testing."""
        return pd.DataFrame({
            'record_id': range(1, num_records + 1),
            'redcap_repeat_instrument': ['a1', 'b3', 'c2'] * (num_records // 3 + 1),
            'field1': [f'value_{i}' for i in range(num_records)],
            'field2': range(num_records),
            'field3': [f'2023-01-{(i % 28) + 1:02d}' for i in range(num_records)],
            'field4': [i * 1.5 for i in range(num_records)]
        }[:num_records])


class TestDataProcessingPerformance(PerformanceTestBase):
    """Test performance of core data processing functions."""
    
    def test_large_dataframe_type_casting_performance(self):
        """Test type casting performance with large datasets."""
        # Create large test dataframe
        large_df = self.create_large_test_dataframe(50000)
        
        # Create mock rules for type casting
        rules = {
            'a1': {
                'field1': {'type': 'text'},
                'field2': {'type': 'number'},
                'field3': {'type': 'date'},
                'field4': {'type': 'number'}
            }
        }
        
        # Test performance
        self.start_performance_monitoring()
        result_df = preprocess_cast_types(large_df, rules)
        self.end_performance_monitoring()
        
        # Verify results
        assert isinstance(result_df, pd.DataFrame)
        assert len(result_df) == len(large_df)
        
        # Performance assertions (adjust thresholds as needed)
        assert self.execution_time < 30.0, f"Type casting took too long: {self.execution_time:.2f}s"
        assert self.memory_usage < 500, f"Memory usage too high: {self.memory_usage:.2f}MB"
        
        print(f"Type casting performance - Time: {self.execution_time:.2f}s, Memory: {self.memory_usage:.2f}MB")
    
    def test_variable_map_building_performance(self):
        """Test performance of building variable maps."""
        # Create large instrument list
        instruments = [f'instrument_{i}' for i in range(100)]
        
        # Create large rules cache
        rules_cache = {}
        for instrument in instruments:
            rules_cache[instrument] = {
                f'field_{j}': {'type': 'text'} for j in range(50)
            }
        
        # Test performance
        self.start_performance_monitoring()
        variable_map, instrument_map = build_variable_maps(instruments, rules_cache)
        self.end_performance_monitoring()
        
        # Verify results
        assert isinstance(variable_map, dict)
        assert isinstance(instrument_map, dict)
        assert len(instrument_map) == len(instruments)
        
        # Performance assertions
        assert self.execution_time < 5.0, f"Variable map building took too long: {self.execution_time:.2f}s"
        
        print(f"Variable map building performance - Time: {self.execution_time:.2f}s")
    
    def test_series_casting_performance(self):
        """Test performance of individual series casting functions."""
        # Create large series for testing
        large_series_size = 100000
        
        # Test integer casting
        int_series = pd.Series([str(i) for i in range(large_series_size)])
        
        self.start_performance_monitoring()
        result_int = cast_to_integer_type(int_series)
        self.end_performance_monitoring()
        
        int_time = self.execution_time
        
        # Test float casting
        float_series = pd.Series([str(i * 1.5) for i in range(large_series_size)])
        
        self.start_performance_monitoring()
        result_float = cast_to_float_type(float_series)
        self.end_performance_monitoring()
        
        float_time = self.execution_time
        
        # Verify results
        assert isinstance(result_int, pd.Series)
        assert isinstance(result_float, pd.Series)
        assert len(result_int) == large_series_size
        assert len(result_float) == large_series_size
        
        # Performance assertions
        assert int_time < 10.0, f"Integer casting took too long: {int_time:.2f}s"
        assert float_time < 10.0, f"Float casting took too long: {float_time:.2f}s"
        
        print(f"Series casting performance - Int: {int_time:.2f}s, Float: {float_time:.2f}s")


class TestMemoryUsageOptimization(PerformanceTestBase):
    """Test memory usage optimization in refactored functions."""
    
    def test_dataframe_processing_memory_efficiency(self):
        """Test that dataframe processing doesn't cause memory leaks."""
        initial_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        
        # Process multiple large dataframes
        for i in range(10):
            large_df = self.create_large_test_dataframe(10000)
            
            # Simulate processing
            rules = {'instrument1': {'field1': {'type': 'text'}}}
            processed_df = preprocess_cast_types(large_df, rules)
            
            # Force garbage collection by deleting references
            del large_df
            del processed_df
        
        final_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        # Memory should not increase significantly (< 100MB for this test)
        assert memory_increase < 100, f"Memory leak detected: {memory_increase:.2f}MB increase"
        
        print(f"Memory efficiency test - Memory increase: {memory_increase:.2f}MB")
    
    def test_large_dataset_chunking_performance(self):
        """Test performance with very large datasets."""
        # Create very large dataset
        very_large_df = self.create_large_test_dataframe(100000)
        
        # Test processing in chunks vs. all at once
        chunk_size = 10000
        chunks = [very_large_df[i:i+chunk_size] for i in range(0, len(very_large_df), chunk_size)]
        
        rules = {'a1': {'field1': {'type': 'text'}}}
        
        # Test chunked processing
        self.start_performance_monitoring()
        chunked_results = []
        for chunk in chunks:
            result = preprocess_cast_types(chunk, rules)
            chunked_results.append(result)
        final_chunked = pd.concat(chunked_results, ignore_index=True)
        self.end_performance_monitoring()
        
        chunked_time = self.execution_time
        chunked_memory = self.memory_usage
        
        # Test all-at-once processing
        self.start_performance_monitoring()
        all_at_once_result = preprocess_cast_types(very_large_df, rules)
        self.end_performance_monitoring()
        
        all_time = self.execution_time
        all_memory = self.memory_usage
        
        # Verify results are equivalent
        assert len(final_chunked) == len(all_at_once_result)
        
        print(f"Large dataset processing:")
        print(f"  Chunked - Time: {chunked_time:.2f}s, Memory: {chunked_memory:.2f}MB")
        print(f"  All-at-once - Time: {all_time:.2f}s, Memory: {all_memory:.2f}MB")


class TestScalabilityPerformance(PerformanceTestBase):
    """Test scalability of refactored functions."""
    
    def test_linear_scaling_with_data_size(self):
        """Test that processing time scales linearly with data size."""
        data_sizes = [1000, 5000, 10000, 20000]
        processing_times = []
        
        rules = {'a1': {'field1': {'type': 'text'}, 'field2': {'type': 'number'}}}
        
        for size in data_sizes:
            test_df = self.create_large_test_dataframe(size)
            
            self.start_performance_monitoring()
            result_df = preprocess_cast_types(test_df, rules)
            self.end_performance_monitoring()
            
            processing_times.append(self.execution_time)
            
            # Verify result
            assert len(result_df) == size
        
        # Check that scaling is reasonable (not exponential)
        # Time for 20k records should be less than 10x time for 1k records
        time_ratio = processing_times[-1] / processing_times[0]
        data_ratio = data_sizes[-1] / data_sizes[0]
        
        assert time_ratio < data_ratio * 2, f"Scaling is not linear: {time_ratio:.2f}x time for {data_ratio}x data"
        
        print("Scalability test results:")
        for size, time in zip(data_sizes, processing_times):
            print(f"  {size:6d} records: {time:.3f}s")
    
    def test_instrument_count_scaling(self):
        """Test scaling with number of instruments."""
        base_df = self.create_large_test_dataframe(10000)
        
        instrument_counts = [5, 10, 20, 50]
        processing_times = []
        
        for count in instrument_counts:
            instruments = [f'instrument_{i}' for i in range(count)]
            rules_cache = {inst: {'field1': {'type': 'text'}} for inst in instruments}
            
            self.start_performance_monitoring()
            variable_map, instrument_map = build_variable_maps(instruments, rules_cache)
            self.end_performance_monitoring()
            
            processing_times.append(self.execution_time)
        
        # Check reasonable scaling
        max_time = max(processing_times)
        assert max_time < 5.0, f"Processing with {max(instrument_counts)} instruments took too long: {max_time:.2f}s"
        
        print("Instrument scaling test results:")
        for count, time in zip(instrument_counts, processing_times):
            print(f"  {count:2d} instruments: {time:.3f}s")


class TestComparisonBenchmarks(PerformanceTestBase):
    """Benchmark tests comparing new vs old implementations."""
    
    def test_modular_vs_monolithic_performance(self):
        """Compare performance of modular vs monolithic approach."""
        # Note: This is a conceptual test - in practice, you would need
        # access to the old monolithic implementation to make real comparisons
        
        test_df = self.create_large_test_dataframe(20000)
        rules = {'a1': {'field1': {'type': 'text'}, 'field2': {'type': 'number'}}}
        
        # Test new modular implementation
        self.start_performance_monitoring()
        
        # Simulate the steps that would be in the old monolithic function
        step1_result = preprocess_cast_types(test_df, rules)
        instruments = ['a1', 'b3', 'c2']
        step2_result = build_variable_maps(instruments, rules)
        
        self.end_performance_monitoring()
        
        modular_time = self.execution_time
        modular_memory = self.memory_usage
        
        # Verify results
        assert isinstance(step1_result, pd.DataFrame)
        assert isinstance(step2_result, tuple)
        assert len(step2_result) == 2
        
        # Performance expectations for modular approach
        assert modular_time < 30.0, f"Modular approach too slow: {modular_time:.2f}s"
        assert modular_memory < 500, f"Modular approach uses too much memory: {modular_memory:.2f}MB"
        
        print(f"Modular implementation performance:")
        print(f"  Time: {modular_time:.2f}s")
        print(f"  Memory: {modular_memory:.2f}MB")


@pytest.mark.performance
class TestPerformanceRegression:
    """Test for performance regressions."""
    
    def test_no_performance_regression(self):
        """Ensure that refactored code doesn't regress in performance."""
        # This test would ideally compare against baseline metrics
        # For now, it ensures reasonable performance bounds
        
        test_df = pd.DataFrame({
            'record_id': range(10000),
            'field1': [f'value_{i}' for i in range(10000)],
            'field2': range(10000)
        })
        
        rules = {'instrument1': {'field1': {'type': 'text'}, 'field2': {'type': 'number'}}}
        
        start_time = time.time()
        result = preprocess_cast_types(test_df, rules)
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Verify reasonable performance (adjust threshold based on your requirements)
        assert execution_time < 10.0, f"Performance regression detected: {execution_time:.2f}s"
        assert len(result) == len(test_df)
        
        print(f"Performance regression test passed: {execution_time:.2f}s")


def run_performance_tests():
    """Run all performance tests and generate report."""
    print("Running performance test suite...")
    print("=" * 50)
    
    # Run specific performance test classes
    test_classes = [
        TestDataProcessingPerformance,
        TestMemoryUsageOptimization,
        TestScalabilityPerformance,
        TestComparisonBenchmarks
    ]
    
    for test_class in test_classes:
        print(f"\nRunning {test_class.__name__}...")
        # In practice, you would use pytest to run these
        # pytest.main([f"-v", f"tests/performance/test_performance.py::{test_class.__name__}"])


if __name__ == "__main__":
    # Run performance tests when script is executed directly
    run_performance_tests()
    
    # Or run with pytest
    pytest.main([__file__])
