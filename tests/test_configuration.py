"""Tests for QCConfig creation, serialization, environment loading, and robustness."""

import importlib
import json
import os
import tempfile
from unittest.mock import patch

import pytest

from src.pipeline.config.config_manager import OutputMode, QCConfig, get_config


class TestQCConfig:
    """All configuration tests in a single flat class."""

    def test_creation_with_defaults(self):
        config = QCConfig()
        assert isinstance(config.instruments, list)
        assert isinstance(config.events, list)

    def test_creation_with_custom_values(self):
        config = QCConfig(
            instruments=["test_instrument"],
            api_token="tok_123",
            api_url="https://test.redcap.url",
        )
        assert config.instruments == ["test_instrument"]
        assert config.api_token == "tok_123"
        assert config.api_url == "https://test.redcap.url"

    @patch.dict(
        os.environ,
        {
            "REDCAP_API_TOKEN": "env_token_123",
            "REDCAP_API_URL": "https://env.redcap.url",
            "PROJECT_ID": "env_project_123",
            "OUTPUT_PATH": "/tmp/env_output",
        },
    )
    def test_environment_variable_loading(self):
        import src.pipeline.config.config_manager

        importlib.reload(src.pipeline.config.config_manager)
        from src.pipeline.config.config_manager import QCConfig as ReloadedQCConfig

        config = ReloadedQCConfig()
        assert config.api_token == "env_token_123"
        assert config.api_url == "https://env.redcap.url"
        assert config.project_id == "env_project_123"
        assert config.output_path.endswith("env_output")

    def test_to_dict(self):
        config = QCConfig(api_token="test_token", instruments=["test_instrument"])
        d = config.to_dict()
        assert d["api_token"] == "test_token"
        assert d["instruments"] == ["test_instrument"]

    def test_roundtrip_to_file_and_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name
        try:
            original = QCConfig(api_token="file_test_token", instruments=["file_test_instrument"])
            original.to_file(temp_path)
            loaded = QCConfig.from_file(temp_path)
            assert loaded.api_token == original.api_token
            assert loaded.instruments == original.instruments
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_get_config_returns_qc_config(self):
        config = get_config()
        assert type(config).__name__ == "QCConfig"
        assert hasattr(config, "instruments")

    @patch("src.pipeline.config.config_manager._config_instance", None)
    def test_get_config_creates_new_instance(self):
        assert type(get_config()).__name__ == "QCConfig"

    def test_get_rules_path_for_packet(self):
        config = QCConfig()
        if hasattr(config, "get_rules_path_for_packet"):
            for packet in ["I", "I4", "F"]:
                path = config.get_rules_path_for_packet(packet)
                assert isinstance(path, str) or path is None

    def test_handles_invalid_json_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json content {")
            temp_path = f.name
        try:
            with pytest.raises((json.JSONDecodeError, ValueError)):
                QCConfig.from_file(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_handles_nonexistent_file(self):
        config = QCConfig.from_file("/path/that/does/not/exist.json")
        assert isinstance(config, QCConfig)

    def test_output_mode_default_is_errors_only(self):
        config = QCConfig()
        assert config.output_mode == OutputMode.ERRORS_ONLY

    def test_output_mode_string_coerces_in_post_init(self):
        config = QCConfig(output_mode="detailed-run")
        assert config.output_mode.value == "detailed-run"

    def test_output_mode_serializes_to_string_in_to_dict(self):
        config = QCConfig(output_mode=OutputMode.DETAILED)
        d = config.to_dict()
        assert d["output_mode"] == "detailed-run"

    def test_output_mode_roundtrips_through_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name
        try:
            original = QCConfig(output_mode=OutputMode.DETAILED)
            original.to_file(temp_path)
            loaded = QCConfig.from_file(temp_path)
            assert loaded.output_mode.value == "detailed-run"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
