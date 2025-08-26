# tests/test_helpers.py

import pytest
import json
import pandas as pd
import warnings
from pathlib import Path
from unittest.mock import patch

# Temporarily add src to path to allow for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pipeline import helpers
from pipeline.config_manager import get_config

# ==================================================================
# Fixtures
# ==================================================================

@pytest.fixture
def mock_rules_dir(tmp_path):
    """Creates a temporary directory with mock JSON rule files."""
    rules_dir = tmp_path / "json_rules"
    rules_dir.mkdir()
    
    # Standard instrument rule file
    with open(rules_dir / "a1_rules.json", "w") as f:
        json.dump({"SEX": {"type": "integer", "allowed": [1, 2]}}, f)
        
    # Dynamic instrument rule files
    with open(rules_dir / "c2_rules.json", "w") as f:
        json.dump({"MINTTOTS": {"type": "integer", "min": 0, "max": 30}}, f)
    with open(rules_dir / "c2t_rules.json", "w") as f:
        json.dump({"MINTTOTS": {"type": "integer", "min": 0, "max": 40}}, f)
        
    # File with invalid JSON
    with open(rules_dir / "bad_rules.json", "w") as f:
        f.write("{'invalid_json': True,}")
        
    return rules_dir

@pytest.fixture
def mock_config_with_rules(mock_rules_dir):
    """Mocks the config to point to the temporary rules directory."""
    # Temporarily mock environment variables to prevent SystemExit
    with patch.dict('os.environ', {
        'REDCAP_API_TOKEN': 'test_token',
        'REDCAP_API_URL': 'https://test.url'
    }):
        config = get_config(force_reload=True)
        config.json_rules_path = str(mock_rules_dir)
        # Mock the instrument mapping to use our test files
        config.instrument_json_mapping.update({
            "a1_participant_demographics": ["a1_rules.json"],
            "c2c2t_neuropsychological_battery_scores": ["c2_rules.json", "c2t_rules.json"],
            "bad_instrument": ["bad_rules.json"],
            "missing_instrument": ["non_existent_file.json"]
        })
        yield config

# ==================================================================
# Tests for Rule Loading
# ==================================================================

def test_load_json_rules_for_instrument_success(mock_config_with_rules):
    """Test loading rules for a standard instrument."""
    rules = helpers.load_json_rules_for_instrument("a1_participant_demographics")
    assert "SEX" in rules
    assert rules["SEX"]["allowed"] == [1, 2]

def test_load_json_rules_for_dynamic_instrument(mock_config_with_rules):
    """Test that loading rules for a dynamic instrument merges them correctly."""
    # Note: load_json_rules_for_instrument is for standard loading,
    # dynamic instruments have their own loader, but this shows the base loader works.
    rules = helpers.load_json_rules_for_instrument("c2c2t_neuropsychological_battery_scores")
    assert "MINTTOTS" in rules
    assert rules["MINTTOTS"]["max"] == 40 # c2t_rules.json should overwrite c2_rules.json

def test_load_rules_file_not_found(mock_config_with_rules):
    """Test that empty rules are returned if a rule file is not found."""
    rules = helpers.load_json_rules_for_instrument("missing_instrument")
    assert not rules  # Should return empty dict for missing files

def test_load_rules_invalid_json(mock_config_with_rules):
    """Test that empty rules are returned for invalid JSON."""
    rules = helpers.load_json_rules_for_instrument("bad_instrument")
    assert not rules  # Should return empty dict for invalid JSON

# ==================================================================
# Tests for Vectorized Checks
# ==================================================================

@pytest.fixture
def sample_data():
    """Sample DataFrame for testing vectorized checks."""
    data = {
        'ptid': [1, 2, 3, 4, 5],
        'redcap_event_name': ['v1', 'v1', 'v1', 'v1', 'v1'],
        'AGE': [25, 99, 50, 30, 40], # 99 is out of range
        'SEX': [1, 3, 2, 1, 9], # 3 and 9 are not allowed
        'POSTAL': ['12345', 'abc', '54321-1234', '1234', '98765'] # abc and 1234 fail regex
    }
    return pd.DataFrame(data)

def test_run_vectorized_simple_checks(sample_data):
    """Test the deprecated _run_vectorized_simple_checks function."""
    rules = {
        'AGE': {'type': 'integer', 'min': 18, 'max': 90},
        'SEX': {'type': 'integer', 'allowed': [1, 2]},
        'POSTAL': {'type': 'string', 'regex': r'^\d{5}(-\d{4})?$'}
    }
    
    # Test that the deprecated function still works but doesn't perform validation
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        errors, passed_df = helpers._run_vectorized_simple_checks(sample_data, rules, "test_instrument")
        
        # Check that deprecation warning is raised
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "deprecated" in str(w[0].message)
    
    # Function should return empty errors and the original DataFrame
    assert len(errors) == 0  # No validation performed
    assert len(passed_df) == len(sample_data)  # All data passed through
    assert passed_df.equals(sample_data)  # Data unchanged
