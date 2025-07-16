# tests/test_config_manager.py

import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Temporarily add src to path to allow for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pipeline import config_manager

@pytest.fixture(autouse=True)
def clear_singleton():
    """Fixture to automatically clear the config singleton before each test."""
    config_manager._config_instance = None

@pytest.fixture
def mock_env():
    """Fixture for mocking environment variables."""
    env_vars = {
        "REDCAP_API_TOKEN": "test_token",
        "REDCAP_API_URL": "https://test.url/api/",
        "PROJECT_ID": "123",
        "JSON_RULES_PATH": "config/json_rules",
        "OUTPUT_PATH": "output",
        "LOG_PATH": "logs",
        "MAX_WORKERS": "8",
        "TIMEOUT": "600",
        "RETRY_ATTEMPTS": "5",
        "GENERATE_HTML_REPORT": "false",
        "LOG_LEVEL": "DEBUG",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        yield

def test_qcconfig_loading_from_env(mock_env):
    """Test that QCConfig correctly loads settings from environment variables."""
    config = config_manager.QCConfig()
    assert config.redcap_api_token == "test_token"
    assert config.redcap_api_url == "https://test.url/api/"
    assert config.project_id == "123"
    assert config.max_workers == 8
    assert config.timeout == 600
    assert config.retry_attempts == 5
    assert config.generate_html_report is False
    assert config.log_level == "DEBUG"

def test_qcconfig_defaults():
    """Test that QCConfig uses default values when environment variables are not set."""
    with patch.dict(os.environ, {}, clear=True):
        config = config_manager.QCConfig()
        assert config.redcap_api_token is None
        assert config.max_workers == 4
        assert config.generate_html_report is True
        assert config.log_level == "INFO"

def test_qcconfig_validation_success(mock_env, tmp_path):
    """Test the validate method with a valid configuration."""
    # Create dummy directories for path validation
    (tmp_path / "config" / "json_rules").mkdir(parents=True)
    (tmp_path / "output").mkdir()
    (tmp_path / "logs").mkdir()

    with patch.dict(os.environ, {
        "REDCAP_API_TOKEN": "valid_token",
        "REDCAP_API_URL": "https://valid.url",
        "JSON_RULES_PATH": str(tmp_path / "config" / "json_rules"),
        "OUTPUT_PATH": str(tmp_path / "output"),
        "LOG_PATH": str(tmp_path / "logs"),
    }):
        config = config_manager.QCConfig()
        errors = config.validate()
        assert not errors

def test_qcconfig_validation_failure(tmp_path):
    """Test the validate method with an invalid configuration."""
    with patch.dict(os.environ, {
        "JSON_RULES_PATH": str(tmp_path / "non_existent_rules"),
        "MAX_WORKERS": "0", # Invalid
        "TIMEOUT": "10", # Invalid
    }, clear=True):
        config = config_manager.QCConfig()
        errors = config.validate()
        assert "REDCAP_API_TOKEN is required" in errors
        assert "REDCAP_API_URL is required" in errors
        assert f"JSON_RULES_PATH '{tmp_path / 'non_existent_rules'}' is not a valid directory." in errors
        assert "max_workers must be at least 1" in errors
        assert "timeout must be at least 30 seconds" in errors

def test_get_config_singleton(mock_env):
    """Test that get_config returns a singleton instance."""
    config1 = config_manager.get_config()
    config2 = config_manager.get_config()
    assert config1 is config2

def test_get_config_force_reload(mock_env):
    """Test that force_reload=True creates a new config instance."""
    config1 = config_manager.get_config()
    # Add required vars for validation to pass on reload
    with patch.dict(os.environ, {
        "REDCAP_API_TOKEN": "new_token",
        "REDCAP_API_URL": "https://new.url",
        "LOG_LEVEL": "WARNING"
    }):
        config2 = config_manager.get_config(force_reload=True)
    assert config1 is not config2
    assert config2.log_level == "WARNING"
    assert config2.redcap_api_token == "new_token"

def test_get_config_validation_exit(mock_env):
    """Test that get_config exits if validation fails."""
    # Unset a required env var
    with patch.dict(os.environ, {"REDCAP_API_TOKEN": ""}):
        with pytest.raises(SystemExit) as e:
            config_manager.get_config(force_reload=True)
        assert e.type == SystemExit
        assert e.value.code == 1

def test_dynamic_rule_helpers():
    """Test helper functions for dynamic rule selection."""
    assert config_manager.is_dynamic_rule_instrument("c2c2t_neuropsychological_battery_scores") is True
    assert config_manager.is_dynamic_rule_instrument("a1_participant_demographics") is False

    assert config_manager.get_discriminant_variable("c2c2t_neuropsychological_battery_scores") == "loc_c2_or_c2t"
    with pytest.raises(ValueError):
        config_manager.get_discriminant_variable("a1_participant_demographics")

    mappings = config_manager.get_rule_mappings("c2c2t_neuropsychological_battery_scores")
    assert mappings == {
        "C2": "c2_rules.json",
        "C2T": "c2t_rules.json"
    }
    with pytest.raises(ValueError):
        config_manager.get_rule_mappings("a1_participant_demographics")


def test_path_helper_functions(mock_env, tmp_path):
    """Test the helper functions that return Path objects."""
    rules_path = tmp_path / "rules"
    output_path = tmp_path / "out"
    rules_path.mkdir(parents=True) # Ensure directory exists
    output_path.mkdir(parents=True) # Ensure directory exists
    
    with patch.dict(os.environ, {
        "JSON_RULES_PATH": str(rules_path),
        "OUTPUT_PATH": str(output_path),
        # Add required vars for validation
        "REDCAP_API_TOKEN": "token",
        "REDCAP_API_URL": "https://url.com",
    }):
        config_manager.get_config(force_reload=True)
        assert config_manager.get_json_rules_path() == rules_path.resolve()
        assert config_manager.get_output_path() == output_path.resolve()

