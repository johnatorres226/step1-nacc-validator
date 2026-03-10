"""
Unit tests for NamespacedRulePool auto-discovery and conflict detection.
"""

import json
from unittest.mock import Mock

import pytest

from src.pipeline.config.config_manager import QCConfig
from src.pipeline.io.rule_pool import NamespacedRulePool, RuleEntry, get_pool, reset_pool

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_pool_singleton():
    """Reset the pool singleton before and after each test."""
    reset_pool()
    yield
    reset_pool()


@pytest.fixture
def tmp_rules_dir(tmp_path):
    """Create a temporary rules directory with sample rule files."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    (rules_dir / "a1_rules.json").write_text(
        json.dumps(
            {
                "a1_birthyr": {"type": "integer", "min": 1900, "max": 2026},
                "a1_sex": {"type": "integer", "allowed": [1, 2]},
            }
        )
    )
    (rules_dir / "b1_rules.json").write_text(
        json.dumps(
            {
                "b1_height": {"type": "float", "min": 0, "max": 300},
            }
        )
    )
    return rules_dir


@pytest.fixture
def tmp_rules_dir_with_optional(tmp_rules_dir):
    """Adds an optional rule file alongside standard rule files."""
    (tmp_rules_dir / "a1a_rules_optional.json").write_text(
        json.dumps({"optional_var": {"type": "string"}})
    )
    return tmp_rules_dir


@pytest.fixture
def tmp_rules_dir_with_txt(tmp_rules_dir):
    """Adds a non-JSON file alongside standard rule files."""
    (tmp_rules_dir / "notes.txt").write_text("not a rule file")
    return tmp_rules_dir


@pytest.fixture
def tmp_rules_dir_with_bad_json(tmp_rules_dir):
    """Adds an invalid JSON file alongside standard rule files."""
    (tmp_rules_dir / "broken_rules.json").write_text("not json {")
    return tmp_rules_dir


@pytest.fixture
def tmp_rules_dir_with_list_json(tmp_rules_dir):
    """Adds a JSON file containing an array instead of a dict."""
    (tmp_rules_dir / "array_rules.json").write_text(json.dumps(["not", "a", "dict"]))
    return tmp_rules_dir


@pytest.fixture
def tmp_empty_rules_dir(tmp_path):
    """An empty rules directory."""
    rules_dir = tmp_path / "empty_rules"
    rules_dir.mkdir()
    return rules_dir


@pytest.fixture
def pool_with_c2_c2t(tmp_path):
    """Pool loaded with C2 and C2T overlapping rule files."""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    (rules_dir / "c2_rules.json").write_text(
        json.dumps(
            {
                "mocacomp": {"type": "integer", "allowed": [0, 1]},
                "mocatots": {"type": "integer", "min": 0, "max": 30},
                "c2_unique_var": {"type": "string"},
            }
        )
    )
    (rules_dir / "c2t_rules.json").write_text(
        json.dumps(
            {
                "mocacomp": {"type": "integer", "allowed": [0, 1, 2]},
                "mocatots": {"type": "integer", "min": 0, "max": 100},
                "c2t_unique_var": {"type": "string"},
            }
        )
    )

    config = Mock(spec=QCConfig)
    config.get_rules_path_for_packet.return_value = str(rules_dir)

    pool = NamespacedRulePool()
    pool.load_packet("I", config=config)
    return pool


def _make_config(rules_dir) -> Mock:
    """Helper to create a mock config pointing at *rules_dir*."""
    config = Mock(spec=QCConfig)
    config.get_rules_path_for_packet.return_value = str(rules_dir)
    return config


# ---------------------------------------------------------------------------
# Loading tests
# ---------------------------------------------------------------------------


class TestLoading:
    def test_load_packet_discovers_all_rule_files(self, tmp_rules_dir):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir))
        # a1_rules.json has 2 vars, b1_rules.json has 1 var
        assert len(pool) == 3
        assert "a1_birthyr" in pool.get_all_rules()
        assert "b1_height" in pool.get_all_rules()

    def test_load_packet_skips_optional_rule_files(self, tmp_rules_dir_with_optional):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir_with_optional))
        assert "optional_var" not in pool.get_all_rules()
        # Only the standard 3 variables should be loaded
        assert len(pool) == 3

    def test_load_packet_skips_non_json_files(self, tmp_rules_dir_with_txt):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir_with_txt))
        assert len(pool) == 3

    def test_load_packet_skips_invalid_json(self, tmp_rules_dir_with_bad_json):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir_with_bad_json))
        assert len(pool) == 3  # broken_rules.json is skipped

    def test_load_packet_skips_non_dict_json(self, tmp_rules_dir_with_list_json):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir_with_list_json))
        assert len(pool) == 3  # array_rules.json is skipped

    def test_load_packet_empty_directory(self, tmp_empty_rules_dir):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_empty_rules_dir))
        assert len(pool) == 0

    def test_load_packet_nonexistent_directory(self, tmp_path):
        config = Mock(spec=QCConfig)
        config.get_rules_path_for_packet.return_value = str(tmp_path / "nonexistent")
        pool = NamespacedRulePool()
        with pytest.raises(FileNotFoundError):
            pool.load_packet("I", config=config)

    def test_load_packet_idempotent(self, tmp_rules_dir):
        pool = NamespacedRulePool()
        cfg = _make_config(tmp_rules_dir)
        pool.load_packet("I", config=cfg)
        count_before = len(pool)
        pool.load_packet("I", config=cfg)
        assert len(pool) == count_before

    def test_load_multiple_packets(self, tmp_path):
        """Loading I then F merges both packet's rules."""
        dir_i = tmp_path / "rules_i"
        dir_i.mkdir()
        (dir_i / "a1_rules.json").write_text(json.dumps({"var_i": {"type": "string"}}))

        dir_f = tmp_path / "rules_f"
        dir_f.mkdir()
        (dir_f / "a1_rules.json").write_text(json.dumps({"var_f": {"type": "string"}}))

        config = Mock(spec=QCConfig)
        config.get_rules_path_for_packet.side_effect = lambda p: (
            str(dir_i) if p == "I" else str(dir_f)
        )

        pool = NamespacedRulePool()
        pool.load_packet("I", config=config)
        pool.load_packet("F", config=config)
        assert "var_i" in pool.get_all_rules()
        assert "var_f" in pool.get_all_rules()
        assert pool.loaded_packets == frozenset({"I", "F"})


