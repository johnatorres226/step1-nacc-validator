"""Tests for packet-based rule isolation.

This module tests the cross-packet namespace collision bug and its fix.
The bug occurs when loading multiple packets (I, I4, F) into the same
NamespacedRulePool, causing F-packet rules to be applied to I/I4 records.

Root Cause:
- config/I/rules/a3_rules.json → namespace "a3"
- config/F/rules/a3_rules.json → namespace "a3" (SAME!)
- No conflict detected because namespaces match
- F-packet variables (nwinfpar, nwinfkid) get added to pool
- F-packet variables validated against I records → FALSE POSITIVE ERRORS
"""

from pathlib import Path

import pytest

from src.pipeline.config.config_manager import QCConfig
from src.pipeline.io.rule_pool import NamespacedRulePool, reset_pool


@pytest.fixture
def config():
    """Create a config with valid rule paths."""
    # Use project root-relative paths for test
    project_root = Path(__file__).parent.parent
    return QCConfig(
        api_token="test_token",
        api_url="https://test.url",
        json_rules_path_i=str(project_root / "config" / "I" / "rules"),
        json_rules_path_i4=str(project_root / "config" / "I4" / "rules"),
        json_rules_path_f=str(project_root / "config" / "F" / "rules"),
    )


@pytest.fixture(autouse=True)
def reset_pool_state():
    """Reset the pool singleton before and after each test."""
    reset_pool()
    yield
    reset_pool()


# =============================================================================
# BUG REPRODUCTION TESTS
# These tests demonstrate the current bug behavior
# =============================================================================


class TestCrossPacketCollisionBug:
    """Tests that demonstrate the cross-packet namespace collision bug."""

    def test_loading_i_then_f_adds_f_only_variables(self, config):
        """BUG: F-packet variables are present after loading both packets.

        When validating I packet records, F-only variables like 'nwinfpar'
        should NOT be in the pool. But because both packets share namespace
        'a3', F variables get added to the same pool.
        """
        pool = NamespacedRulePool()

        # Load I packet first
        pool.load_packet("I", config)
        i_packet_only_pool = dict(pool._rules)

        # Check nwinfpar is NOT in I packet rules (F-only variable)
        nwinfpar_in_i = "nwinfpar" in i_packet_only_pool
        assert not nwinfpar_in_i, "nwinfpar should NOT exist in I packet rules"

        # Now load F packet into same pool
        pool.load_packet("F", config)

        # BUG: nwinfpar is now present (from F packet)
        nwinfpar_after_f = pool.get_rule("nwinfpar")
        assert nwinfpar_after_f is not None, (
            "Expected BUG: nwinfpar should be present after loading F packet, "
            "but it's not - this may indicate the bug is already fixed!"
        )

        # This is the bug: F-only variables are available when validating I records
        print("BUG CONFIRMED: nwinfpar (F-only) is present after loading I+F")
        print(f"  Source file: {nwinfpar_after_f.source_file}")
        print(f"  Namespace: {nwinfpar_after_f.namespace}")

    def test_same_namespace_no_conflict_detected(self, config):
        """BUG: Same namespace across packets means no conflict detection.

        Both config/I/rules/a3_rules.json and config/F/rules/a3_rules.json
        produce namespace 'a3'. The pool doesn't detect this as a conflict
        because the namespace is identical.
        """
        pool = NamespacedRulePool()

        pool.load_packet("I", config)
        pool.load_packet("F", config)

        # Check conflicting variables - momyob exists in both I and F
        momyob_rule = pool.get_rule("momyob")
        assert momyob_rule is not None

        # BUG: momyob is NOT in the conflicts set because same namespace
        is_conflict = "momyob" in pool.conflict_variables
        print(f"momyob in conflict set: {is_conflict}")
        print(f"Total conflicts detected: {len(pool.conflict_variables)}")

        # The bug is that inter-packet conflicts are not detected
        # because namespace is derived from filename only, not packet

    def test_pool_size_increases_after_loading_f(self, config):
        """Shows that loading F packet adds variables to existing I pool."""
        pool = NamespacedRulePool()

        pool.load_packet("I", config)
        i_count = len(pool)

        pool.load_packet("F", config)
        if_count = len(pool)

        print(f"Pool size after I: {i_count}")
        print(f"Pool size after I+F: {if_count}")
        print(f"Additional variables from F: {if_count - i_count}")

        # F packet adds F-only variables
        assert if_count >= i_count, "F packet should add or maintain pool size"


