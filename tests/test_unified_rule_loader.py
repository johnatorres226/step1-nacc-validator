"""
Tests for the unified rule loader.

This module tests the UnifiedRuleLoader class which loads and merges all rules
for a packet into a single schema.
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

from src.pipeline.io.unified_rule_loader import UnifiedRuleLoader
from src.pipeline.config.config_manager import QCConfig


@pytest.fixture
def mock_config():
    """Create a mock config for testing."""
    config = Mock(spec=QCConfig)
    config.get_rules_path_for_packet.side_effect = lambda packet: {
        "I": "config/I/rules",
        "I4": "config/I4/rules",
        "F": "config/F/rules",
    }.get(packet)
    return config


@pytest.fixture
def sample_rule_files(tmp_path):
    """Create sample rule files for testing."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    
    # Create sample rule files
    a1_rules = {
        "birthmo": {"required": True, "type": "integer", "min": 1, "max": 12},
        "birthyr": {"required": True, "type": "integer", "min": 1850},
    }
    
    b1_rules = {
        "height": {"required": True, "type": "integer"},
        "weight": {"required": True, "type": "integer"},
    }
    
    header_rules = {
        "packet": {"required": True, "type": "string"},
        "visit_num": {"required": True, "type": "integer"},
    }
    
    (rules_dir / "a1_rules.json").write_text(json.dumps(a1_rules))
    (rules_dir / "b1_rules.json").write_text(json.dumps(b1_rules))
    (rules_dir / "header_rules.json").write_text(json.dumps(header_rules))
    
    return rules_dir


class TestUnifiedRuleLoaderInitialization:
    """Test UnifiedRuleLoader initialization."""

    def test_initialization_with_config(self, mock_config):
        """Test initialization with provided config."""
        loader = UnifiedRuleLoader(config=mock_config)
        
        assert loader.config == mock_config
        assert loader._packet_cache == {}
        assert loader._cache_stats == {"hits": 0, "misses": 0}

    def test_initialization_without_config(self):
        """Test initialization without config (uses get_config())."""
        with patch("src.pipeline.io.unified_rule_loader.get_config") as mock_get_config:
            mock_get_config.return_value = Mock(spec=QCConfig)
            loader = UnifiedRuleLoader()
            
            assert loader.config is not None
            mock_get_config.assert_called_once()


