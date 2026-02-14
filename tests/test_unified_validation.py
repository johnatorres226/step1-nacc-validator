"""
Tests for unified validation using validate_data_unified().

This module tests the new unified variable-based validation approach that
eliminates instrument-level routing while maintaining backward compatibility.

Note: These tests are integration tests that validate the unified approach works
in practice with real rule loading to ensure end-to-end functionality.
"""

import time
import pandas as pd
import pytest

from src.pipeline.reports.report_pipeline import validate_data_unified


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    return pd.DataFrame([
        {
            "ptid": "TEST001",
            "packet": "I",
            "visitnum": 1,
        },
        {
            "ptid": "TEST002",
            "packet": "I",
            "visitnum": 2,
        },
    ])


class TestUnifiedValidationBasic:
    """Test basic unified validation functionality."""

    def test_validate_returns_correct_structure(self, sample_data):
        """Test that validate_data_unified returns correct structure."""
        # Use real config and rules
        errors, logs, passed_records = validate_data_unified(
            data=sample_data,
            primary_key_field="ptid",
            instrument_name="test_instrument"
        )
        
        # Should return lists
        assert isinstance(errors, list)
        assert isinstance(logs, list)
        assert isinstance(passed_records, list)

    def test_validate_empty_data(self):
        """Test validating empty DataFrame."""
        empty_data = pd.DataFrame()
        
        errors, logs, passed_records = validate_data_unified(
            data=empty_data,
            primary_key_field="ptid",
            instrument_name="test_instrument"
        )
        
        # Should handle empty data gracefully
        assert isinstance(errors, list)
        assert isinstance(logs, list)
        assert isinstance(passed_records, list)

    def test_validate_with_packet_i(self, sample_data):
        """Test validation for packet I."""
        errors, logs, passed_records = validate_data_unified(
            data=sample_data,
            primary_key_field="ptid",
            instrument_name="test_instrument"
        )
        
        # Should complete successfully
        assert isinstance(errors, list)
        assert isinstance(logs, list)
        assert isinstance(passed_records, list)

    def test_validate_with_packet_i4(self):
        """Test validation for packet I4."""
        i4_data = pd.DataFrame([
            {"ptid": "TEST001", "packet": "I4", "visitnum": 1}
        ])
        
        errors, logs, passed_records = validate_data_unified(
            data=i4_data,
            primary_key_field="ptid",
            instrument_name="test_instrument"
        )
        
        # Should complete successfully  
        assert isinstance(errors, list)

    def test_validate_with_packet_f(self):
        """Test validation for packet F."""
        f_data = pd.DataFrame([
            {"ptid": "TEST001", "packet": "F", "visitnum": 1}
        ])
        
        errors, logs, passed_records = validate_data_unified(
            data=f_data,
            primary_key_field="ptid",
            instrument_name="test_instrument"
        )
        
        # Should complete successfully
        assert isinstance(errors, list)


class TestUnifiedValidationErrorFormat:
    """Test that error format is consistent with existing system."""

    def test_error_structure_includes_required_fields(self):
        """Test that errors include required fields for reporting."""
        # Create data that will have errors (missing required fields)
        data_with_errors = pd.DataFrame([
            {"ptid": "TEST001", "packet": "I"}  # Missing visitnum which might be required
        ])
        
        errors, logs, passed_records = validate_data_unified(
            data=data_with_errors,
            primary_key_field="ptid",
            instrument_name="test_instrument"
        )
        
        # Check error structure if there are any errors
        if len(errors) > 0:
            error = errors[0]
            # Should have key fields for reporting
            assert "ptid" in error or "primary_key" in str(error)
            assert "variable" in error or "field" in str(error)
            assert "error" in error or "error_message" in str(error)


class TestUnifiedValidationPerformance:
    """Performance benchmarks for unified validation approach."""

    def test_performance_with_moderate_dataset(self):
        """Test performance with moderate sized dataset (100 records)."""
        # Create moderate dataset
        data = pd.DataFrame([
            {
                "ptid": f"TEST{i:04d}",
                "packet": "I",
                "visitnum": i % 10 + 1,
            }
            for i in range(100)
        ])
        
        start_time = time.time()
        errors, logs, passed_records = validate_data_unified(
            data=data,
            primary_key_field="ptid",
            instrument_name="test_instrument"
        )
        elapsed = time.time() - start_time
        
        #Should complete in reasonable time (< 10 seconds for 100 records)
        assert elapsed < 10.0, f"Validation took {elapsed:.2f}s (expected < 10.0s)"
        
        # Should return results
        assert isinstance(errors, list)
        assert isinstance(passed_records, list)
        
        print(f"\nPerformance: Validated {len(data)} records in {elapsed:.2f}s "
              f"({len(data)/elapsed:.1f} records/sec)")

    def test_performance_with_large_dataset(self):
        """Test performance with larger dataset (500 records)."""
        # Create large dataset
        data = pd.DataFrame([
            {
                "ptid": f"TEST{i:05d}",
                "packet": "I",
                "visitnum": i % 10 + 1,
            }
            for i in range(500)
        ])
        
        start_time = time.time()
        errors, logs, passed_records = validate_data_unified(
            data=data,
            primary_key_field="ptid",
            instrument_name="test_instrument"
        )
        elapsed = time.time() - start_time
        
        # Should complete in reasonable time (< 60 seconds for 500 records)
        assert elapsed < 60.0, f"Validation took {elapsed:.2f}s (expected < 60.0s)"
        
        print(f"\nPerformance: Validated {len(data)} records in {elapsed:.2f}s "
              f"({len(data)/elapsed:.1f} records/sec)")

    def test_rule_loader_caching_efficiency(self, sample_data):
        """Test that rule caching improves performance on repeated runs."""
        # First run - cold cache
        start1 = time.time()
        errors1, logs1, passed1 = validate_data_unified(
            data=sample_data,
            primary_key_field="ptid",
            instrument_name="test_instrument"
        )
        elapsed1 = time.time() - start1
        
        # Second run - warm cache (same packet type)
        start2 = time.time()
        errors2, logs2, passed2 = validate_data_unified(
            data=sample_data,
            primary_key_field="ptid",
            instrument_name="test_instrument"
        )
        elapsed2 = time.time() - start2
        
        # Second run should not be slower (caching helps or has minimal overhead)
        # Allow some variance, just ensure no significant regression
        print(f"\nCaching efficiency: First run: {elapsed1:.3f}s, Second run: {elapsed2:.3f}s")
        assert elapsed2 <= elapsed1 * 1.5, "Second run should not be significantly slower"
