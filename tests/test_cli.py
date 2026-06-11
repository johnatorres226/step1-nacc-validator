"""Tests for the Click command-line interface (argument parsing, help, config status)."""

import json

from click.testing import CliRunner

from src.cli.cli import cli


class TestCli:
    """CLI invocation tests that never reach the pipeline or REDCap API."""

    def test_no_args_shows_help(self):
        result = CliRunner().invoke(cli, [])
        # click 8.1 exits 0 with no_args_is_help; click >= 8.2 exits 2
        assert result.exit_code in (0, 2)
        assert "Usage:" in result.output

    def test_help_lists_commands_and_options(self):
        result = CliRunner().invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "config" in result.output
        assert "--mode" in result.output
        assert "--initials" in result.output

    def test_run_without_initials_fails(self):
        result = CliRunner().invoke(cli, ["--mode", "errors-only"])
        assert result.exit_code == 2
        assert "initials" in result.output.lower()

    def test_invalid_mode_fails(self):
        result = CliRunner().invoke(cli, ["--mode", "not-a-mode"])
        assert result.exit_code == 2

    def test_config_json_output_schema(self):
        # COLUMNS keeps Rich from wrapping long JSON lines to terminal width
        result = CliRunner().invoke(cli, ["config", "--json-output"], env={"COLUMNS": "500"})
        assert result.exit_code == 0
        # When .env is unconfigured, get_config prints errors before the JSON
        status = json.loads(result.output[result.output.index("{") :])
        assert set(status) == {
            "valid",
            "errors",
            "redcap_configured",
            "output_path_exists",
            "packet_rules_configured",
        }