# ---------------------------------------------------------------------------
# Namespace extraction
# ---------------------------------------------------------------------------


class TestNamespaceExtraction:
    def test_namespace_from_filename(self, tmp_rules_dir):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir))
        entry = pool.get_rule("a1_birthyr")
        assert entry is not None
        assert entry.namespace == "a1"

        entry_b = pool.get_rule("b1_height")
        assert entry_b is not None
        assert entry_b.namespace == "b1"


# ---------------------------------------------------------------------------
# Flat index (no conflicts)
# ---------------------------------------------------------------------------


class TestFlatIndex:
    def test_get_rule_unique_variable(self, tmp_rules_dir):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir))
        entry = pool.get_rule("a1_birthyr")
        assert entry is not None
        assert isinstance(entry, RuleEntry)
        assert entry.variable == "a1_birthyr"
        assert entry.rule == {"type": "integer", "min": 1900, "max": 2026}

    def test_get_rule_missing_variable(self, tmp_rules_dir):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir))
        assert pool.get_rule("nonexistent_var") is None

    def test_get_all_rules_returns_flat_dict(self, tmp_rules_dir):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir))
        all_rules = pool.get_all_rules()
        assert isinstance(all_rules, dict)
        assert len(all_rules) == 3


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


class TestConflictDetection:
    def test_conflicts_detected_for_overlapping_variables(self, pool_with_c2_c2t):
        assert "mocacomp" in pool_with_c2_c2t.conflict_variables
        assert "mocatots" in pool_with_c2_c2t.conflict_variables

    def test_conflict_variables_property(self, pool_with_c2_c2t):
        conflicts = pool_with_c2_c2t.conflict_variables
        assert isinstance(conflicts, frozenset)
        assert len(conflicts) == 2  # mocacomp and mocatots

    def test_get_rule_conflict_without_namespace_returns_first_wins(self, pool_with_c2_c2t):
        # c2 is alphabetically before c2t, so c2's rule wins
        entry = pool_with_c2_c2t.get_rule("mocacomp")
        assert entry is not None
        assert entry.namespace == "c2"
        assert entry.rule["allowed"] == [0, 1]

    def test_get_rule_conflict_with_namespace_returns_correct_variant(self, pool_with_c2_c2t):
        entry = pool_with_c2_c2t.get_rule("mocacomp", namespace="c2t")
        assert entry is not None
        assert entry.namespace == "c2t"
        assert entry.rule["allowed"] == [0, 1, 2]

    def test_get_rule_conflict_with_unknown_namespace_returns_none(self, pool_with_c2_c2t):
        entry = pool_with_c2_c2t.get_rule("mocacomp", namespace="nonexistent")
        assert entry is None

    def test_unique_vars_not_in_conflicts(self, pool_with_c2_c2t):
        assert "c2_unique_var" not in pool_with_c2_c2t.conflict_variables
        assert "c2t_unique_var" not in pool_with_c2_c2t.conflict_variables

    def test_expected_c2_c2t_conflicts_not_reported_as_unexpected(self, tmp_path):
        """C2/C2T conflicts are expected and should not be in unexpected conflicts."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        
        # Create C2 and C2T files with overlapping variables (expected conflict)
        (rules_dir / "c2_rules.json").write_text(
            json.dumps({"shared_var": {"type": "integer"}})
        )
        (rules_dir / "c2t_rules.json").write_text(
            json.dumps({"shared_var": {"type": "string"}})
        )
        
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(rules_dir))
        
        # Variable should be in conflicts
        assert "shared_var" in pool.conflict_variables
        
        # But should NOT be in unexpected conflicts
        unexpected = pool._get_unexpected_conflicts()
        assert "shared_var" not in unexpected
        assert len(unexpected) == 0

    def test_unexpected_conflicts_are_reported(self, tmp_path):
        """Conflicts between non-C2/C2T namespaces should be reported as unexpected."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        
        # Create A1 and B1 files with overlapping variables (unexpected conflict)
        (rules_dir / "a1_rules.json").write_text(
            json.dumps({"unexpected_shared_var": {"type": "integer"}})
        )
        (rules_dir / "b1_rules.json").write_text(
            json.dumps({"unexpected_shared_var": {"type": "string"}})
        )
        
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(rules_dir))
        
        # Variable should be in conflicts
        assert "unexpected_shared_var" in pool.conflict_variables
        
        # And should be in unexpected conflicts
        unexpected = pool._get_unexpected_conflicts()
        assert "unexpected_shared_var" in unexpected
        assert len(unexpected) == 1




