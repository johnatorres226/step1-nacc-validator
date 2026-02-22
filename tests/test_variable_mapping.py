"""Tests for config/variable_instrument_mapping.json integrity."""

import json
from pathlib import Path

MAPPING_FILE = Path("config/variable_instrument_mapping.json")


class TestVariableMapping:
    """Validate the static variable-to-instrument mapping file."""

    def test_mapping_file_exists_and_is_valid(self):
        """File exists, is valid JSON, and parses to a dict."""
        assert MAPPING_FILE.exists(), "Mapping file missing"

        with open(MAPPING_FILE) as f:
            mapping = json.load(f)

        assert isinstance(mapping, dict), "Mapping should be a dict"

    def test_mapping_has_substantial_coverage(self):
        """Over 100 entries, all values are non-empty instrument name strings."""
        with open(MAPPING_FILE) as f:
            mapping = json.load(f)

        assert len(mapping) > 100, f"Expected >100 entries, got {len(mapping)}"

        for variable, instrument in mapping.items():
            assert isinstance(instrument, str) and instrument, (
                f"Bad instrument value for '{variable}': {instrument!r}"
            )

    def test_mapping_keys_are_sorted(self):
        """Keys are alphabetically sorted for maintenance."""
        with open(MAPPING_FILE) as f:
            mapping = json.load(f)

        keys = list(mapping.keys())
        assert keys == sorted(keys), "Mapping keys should be sorted alphabetically"