# =============================================================================
# FIX VERIFICATION TESTS
# These tests verify the fix works correctly
# =============================================================================


class TestPacketIsolationFix:
    """Tests to verify the packet isolation fix."""

    def test_clearing_pool_between_packets_isolates_rules(self, config):
        """FIXED: Clearing pool before loading new packet prevents collision."""
        pool = NamespacedRulePool()

        # Load I packet
        pool.load_packet("I", config)
        assert pool.get_rule("nwinfpar") is None, "nwinfpar should not exist in I"

        # Clear and load F packet (simulating per-record loading)
        pool.clear()
        pool.load_packet("F", config)

        # Now nwinfpar exists (correctly, for F packet validation)
        nwinfpar_rule = pool.get_rule("nwinfpar")
        assert nwinfpar_rule is not None, "nwinfpar should exist in F packet"

        # And momyob has F-packet semantics
        momyob_rule = pool.get_rule("momyob")
        assert momyob_rule is not None

    def test_separate_pools_per_packet_no_collision(self, config):
        """FIXED: Using separate pool instances per packet prevents collision."""
        pool_i = NamespacedRulePool()
        pool_f = NamespacedRulePool()

        pool_i.load_packet("I", config)
        pool_f.load_packet("F", config)

        # I pool should NOT have F-only variables
        assert pool_i.get_rule("nwinfpar") is None
        assert pool_i.get_rule("nwinfkid") is None
        assert pool_i.get_rule("nwinfsib") is None

        # F pool SHOULD have F-only variables
        assert pool_f.get_rule("nwinfpar") is not None
        assert pool_f.get_rule("nwinfkid") is not None
        assert pool_f.get_rule("nwinfsib") is not None

        # Both have common variables
        assert pool_i.get_rule("momyob") is not None
        assert pool_f.get_rule("momyob") is not None

    def test_validation_with_correct_packet_rules(self, config):
        """Verifies record validation uses correct packet's rules."""
        # Test data setup (records defined for documentation)
        # i_record = {"ptid": "TEST001", "packet": "I", "momyob": 1940}
        # f_record = {"ptid": "TEST002", "packet": "F", "momyob": "", "nwinfpar": 0}

        # For I record, nwinfpar validation should NOT happen
        pool_i = NamespacedRulePool()
        pool_i.load_packet("I", config)
        i_rules = pool_i.get_all_rules()
        i_vars = set(i_rules.keys())

        # For F record, nwinfpar validation SHOULD happen
        pool_f = NamespacedRulePool()
        pool_f.load_packet("F", config)
        f_rules = pool_f.get_all_rules()
        f_vars = set(f_rules.keys())

        # F-only variables
        f_only = f_vars - i_vars
        print(f"F-only variables: {len(f_only)}")
        print(f"Sample F-only vars: {list(f_only)[:5]}")

        assert "nwinfpar" in f_vars
        assert "nwinfpar" not in i_vars


# =============================================================================
# REGRESSION TESTS
# =============================================================================


class TestPoolBehavior:
    """General pool behavior tests."""

    def test_pool_is_idempotent_for_same_packet(self, config):
        """Loading same packet twice doesn't duplicate rules."""
        pool = NamespacedRulePool()

        pool.load_packet("I", config)
        count1 = len(pool)

        pool.load_packet("I", config)  # Load again
        count2 = len(pool)

        assert count1 == count2, "Re-loading same packet should be idempotent"

    def test_pool_tracks_loaded_packets(self, config):
        """Pool correctly tracks which packets have been loaded."""
        pool = NamespacedRulePool()

        assert "I" not in pool.loaded_packets
        pool.load_packet("I", config)
        assert "I" in pool.loaded_packets

        pool.load_packet("F", config)
        assert "F" in pool.loaded_packets
        assert "I" in pool.loaded_packets

    def test_clear_resets_all_state(self, config):
        """Pool clear() resets all internal state."""
        pool = NamespacedRulePool()
        pool.load_packet("I", config)

        assert len(pool) > 0
        assert len(pool.loaded_packets) > 0

        pool.clear()

        assert len(pool) == 0
        assert len(pool.loaded_packets) == 0
        assert len(pool.conflict_variables) == 0
