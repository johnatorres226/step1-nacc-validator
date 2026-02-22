"""
Tests for the consolidated rule_loader module.

Tests packet-based rule loading, caching, dynamic instrument resolution,
and error handling.
"""

import json
from unittest.mock import Mock, patch

import pytest

from src.pipeline.config.config_manager import QCConfig
from src.pipeline.io.rule_loader import (
    clear_cache,
    get_rules_for_record,
    load_rules_for_instrument,
    load_rules_for_instruments,
    load_rules_for_packet,
    resolve_dynamic_rules,
)


@pytest.fixture(autouse=True)
def _clear_rule_cache():
    """Clear the rule loader cache before each test."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def sample_rules_dir(tmp_path):
    """Create a temporary rules directory with sample JSON files."""
    a1 = {"birthmo": {"type": "integer", "min": 1, "max": 12}}
    b1 = {"height": {"type": "integer"}, "weight": {"type": "integer"}}
    header = {"packet": {"type": "string"}}

    (tmp_path / "a1_rules.json").write_text(json.dumps(a1))
    (tmp_path / "b1_rules.json").write_text(json.dumps(b1))
    (tmp_path / "header_rules.json").write_text(json.dumps(header))
    return tmp_path


@pytest.fixture
def mock_config(sample_rules_dir):
    """Create a mock QCConfig pointing to the sample rules directory."""
    config = Mock(spec=QCConfig)
    config.get_rules_path_for_packet.return_value = str(sample_rules_dir)
    config.json_rules_path_i = str(sample_rules_dir)
    return config


# =============================================================================
# load_rules_for_packet
# =============================================================================


class TestLoadRulesForPacket:
    def test_loads_and_merges_all_json_files(self, mock_config):
        rules = load_rules_for_packet("I", config=mock_config)
        assert "birthmo" in rules
        assert "height" in rules
        assert "weight" in rules
        assert "packet" in rules
        assert len(rules) == 4

    def test_caches_result(self, mock_config):
        rules1 = load_rules_for_packet("I", config=mock_config)
        rules2 = load_rules_for_packet("I", config=mock_config)
        assert rules1 is rules2

    def test_case_insensitive_packet(self, mock_config):
        rules_lower = load_rules_for_packet("i", config=mock_config)
        rules_upper = load_rules_for_packet("I", config=mock_config)
        assert rules_lower is rules_upper

    def test_invalid_packet_raises(self, mock_config):
        with pytest.raises(ValueError, match="Invalid packet"):
            load_rules_for_packet("INVALID", config=mock_config)

    def test_nonexistent_path_raises(self, mock_config):
        mock_config.get_rules_path_for_packet.return_value = "/nonexistent/path"
        with pytest.raises(FileNotFoundError):
            load_rules_for_packet("I", config=mock_config)

    def test_empty_directory(self, mock_config, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        mock_config.get_rules_path_for_packet.return_value = str(empty_dir)
        rules = load_rules_for_packet("I", config=mock_config)
        assert rules == {}

    def test_skips_invalid_json(self, tmp_path, mock_config):
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "bad.json").write_text("not json {")
        (bad_dir / "good.json").write_text(json.dumps({"var1": {"type": "string"}}))
        mock_config.get_rules_path_for_packet.return_value = str(bad_dir)
        rules = load_rules_for_packet("I", config=mock_config)
        assert "var1" in rules

    def test_skips_non_dict_content(self, tmp_path, mock_config):
        nd_dir = tmp_path / "nondict"
        nd_dir.mkdir()
        (nd_dir / "array.json").write_text(json.dumps(["not", "a", "dict"]))
        (nd_dir / "valid.json").write_text(json.dumps({"var1": {"type": "string"}}))
        mock_config.get_rules_path_for_packet.return_value = str(nd_dir)
        rules = load_rules_for_packet("I", config=mock_config)
        assert "var1" in rules


# =============================================================================
# resolve_dynamic_rules
# =============================================================================


class TestResolveDynamicRules:
    def test_non_dynamic_instrument_returns_base(self):
        base = {"var1": {"type": "string"}}
        result = resolve_dynamic_rules(
            {"packet": "I"}, base, "a1_participant_demographics"
        )
        assert result == base

    @patch("src.pipeline.io.rule_loader.is_dynamic_rule_instrument", return_value=True)
    @patch("src.pipeline.io.rule_loader.get_discriminant_variable", return_value="loc_c2_or_c2t")
    def test_c2_variant_resolved(self, _mock_disc, _mock_dyn):
        base = {"C2": {"var1": {"type": "string"}}, "C2T": {"var2": {"type": "int"}}}
        record = {"loc_c2_or_c2t": "C2"}
        result = resolve_dynamic_rules(record, base, "c2c2t_neuropsychological_battery_scores")
        assert result == {"var1": {"type": "string"}}

    @patch("src.pipeline.io.rule_loader.is_dynamic_rule_instrument", return_value=True)
    @patch("src.pipeline.io.rule_loader.get_discriminant_variable", return_value="loc_c2_or_c2t")
    def test_c2t_variant_resolved(self, _mock_disc, _mock_dyn):
        base = {"C2": {"var1": {"type": "string"}}, "C2T": {"var2": {"type": "int"}}}
        record = {"loc_c2_or_c2t": "C2T"}
        result = resolve_dynamic_rules(record, base, "c2c2t_neuropsychological_battery_scores")
        assert result == {"var2": {"type": "int"}}

    @patch("src.pipeline.io.rule_loader.is_dynamic_rule_instrument", return_value=True)
    @patch("src.pipeline.io.rule_loader.get_discriminant_variable", return_value="loc_c2_or_c2t")
    def test_missing_discriminant_falls_back(self, _mock_disc, _mock_dyn):
        base = {"C2": {"var1": {"type": "string"}}, "C2T": {"var2": {"type": "int"}}}
        record = {}
        result = resolve_dynamic_rules(record, base, "c2c2t_neuropsychological_battery_scores")
        assert result == {"var1": {"type": "string"}}


# =============================================================================
# get_rules_for_record
# =============================================================================


class TestGetRulesForRecord:
    def test_returns_rules_for_standard_instrument(self, mock_config):
        record = {"packet": "I", "ptid": "TEST001"}
        rules = get_rules_for_record(record, "a1_participant_demographics", config=mock_config)
        assert isinstance(rules, dict)

    def test_missing_packet_raises(self, mock_config):
        with pytest.raises(ValueError, match="Invalid packet"):
            get_rules_for_record({"ptid": "TEST001"}, "a1", config=mock_config)

    def test_invalid_packet_raises(self, mock_config):
        with pytest.raises(ValueError, match="Invalid packet"):
            get_rules_for_record({"packet": "X"}, "a1", config=mock_config)


# =============================================================================
# clear_cache
# =============================================================================


class TestClearCache:
    def test_clear_forces_reload(self, mock_config):
        rules1 = load_rules_for_packet("I", config=mock_config)
        clear_cache()
        rules2 = load_rules_for_packet("I", config=mock_config)
        assert rules1 is not rules2
        assert rules1 == rules2


# =============================================================================
# load_rules_for_instruments
# =============================================================================


class TestLoadRulesForInstruments:
    @patch("src.pipeline.io.rule_loader.load_rules_for_instrument")
    def test_loads_multiple_instruments(self, mock_load):
        mock_load.side_effect = lambda name, config=None: {f"{name}_var": {"type": "string"}}
        result = load_rules_for_instruments(["a1", "b1"])
        assert "a1" in result
        assert "b1" in result
        assert mock_load.call_count == 2