class TestLoadPacketRules:
    """Test loading rules for a packet."""

    def test_load_packet_rules_success(self, mock_config, sample_rule_files):
        """Test successfully loading rules for a packet."""
        # Ensure we're using the temp directory, not real  config paths
        mock_config.get_rules_path_for_packet = Mock(return_value=str(sample_rule_files))
        loader = UnifiedRuleLoader(config=mock_config)
        
        rules = loader.load_packet_rules("I")
        
        # Should have merged all rules from all files
        assert "birthmo" in rules
        assert "birthyr" in rules
        assert "height" in rules
        assert "weight" in rules
        assert "packet" in rules
        assert "visit_num" in rules
        assert len(rules) == 6

    def test_load_packet_rules_caching(self, mock_config, sample_rule_files):
        """Test that rules are cached and not reloaded."""
        mock_config.get_rules_path_for_packet = Mock(return_value=str(sample_rule_files))
        loader = UnifiedRuleLoader(config=mock_config)
        
        # First load - should miss cache
        rules1 = loader.load_packet_rules("I")
        assert loader._cache_stats["misses"] == 1
        assert loader._cache_stats["hits"] == 0
        
        # Second load - should hit cache
        rules2 = loader.load_packet_rules("I")
        assert loader._cache_stats["misses"] == 1
        assert loader._cache_stats["hits"] == 1
        
        # Should return same object
        assert rules1 is rules2

    def test_load_packet_rules_invalid_packet(self, mock_config):
        """Test loading rules with invalid packet value."""
        loader = UnifiedRuleLoader(config=mock_config)
        
        with pytest.raises(ValueError, match="Invalid packet value"):
            loader.load_packet_rules("INVALID")

    def test_load_packet_rules_missing_path(self, mock_config):
        """Test loading rules when path is not configured."""
        mock_config.get_rules_path_for_packet.side_effect = ValueError("No rules path")
        loader = UnifiedRuleLoader(config=mock_config)
        
        with pytest.raises(ValueError, match="No rules path"):
            loader.load_packet_rules("I")

    def test_load_packet_rules_nonexistent_path(self, mock_config):
        """Test loading rules when path does not exist."""
        mock_config.get_rules_path_for_packet = Mock(return_value="/nonexistent/path")
        loader = UnifiedRuleLoader(config=mock_config)
        
        with pytest.raises(FileNotFoundError, match="does not exist"):
            loader.load_packet_rules("I")

    def test_load_packet_rules_empty_directory(self, mock_config, tmp_path):
        """Test loading rules from empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        mock_config.get_rules_path_for_packet = Mock(return_value=str(empty_dir))
        loader = UnifiedRuleLoader(config=mock_config)
        
        rules = loader.load_packet_rules("I")
        
        assert rules == {}

    def test_load_packet_rules_multiple_packets(self, mock_config, sample_rule_files):
        """Test loading rules for multiple different packets."""
        mock_config.get_rules_path_for_packet = Mock(side_effect=lambda p: str(sample_rule_files))
        loader = UnifiedRuleLoader(config=mock_config)
        
        rules_i = loader.load_packet_rules("I")
        rules_i4 = loader.load_packet_rules("I4")
        
        # Both should be cached separately
        assert len(loader._packet_cache) == 2
        assert "I" in loader._packet_cache
        assert "I4" in loader._packet_cache


class TestLoadAndMergeRules:
    """Test the _load_and_merge_rules method."""

    def test_merge_rules_from_multiple_files(self, mock_config, sample_rule_files):
        """Test merging rules from multiple JSON files."""
        mock_config.get_rules_path_for_packet.return_value = str(sample_rule_files)
        loader = UnifiedRuleLoader(config=mock_config)
        
        rules = loader._load_and_merge_rules(sample_rule_files, "I")
        
        # Check that rules from all files are present
        assert "birthmo" in rules  # from a1_rules.json
        assert "height" in rules   # from b1_rules.json
        assert "packet" in rules   # from header_rules.json

    def test_merge_rules_invalid_json(self, mock_config, tmp_path):
        """Test handling of invalid JSON in rule files."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "invalid.json").write_text("not valid json {")
        
        loader = UnifiedRuleLoader(config=mock_config)
        
        with pytest.raises(json.JSONDecodeError):
            loader._load_and_merge_rules(rules_dir, "I")

    def test_merge_rules_non_dict_content(self, mock_config, tmp_path):
        """Test handling of non-dictionary JSON content."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "list.json").write_text(json.dumps(["not", "a", "dict"]))
        (rules_dir / "valid.json").write_text(json.dumps({"var1": {"type": "string"}}))
        
        loader = UnifiedRuleLoader(config=mock_config)
        
        # Should skip the non-dict file and continue
        rules = loader._load_and_merge_rules(rules_dir, "I")
        
        # Should have rules from valid file only
        assert "var1" in rules
        assert len(rules) == 1

    def test_merge_rules_variable_collision(self, mock_config, tmp_path):
        """Test handling of variable name collisions."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        
        # Create files with same variable name
        rules1 = {"shared_var": {"type": "string", "max": 10}}
        rules2 = {"shared_var": {"type": "integer", "max": 100}}
        
        (rules_dir / "file1.json").write_text(json.dumps(rules1))
        (rules_dir / "file2.json").write_text(json.dumps(rules2))
        
        loader = UnifiedRuleLoader(config=mock_config)
        
        # Should log warning but continue (later file wins)
        rules = loader._load_and_merge_rules(rules_dir, "I")
        
        # Second file should override first
        assert rules["shared_var"]["type"] == "integer"
        assert rules["shared_var"]["max"] == 100


class TestGetRulesForRecord:
    """Test getting rules for a specific record."""

    def test_get_rules_for_record_success(self, mock_config, sample_rule_files):
        """Test getting rules for a record with valid packet."""
        mock_config.get_rules_path_for_packet = Mock(return_value=str(sample_rule_files))
        loader = UnifiedRuleLoader(config=mock_config)
        
        record = {"packet": "I", "other_field": "value"}
        rules = loader.get_rules_for_record(record)
        
        assert len(rules) > 0
        assert "birthmo" in rules

    def test_get_rules_for_record_missing_packet(self, mock_config):
        """Test getting rules for record without packet field."""
        loader = UnifiedRuleLoader(config=mock_config)
        
        record = {"other_field": "value"}
        
        with pytest.raises(ValueError, match="Missing packet value"):
            loader.get_rules_for_record(record)

    def test_get_rules_for_record_empty_packet(self, mock_config):
        """Test getting rules for record with empty packet value."""
        loader = UnifiedRuleLoader(config=mock_config)
        
        record = {"packet": "", "other_field": "value"}
        
        with pytest.raises(ValueError, match="Missing packet value"):
            loader.get_rules_for_record(record)

    def test_get_rules_for_record_case_insensitive(self, mock_config, sample_rule_files):
        """Test that packet value is case-insensitive."""
        mock_config.get_rules_path_for_packet = Mock(return_value=str(sample_rule_files))
        loader = UnifiedRuleLoader(config=mock_config)
        
        record_lower = {"packet": "i"}
        record_upper = {"packet": "I"}
        
        rules_lower = loader.get_rules_for_record(record_lower)
        rules_upper = loader.get_rules_for_record(record_upper)
        
        # Should return same cached rules
        assert rules_lower is rules_upper


class TestResolveDynamicRules:
    """Test dynamic rule resolution (C2/C2T)."""

    def test_resolve_dynamic_rules_without_discriminant(self, mock_config):
        """Test dynamic resolution for record without discriminant."""
        loader = UnifiedRuleLoader(config=mock_config)
        
        record = {"packet": "I", "some_field": "value"}
        base_rules = {"var1": {"type": "string"}}
        
        resolved = loader._resolve_dynamic_rules(record, base_rules)
        
        # Should return base rules unchanged
        assert resolved == base_rules

    def test_resolve_dynamic_rules_with_c2_discriminant(self, mock_config):
        """Test dynamic resolution for record with C2 discriminant."""
        loader = UnifiedRuleLoader(config=mock_config)
        
        record = {"packet": "I", "loc_c2_or_c2t": "C2"}
        base_rules = {"var1": {"type": "string"}}
        
        resolved = loader._resolve_dynamic_rules(record, base_rules)
        
        # Currently returns base rules (logic delegated to HierarchicalRuleResolver)
        assert resolved == base_rules

    def test_resolve_dynamic_rules_with_c2t_discriminant(self, mock_config):
        """Test dynamic resolution for record with C2T discriminant."""
        loader = UnifiedRuleLoader(config=mock_config)
        
        record = {"packet": "I", "loc_c2_or_c2t": "C2T"}
        base_rules = {"var1": {"type": "string"}}
        
        resolved = loader._resolve_dynamic_rules(record, base_rules)
        
        # Currently returns base rules (logic delegated to HierarchicalRuleResolver)
        assert resolved == base_rules


class TestCacheManagement:
    """Test cache management functionality."""

    def test_clear_cache(self, mock_config, sample_rule_files):
        """Test clearing the cache."""
        mock_config.get_rules_path_for_packet = Mock(return_value=str(sample_rule_files))
        loader = UnifiedRuleLoader(config=mock_config)
        
        # Load rules to populate cache
        loader.load_packet_rules("I")
        assert len(loader._packet_cache) == 1
        
        # Clear cache
        loader.clear_cache()
        assert len(loader._packet_cache) == 0

    def test_get_cache_stats(self, mock_config, sample_rule_files):
        """Test getting cache statistics."""
        mock_config.get_rules_path_for_packet = Mock(return_value=str(sample_rule_files))
        loader = UnifiedRuleLoader(config=mock_config)
        
        # Initial stats
        stats = loader.get_cache_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["cached_packets"] == 0
        
        # Load once (miss)
        loader.load_packet_rules("I")
        stats = loader.get_cache_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 1
        assert stats["cached_packets"] == 1
        
        # Load again (hit)
        loader.load_packet_rules("I")
        stats = loader.get_cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["cached_packets"] == 1

    def test_cache_stats_after_clear(self, mock_config, sample_rule_files):
        """Test cache stats after clearing cache."""
        mock_config.get_rules_path_for_packet = Mock(return_value=str(sample_rule_files))
        loader = UnifiedRuleLoader(config=mock_config)
        
        # Load and get stats
        loader.load_packet_rules("I")
        loader.load_packet_rules("I")  # Hit
        
        # Clear cache
        loader.clear_cache()
        
        # Stats should keep counts but show 0 cached packets
        stats = loader.get_cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["cached_packets"] == 0


class TestIntegration:
    """Integration tests for UnifiedRuleLoader."""

    def test_full_workflow(self, mock_config, sample_rule_files):
        """Test complete workflow: load, cache, retrieve."""
        mock_config.get_rules_path_for_packet = Mock(return_value=str(sample_rule_files))
        loader = UnifiedRuleLoader(config=mock_config)
        
        # Load rules via record
        record = {"packet": "I", "birthmo": 5}
        rules = loader.get_rules_for_record(record)
        
        # Verify rules loaded
        assert len(rules) == 6
        assert "birthmo" in rules
        
        # Verify caching
        stats = loader.get_cache_stats()
        assert stats["misses"] == 1
        assert stats["hits"] == 0
        
        # Load again - should hit cache
        rules2 = loader.get_rules_for_record(record)
        assert rules2 is rules
        
        stats = loader.get_cache_stats()
        assert stats["hits"] == 1

    def test_multiple_packets_workflow(self, mock_config, tmp_path):
        """Test workflow with multiple packet types."""
        # Create different rule sets for different packets
        i_rules_dir = tmp_path / "I"
        i4_rules_dir = tmp_path / "I4"
        i_rules_dir.mkdir()
        i4_rules_dir.mkdir()
        
        (i_rules_dir / "rules.json").write_text(
            json.dumps({"i_var": {"type": "string"}})
        )
        (i4_rules_dir / "rules.json").write_text(
            json.dumps({"i4_var": {"type": "integer"}})
        )
        
        def get_path(packet):
            return str(i_rules_dir if packet == "I" else i4_rules_dir)
        
        mock_config.get_rules_path_for_packet = Mock(side_effect=get_path)
        loader = UnifiedRuleLoader(config=mock_config)
        
        # Load rules for both packets
        rules_i = loader.load_packet_rules("I")
        rules_i4 = loader.load_packet_rules("I4")
        
        # Should have different rules
        assert "i_var" in rules_i
        assert "i_var" not in rules_i4
        assert "i4_var" in rules_i4
        assert "i4_var" not in rules_i
        
        # Both should be cached
        assert len(loader._packet_cache) == 2
