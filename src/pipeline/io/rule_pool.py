"""
Namespaced Rule Pool — auto-discovered, O(1) per-variable rule lookup.

Loads all ``*_rules.json`` files from a packet directory, indexes every variable,
and auto-detects namespace conflicts (e.g. C2/C2T overlapping variables).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config.config_manager import QCConfig, get_config
from ..logging.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuleEntry:
    """A single variable's validation rule with source metadata."""

    variable: str
    rule: dict[str, Any]
    source_file: str
    namespace: str


# ---------------------------------------------------------------------------
# Pool implementation
# ---------------------------------------------------------------------------


class NamespacedRulePool:
    """
    Auto-discovered, namespaced rule pool with O(1) per-variable lookup.

    Loads all ``*_rules.json`` files from a packet directory, indexes by
    variable, and auto-detects namespace conflicts (e.g. C2/C2T overlapping
    variables).
    """

    # Glob pattern: only files ending with ``_rules.json``
    # Excludes ``*_rules_optional.json`` by design.
    _GLOB = "*_rules.json"

    # Known namespace pairs that are expected to have conflicts (e.g., C2/C2T)
    # These use discriminant variables for dynamic routing
    _EXPECTED_CONFLICT_PAIRS = frozenset([("c2", "c2t")])

    def __init__(self) -> None:
        self._rules: dict[str, RuleEntry] = {}
        self._namespaced: dict[str, dict[str, RuleEntry]] = {}
        self._conflicts: set[str] = set()
        self._conflict_namespaces: dict[str, set[str]] = {}  # variable -> {namespaces}
        self._loaded_packets: set[str] = set()

    # -- Loading ----------------------------------------------------------

    def load_packet(self, packet: str, config: QCConfig | None = None) -> None:
        """Load all ``*_rules.json`` files from a packet's rules directory."""
        packet = packet.upper()
        if packet in self._loaded_packets:
            return  # idempotent

        cfg = config if config is not None else get_config()
        rules_path = cfg.get_rules_path_for_packet(packet)
        rules_dir = Path(rules_path)

        if not rules_dir.exists():
            msg = "Rules path for packet '%s' does not exist: %s" % (packet, rules_path)
            raise FileNotFoundError(msg)

        rule_files = sorted(rules_dir.glob(self._GLOB))

        # Filter out *_rules_optional.json explicitly
        rule_files = [f for f in rule_files if not f.stem.endswith("_rules_optional")]

        if not rule_files:
            logger.warning("No *_rules.json files found in %s", rules_dir)
            self._loaded_packets.add(packet)
            return

        for rule_file in rule_files:
            namespace = self._namespace_from_path(rule_file)
            self._load_file(rule_file, namespace)

        # Check if conflicts are expected (e.g., C2/C2T dynamic routing)
        if self._conflicts:
            unexpected_conflicts = self._get_unexpected_conflicts()

            if unexpected_conflicts:
                # Warn about unexpected conflicts
                logger.warning(
                    "Unexpected namespace conflicts detected for %d variable(s): %s",
                    len(unexpected_conflicts),
                    ", ".join(sorted(unexpected_conflicts)[:10])
                    + (" ..." if len(unexpected_conflicts) > 10 else ""),
                )
            else:
                # All conflicts are expected (e.g., C2/C2T), log at debug level
                logger.debug(
                    "Expected namespace conflicts for %d variable(s) (C2/C2T dynamic routing)",
                    len(self._conflicts),
                )

        self._loaded_packets.add(packet)
        logger.debug(
            "Loaded %d rules for packet %s from %d files (%d conflicts across %d namespaces)",
            len(self._rules),
            packet,
            len(rule_files),
            len(self._conflicts),
            len(self._namespaced),
        )

    def _load_file(self, path: Path, namespace: str) -> None:
        """Parse a single JSON file and index its variables."""
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in rule file %s, skipping", path.name)
            return

        if not isinstance(data, dict):
            logger.warning("Rule file %s does not contain a dict, skipping", path.name)
            return

        ns_dict = self._namespaced.setdefault(namespace, {})

        for variable, rule_body in data.items():
            entry = RuleEntry(
                variable=variable,
                rule=rule_body,
                source_file=path.name,
                namespace=namespace,
            )

            # Populate namespace index unconditionally
            ns_dict[variable] = entry

            # Flat index: first-wins (files sorted alphabetically)
            if variable in self._rules:
                # Already present from a different namespace → conflict
                if self._rules[variable].namespace != namespace:
                    self._conflicts.add(variable)
                    # Track which namespaces are involved in this conflict
                    if variable not in self._conflict_namespaces:
                        self._conflict_namespaces[variable] = set()
                    self._conflict_namespaces[variable].add(self._rules[variable].namespace)
                    self._conflict_namespaces[variable].add(namespace)
            else:
                self._rules[variable] = entry

    # -- Lookup -----------------------------------------------------------

    def get_rule(self, variable: str, namespace: str | None = None) -> RuleEntry | None:
        """O(1) rule lookup. Use *namespace* for conflict disambiguation."""
        if namespace is not None and variable in self._conflicts:
            ns_dict = self._namespaced.get(namespace, {})
            return ns_dict.get(variable)
        return self._rules.get(variable)

    def get_all_rules(self) -> dict[str, RuleEntry]:
        """Return the flat index (first-wins for conflicts)."""
        return dict(self._rules)

    def get_all_rules_for_namespace(self, namespace: str) -> dict[str, RuleEntry]:
        """Get all rules from a specific source file/namespace."""
        return dict(self._namespaced.get(namespace, {}))

    def get_resolved_rules_dict(self, namespace: str | None = None) -> dict[str, dict[str, Any]]:
        """
        Return ``{variable: rule_dict}`` suitable for schema building.

        If *namespace* is given, ONLY rules from that namespace are returned
        (strict namespace filtering). Otherwise the flat index (first-wins) is returned.
        """
        result: dict[str, dict[str, Any]] = {}

        # When namespace is specified, return ONLY variables from that namespace
        if namespace:
            ns_dict = self._namespaced.get(namespace, {})
            for var, entry in ns_dict.items():
                result[var] = entry.rule
        else:
            # No namespace specified: return flat index (first-wins for conflicts)
            for var, entry in self._rules.items():
                result[var] = entry.rule

        return result

    # -- Helpers ----------------------------------------------------------

    def _get_unexpected_conflicts(self) -> set[str]:
        """
        Return variables with conflicts that are NOT in expected namespace pairs.

        Expected conflicts (e.g., C2/C2T) use discriminant variables for dynamic
        routing and are intentional. Unexpected conflicts indicate a configuration
        issue.
        """
        unexpected = set()
        for variable, namespaces in self._conflict_namespaces.items():
            # Check if this is an expected conflict
            # For expected pairs, the conflict should only involve those two namespaces
            is_expected = False
            for ns1, ns2 in self._EXPECTED_CONFLICT_PAIRS:
                if namespaces == {ns1, ns2}:
                    is_expected = True
                    break

            if not is_expected:
                unexpected.add(variable)

        return unexpected

    @staticmethod
    def _namespace_from_path(path: Path) -> str:
        """Derive namespace from file stem: ``c2_rules.json`` → ``c2``."""
        stem = path.stem  # e.g. "c2_rules"
        if stem.endswith("_rules"):
            return stem[: -len("_rules")]
        return stem

    # -- Properties -------------------------------------------------------

    @property
    def conflict_variables(self) -> frozenset[str]:
        """Variables existing in 2+ rule files."""
        return frozenset(self._conflicts)

    @property
    def loaded_packets(self) -> frozenset[str]:
        """Packets that have been loaded."""
        return frozenset(self._loaded_packets)

    # -- Lifecycle --------------------------------------------------------

    def clear(self) -> None:
        """Reset pool state."""
        self._rules.clear()
        self._namespaced.clear()
        self._conflicts.clear()
        self._conflict_namespaces.clear()
        self._loaded_packets.clear()

    def __len__(self) -> int:
        return len(self._rules)

    def __repr__(self) -> str:
        return "NamespacedRulePool(rules=%d, namespaces=%d, conflicts=%d)" % (
            len(self._rules),
            len(self._namespaced),
            len(self._conflicts),
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_pool: NamespacedRulePool | None = None


def get_pool(config: QCConfig | None = None) -> NamespacedRulePool:
    """Get or create the module-level rule pool singleton."""
    global _pool
    if _pool is None:
        _pool = NamespacedRulePool()
    return _pool


def reset_pool() -> None:
    """Reset the module-level pool (for testing)."""
    global _pool
    if _pool is not None:
        _pool.clear()
    _pool = None
