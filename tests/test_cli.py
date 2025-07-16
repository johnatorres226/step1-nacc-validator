# tests/test_cli.py

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from pathlib import Path
import json

# Temporarily add src to path to allow for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cli.cli import cli
from pipeline import config_manager

@pytest.fixture
def runner():
    """Fixture for invoking command-line calls."""
    return CliRunner()

@pytest.fixture
def mock_config(tmp_path):
    """Fixture for a mocked QCConfig object."""
    # Create dummy directories for the mock config
    (tmp_path / "rules").mkdir()
    (tmp_path / "output").mkdir()

    with patch('cli.cli.get_config') as mock_get_config:
        config_instance = MagicMock()
        config_instance.validate.return_value = []  # Assume valid config by default
        config_instance.redcap_api_token = "fake_token"
        config_instance.redcap_api_url = "https://fake.url/api/"
        config_instance.output_path = str(tmp_path / "output")
        config_instance.json_rules_path = str(tmp_path / "rules")
        config_instance.log_level = "INFO"
        config_instance.events = []
        config_instance.ptid_list = []
        config_instance.user_initials = "TEST"
        config_instance.mode = "complete_visits"
        config_instance.include_qced = False
        
        mock_get_config.return_value = config_instance
        yield config_instance

# ==================================================================
# Tests for the 'config' command
# ==================================================================

def test_config_command_valid(runner, mock_config):
    """Test the 'config' command with a valid configuration."""
    with patch('pathlib.Path.exists', return_value=True):
        result = runner.invoke(cli, ['config'])
        assert result.exit_code == 0
        assert "All systems ready for QC validation!" in result.output
        assert "✅ Ready" in result.output

def test_config_command_invalid(runner, mock_config):
    """Test the 'config' command with an invalid configuration."""
    mock_config.validate.return_value = ["REDCAP_API_TOKEN is missing"]
    with patch('pathlib.Path.exists', return_value=False):
        result = runner.invoke(cli, ['config'])
        assert result.exit_code == 0
        assert "Configuration issues detected" in result.output
        assert "❌ Issues Found" in result.output
        assert "REDCAP_API_TOKEN is missing" in result.output

def test_config_command_json_output(runner, mock_config):
    """Test the 'config' command with --json-output."""
    mock_config.validate.return_value = []
    with patch('pathlib.Path.exists', return_value=True):
        result = runner.invoke(cli, ['config', '--json-output'])
        assert result.exit_code == 0
        # Find the start of the JSON output
        json_start = result.output.find('{')
        assert json_start != -1
        json_data = json.loads(result.output[json_start:])
        assert json_data['valid'] is True

# ==================================================================
# Tests for the 'run' command
# ==================================================================

@patch('cli.cli.run_report_pipeline')
def test_run_command_success(mock_run_pipeline, runner, mock_config):
    """Test the 'run' command in a successful scenario."""
    result = runner.invoke(cli, ['run', '--mode', 'complete_visits'], input='JD\n')
    assert result.exit_code == 0
    assert "Running QC pipeline in 'complete_visits' mode." in result.output
    assert "QC Run Complete!" in result.output
    mock_run_pipeline.assert_called_once()
    # Check that user initials were set
    assert mock_config.user_initials == "JD"

def test_run_command_config_failure(runner, mock_config):
    """Test that the 'run' command exits if configuration is invalid."""
    mock_config.validate.return_value = ["Something is wrong"]
    result = runner.invoke(cli, ['run', '--mode', 'complete_visits'])
    assert result.exit_code == 0 # The command itself doesn't exit with error, it prints errors
    assert "Configuration errors detected" in result.output
    assert "Something is wrong" in result.output

@patch('cli.cli.run_report_pipeline')
def test_run_command_with_overrides(mock_run_pipeline, runner, mock_config):
    """Test the 'run' command with CLI option overrides."""
    result = runner.invoke(cli, [
        'run',
        '--mode', 'custom',
        '--output-dir', '/new/output',
        '--event', 'visit_1',
        '--ptid', '12345',
        '--include-qced'
    ], input='TEST\n')

    assert result.exit_code == 0
    mock_run_pipeline.assert_called_once()
    
    # Verify that the config object was updated correctly
    # Use Path to create a platform-agnostic path for comparison
    assert mock_config.output_path == str(Path('/new/output').resolve())
    assert mock_config.events == ['visit_1']
    assert mock_config.ptid_list == ['12345']
    assert mock_config.include_qced is True
    assert mock_config.mode == 'custom'

@patch('cli.cli.run_report_pipeline', side_effect=Exception("Pipeline Error"))
def test_run_command_pipeline_exception(mock_run_pipeline, runner, mock_config):
    """Test the 'run' command when the pipeline raises an exception."""
    result = runner.invoke(cli, ['run', '--mode', 'all_incomplete_visits'], input='ERR\n')
    assert result.exit_code == 1
    assert "An error occurred. See logs for details." in result.output
    mock_run_pipeline.assert_called_once()