# ---------------------------------------------------------------------------
# get_resolved_rules_dict
# ---------------------------------------------------------------------------


class TestResolvedRulesDict:
    def test_no_namespace(self, tmp_rules_dir):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir))
        result = pool.get_resolved_rules_dict()
        assert "a1_birthyr" in result
        assert "b1_height" in result
        assert result["a1_birthyr"] == {"type": "integer", "min": 1900, "max": 2026}

    def test_with_namespace_resolves_conflicts(self, pool_with_c2_c2t):
        result = pool_with_c2_c2t.get_resolved_rules_dict(namespace="c2t")
        assert result["mocatots"]["max"] == 100  # c2t version
        assert result["mocacomp"]["allowed"] == [0, 1, 2]  # c2t version
        # c2t-unique var should be included
        assert "c2t_unique_var" in result

    def test_with_namespace_includes_unique_vars(self, pool_with_c2_c2t):
        result = pool_with_c2_c2t.get_resolved_rules_dict(namespace="c2")
        assert "c2_unique_var" in result
        assert result["mocatots"]["max"] == 30  # c2 version

    def test_compatible_with_schema_builder(self, tmp_rules_dir):
        """Output dict is {variable: dict} suitable for _build_schema_from_raw."""
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir))
        result = pool.get_resolved_rules_dict()
        for var, rule in result.items():
            assert isinstance(var, str)
            assert isinstance(rule, dict)


# ---------------------------------------------------------------------------
# Pool lifecycle
# ---------------------------------------------------------------------------


class TestPoolLifecycle:
    def test_clear_resets_all_state(self, tmp_rules_dir):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir))
        assert len(pool) > 0
        pool.clear()
        assert len(pool) == 0
        assert pool.loaded_packets == frozenset()
        assert pool.conflict_variables == frozenset()

    def test_len_returns_flat_rule_count(self, tmp_rules_dir):
        pool = NamespacedRulePool()
        pool.load_packet("I", config=_make_config(tmp_rules_dir))
        assert len(pool) == 3

    def test_repr(self, pool_with_c2_c2t):
        r = repr(pool_with_c2_c2t)
        assert "NamespacedRulePool" in r
        assert "rules=" in r
        assert "namespaces=" in r
        assert "conflicts=" in r


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_pool_returns_singleton(self):
        pool1 = get_pool()
        pool2 = get_pool()
        assert pool1 is pool2

    def test_reset_pool_clears_singleton(self):
        pool1 = get_pool()
        reset_pool()
        pool2 = get_pool()
        assert pool1 is not pool2


# ---------------------------------------------------------------------------
# get_all_rules_for_namespace
# ---------------------------------------------------------------------------


class TestGetAllRulesForNamespace:
    def test_returns_all_rules_for_namespace(self, pool_with_c2_c2t):
        c2_rules = pool_with_c2_c2t.get_all_rules_for_namespace("c2")
        assert "mocacomp" in c2_rules
        assert "c2_unique_var" in c2_rules
        assert "c2t_unique_var" not in c2_rules

    def test_returns_empty_for_unknown_namespace(self, pool_with_c2_c2t):
        result = pool_with_c2_c2t.get_all_rules_for_namespace("nonexistent")
        assert result == {}
