"""
Tests for the consolidated rule_loader module backed by NamespacedRulePool.

Tests packet-based rule loading, caching, pool-based namespace resolution,
and error handling.
"""

import json
from unittest.mock import Mock

import pytest

from src.pipeline.config.config_manager import QCConfig
from src.pipeline.io.rule_loader import (
    _resolve_namespace,
    clear_cache,
    get_rules_for_record,
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


@pytest.fixture
def c2_c2t_rules_dir(tmp_path):
    """Create a temp directory with C2 and C2T overlapping rule files."""
    c2 = {
        "mocacomp": {"type": "integer", "allowed": [0, 1]},
        "mocatots": {"type": "integer", "min": 0, "max": 30},
        "c2_unique": {"type": "string"},
    }
    c2t = {
        "mocacomp": {"type": "integer", "allowed": [0, 1, 2]},
        "mocatots": {"type": "integer", "min": 0, "max": 100},
        "c2t_unique": {"type": "string"},
    }
    (tmp_path / "c2_rules.json").write_text(json.dumps(c2))
    (tmp_path / "c2t_rules.json").write_text(json.dumps(c2t))
    return tmp_path


@pytest.fixture
def c2_mock_config(c2_c2t_rules_dir):
    """Config pointing to directory with C2/C2T overlapping rules."""
    config = Mock(spec=QCConfig)
    config.get_rules_path_for_packet.return_value = str(c2_c2t_rules_dir)
    return config


# =============================================================================
# _resolve_namespace (replaces resolve_dynamic_rules tests)
# =============================================================================


class TestResolveNamespace:
    def test_non_discriminant_instrument_returns_none(self):
        result = _resolve_namespace({"packet": "I"}, "a1_participant_demographics")
        assert result is None

    def test_c2_variant_resolved(self):
        record = {"loc_c2_or_c2t": "C2"}
        result = _resolve_namespace(record, "c2c2t_neuropsychological_battery_scores")
        assert result == "c2"

    def test_c2t_variant_resolved(self):
        record = {"loc_c2_or_c2t": "C2T"}
        result = _resolve_namespace(record, "c2c2t_neuropsychological_battery_scores")
        assert result == "c2t"

    def test_missing_discriminant_returns_none(self):
        record = {}
        result = _resolve_namespace(record, "c2c2t_neuropsychological_battery_scores")
        assert result is None

    def test_case_insensitive_discriminant(self):
        record = {"loc_c2_or_c2t": "c2t"}
        result = _resolve_namespace(record, "c2c2t_neuropsychological_battery_scores")
        assert result == "c2t"


# =============================================================================
# get_rules_for_record (pool-based)
# =============================================================================


class TestGetRulesForRecord:
    def test_returns_rules_for_standard_instrument(self, mock_config):
        record = {"packet": "I", "ptid": "TEST001"}
        rules = get_rules_for_record(record, "a1_participant_demographics", config=mock_config)
        assert isinstance(rules, dict)
        assert "birthmo" in rules

    def test_returns_all_pool_rules_for_packet(self, mock_config):
        """Pool-based loading returns all rules for the packet."""
        record = {"packet": "I", "ptid": "TEST001"}
        rules = get_rules_for_record(record, "a1_participant_demographics", config=mock_config)
        # Pool returns ALL rules for the packet, including from all rule files
        assert "birthmo" in rules
        assert "height" in rules
        assert "packet" in rules

    def test_missing_packet_raises(self, mock_config):
        with pytest.raises(ValueError, match="Invalid packet"):
            get_rules_for_record({"ptid": "TEST001"}, "a1", config=mock_config)

    def test_invalid_packet_raises(self, mock_config):
        with pytest.raises(ValueError, match="Invalid packet"):
            get_rules_for_record({"packet": "X"}, "a1", config=mock_config)

    def test_c2_namespace_resolution(self, c2_mock_config):
        """C2 discriminant resolves to c2 namespace rules."""
        record = {"packet": "I", "loc_c2_or_c2t": "C2"}
        rules = get_rules_for_record(
            record, "c2c2t_neuropsychological_battery_scores", config=c2_mock_config
        )
        assert isinstance(rules, dict)
        # Should include c2-unique variable
        assert "c2_unique" in rules
        # Conflict variables should use c2 namespace values
        assert rules["mocatots"]["max"] == 30  # c2 version

    def test_c2t_namespace_resolution(self, c2_mock_config):
        """C2T discriminant resolves to c2t namespace rules."""
        record = {"packet": "I", "loc_c2_or_c2t": "C2T"}
        rules = get_rules_for_record(
            record, "c2c2t_neuropsychological_battery_scores", config=c2_mock_config
        )
        assert isinstance(rules, dict)
        assert "c2t_unique" in rules
        assert rules["mocatots"]["max"] == 100  # c2t version

    def test_missing_discriminant_returns_default_rules(self, c2_mock_config):
        """Missing discriminant returns first-wins (alphabetical) rules."""
        record = {"packet": "I"}
        rules = get_rules_for_record(
            record, "c2c2t_neuropsychological_battery_scores", config=c2_mock_config
        )
        assert isinstance(rules, dict)
        assert "mocacomp" in rules


# =============================================================================
# clear_cache
# =============================================================================


class TestClearCache:
    def test_clear_resets_pool(self, mock_config):
        """clear_cache also resets the pool singleton."""
        from src.pipeline.io.rule_pool import get_pool

        record = {"packet": "I", "ptid": "TEST001"}
        get_rules_for_record(record, "a1_participant_demographics", config=mock_config)
        pool = get_pool()
        assert len(pool) > 0
        clear_cache()
        pool = get_pool()
        assert len(pool) == 0
