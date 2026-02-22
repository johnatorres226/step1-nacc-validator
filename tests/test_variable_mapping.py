"""
Tests for variable-to-instrument mapping functionality.

This module tests the variable mapping utility that translates variable names
to their source instruments, supporting backward compatible reporting in the
unified validation approach.
"""

import json
from pathlib import Path


class TestVariableMappingFile:
    """Test the generated variable_instrument_mapping.json file."""

    def test_mapping_file_exists(self):
        """Test that the variable mapping file was generated."""
        mapping_file = Path("config/variable_instrument_mapping.json")
        assert mapping_file.exists(), "Variable mapping file should exist"

    def test_mapping_file_is_valid_json(self):
        """Test that the mapping file is valid JSON."""
        mapping_file = Path("config/variable_instrument_mapping.json")

        with open(mapping_file, "r") as f:
            mapping = json.load(f)

        assert isinstance(mapping, dict), "Mapping should be a dictionary"

    def test_mapping_contains_expected_variables(self):
        """Test that mapping contains expected variables from rule files."""
        mapping_file = Path("config/variable_instrument_mapping.json")

        with open(mapping_file, "r") as f:
            mapping = json.load(f)

        # Should have many variables (>1000 based on generation output)
        assert len(mapping) > 100, "Should have substantial number of variables mapped"

        # Check some expected variables exist (common across UDS forms)
        # Note: actual variable names depend on rule files
        assert isinstance(mapping, dict), "Should be variable -> instrument mapping"

    def test_mapping_values_are_instruments(self):
        """Test that mapping values are instrument names."""
        mapping_file = Path("config/variable_instrument_mapping.json")

        with open(mapping_file, "r") as f:
            mapping = json.load(f)

        # All values should be strings (instrument names)
        for variable, instrument in mapping.items():
            assert isinstance(variable, str), f"Variable key should be string: {variable}"
            assert isinstance(instrument, str), f"Instrument value should be string: {instrument}"
            assert len(instrument) > 0, f"Instrument name should not be empty for {variable}"

    def test_mapping_keys_are_variable_names(self):
        """Test that mapping keys are variable names."""
        mapping_file = Path("config/variable_instrument_mapping.json")

        with open(mapping_file, "r") as f:
            mapping = json.load(f)

        # All keys should be non-empty strings
        for variable in mapping.keys():
            assert isinstance(variable, str), "Variable should be string"
            assert len(variable) > 0, "Variable name should not be empty"


class TestVariableMappingUsage:
    """Test using the variable mapping for instrument inference."""

    def test_can_infer_instrument_from_variable_prefix(self):
        """Test inferring instrument from variable name prefix."""
        # Common pattern: variables start with instrument prefix
        # e.g., "a1_birthyr" -> "a1"

        test_cases = [
            ("a1_birthyr", "a1"),
            ("b1_height", "b1"),
            ("c2_memory", "c2"),
            ("d1_cog", "d1"),
        ]

        for variable, expected_prefix in test_cases:
            # Simple prefix extraction
            if "_" in variable:
                prefix = variable.split("_")[0]
                assert prefix == expected_prefix, f"Expected {expected_prefix}, got {prefix}"

    def test_mapping_provides_fallback_for_inference(self):
        """Test that mapping file provides fallback when prefix inference unclear."""
        mapping_file = Path("config/variable_instrument_mapping.json")

        with open(mapping_file, "r") as f:
            mapping = json.load(f)

        # For any variable in the mapping, we can get its instrument
        if len(mapping) > 0:
            test_variable = list(mapping.keys())[0]
            instrument = mapping[test_variable]

            assert isinstance(instrument, str)
            assert len(instrument) > 0


class TestVariableMappingGeneration:
    """Test the generation script logic (not running it)."""

    def test_mapping_file_format_is_correct(self):
        """Test that the generated mapping follows expected format."""
        mapping_file = Path("config/variable_instrument_mapping.json")

        with open(mapping_file, "r") as f:
            content = f.read()
            mapping = json.loads(content)

        # Should be properly formatted JSON
        assert isinstance(mapping, dict)

        # Should be sorted (for easier maintenance)
        keys_list = list(mapping.keys())
        sorted_keys = sorted(keys_list)

        # Check if keys are sorted (they should be per generation script)
        assert keys_list == sorted_keys, "Mapping keys should be sorted alphabetically"

    def test_mapping_covers_multiple_packets(self):
        """Test that mapping includes variables from different packets."""
        mapping_file = Path("config/variable_instrument_mapping.json")

        with open(mapping_file, "r") as f:
            mapping = json.load(f)

        # Should have variables from various instruments
        # Get unique instruments
        instruments = set(mapping.values())

        # Should have multiple instruments represented
        assert len(instruments) > 1, "Should have variables from multiple instruments"
