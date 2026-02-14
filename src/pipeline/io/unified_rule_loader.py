"""
Unified rule loader for the QC pipeline.

This module provides functionality to load and merge all rules for a packet
into a single schema, eliminating the need for instrument-based routing while
maintaining support for dynamic rule resolution (e.g., C2/C2T).
"""

import json
from pathlib import Path
from typing import Any

from ..config.config_manager import QCConfig, get_config, is_dynamic_rule_instrument
from ..logging.logging_config import get_logger

logger = get_logger(__name__)


class UnifiedRuleLoader:
    """
    Loads and merges all rules for a packet into a single schema.
    
    This loader eliminates instrument-based routing by loading all rules for a packet
    at once and merging them into a single variable-keyed dictionary. Dynamic rule
    resolution (e.g., C2/C2T) is still supported through discriminant variables.
    """

    def __init__(self, config: QCConfig | None = None):
        """
        Initialize the unified rule loader.

        Args:
            config: Optional QCConfig instance. If not provided, will use get_config()
        """
        self.config = config if config is not None else get_config()
        self._packet_cache: dict[str, dict[str, Any]] = {}
        self._cache_stats = {"hits": 0, "misses": 0}
        logger.debug("UnifiedRuleLoader initialized")

    def load_packet_rules(self, packet: str) -> dict[str, Any]:
        """
        Load ALL rules for a packet, merging all rule files.

        This method loads every JSON rule file in the packet's rules directory
        and merges them into a single dictionary keyed by variable name.

        Args:
            packet: Packet type (I, I4, F)

        Returns:
            Dictionary of {variable_name: rule_dict} for all variables in packet

        Raises:
            ValueError: If packet is invalid or rules path not configured
            FileNotFoundError: If rules path does not exist
            RuntimeError: If rules cannot be loaded
        """
        packet = packet.upper()
        
        # Check cache first
        if packet in self._packet_cache:
            self._cache_stats["hits"] += 1
            logger.debug(f"Cache hit for packet {packet}")
            return self._packet_cache[packet]
        
        self._cache_stats["misses"] += 1
        logger.debug(f"Cache miss for packet {packet} - loading rules")
        
        # Validate packet type
        if packet not in ["I", "I4", "F"]:
            raise ValueError(
                f"Invalid packet value '{packet}'. Valid packet values are: I, I4, F"
            )
        
        # Get rules path for packet
        try:
            rules_path = self.config.get_rules_path_for_packet(packet)
        except ValueError as e:
            logger.error(f"Failed to get rules path for packet {packet}: {e}")
            raise
        
        rules_path_obj = Path(rules_path)
        if not rules_path_obj.exists():
            raise FileNotFoundError(
                f"Rules path for packet '{packet}' does not exist: {rules_path}"
            )
        
        # Load and merge all rule files
        try:
            all_rules = self._load_and_merge_rules(rules_path_obj, packet)
            self._packet_cache[packet] = all_rules
            
            logger.info(
                f"Loaded {len(all_rules)} total rules for packet {packet} "
                f"from {rules_path}"
            )
            return all_rules
            
        except Exception as e:
            logger.error(f"Failed to load rules for packet {packet}: {e}")
            raise RuntimeError(
                f"Failed to load rules for packet {packet} from {rules_path}: {e}"
            ) from e

    def _load_and_merge_rules(
        self, rules_path: Path, packet: str
    ) -> dict[str, Any]:
        """
        Load all JSON files in a directory and merge them into a single dictionary.

        Args:
            rules_path: Path to the rules directory
            packet: Packet type (for logging)

        Returns:
            Merged dictionary of all rules

        Raises:
            json.JSONDecodeError: If a rule file contains invalid JSON
            IOError: If a rule file cannot be read
        """
        all_rules = {}
        rule_files = sorted(rules_path.glob("*.json"))
        
        if not rule_files:
            logger.warning(f"No rule files found in {rules_path}")
            return all_rules
        
        file_stats = []
        for rule_file in rule_files:
            try:
                with rule_file.open("r", encoding="utf-8") as f:
                    file_rules = json.load(f)
                
                if not isinstance(file_rules, dict):
                    logger.warning(
                        f"Rule file {rule_file.name} does not contain a dictionary, skipping"
                    )
                    continue
                
                # Check for variable name collisions
                collisions = set(all_rules.keys()) & set(file_rules.keys())
                if collisions:
                    logger.warning(
                        f"Variable name collisions detected in {rule_file.name}: "
                        f"{collisions}. Later definitions will override earlier ones."
                    )
                
                # Merge rules
                all_rules.update(file_rules)
                file_stats.append(f"{rule_file.name}: {len(file_rules)} rules")
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in rule file {rule_file}: {e}")
                raise
            except IOError as e:
                logger.error(f"Failed to read rule file {rule_file}: {e}")
                raise
        
        logger.debug(
            f"Merged {len(rule_files)} rule files for packet {packet}: "
            f"{', '.join(file_stats)}"
        )
        
        return all_rules

    def get_rules_for_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """
        Get applicable rules for a record.

        This method loads the base rules for the record's packet and applies
        dynamic resolution if needed (e.g., C2/C2T discriminant variables).

        Args:
            record: Data record with packet field

        Returns:
            Merged rules dictionary for all variables applicable to the record

        Raises:
            ValueError: If packet is missing or invalid
        """
        packet = record.get("packet", "").upper()
        
        if not packet:
            raise ValueError(
                "Missing packet value in record. "
                "Packet-based routing requires valid packet field (I, I4, or F)."
            )
        
        # Get base rules for packet
        base_rules = self.load_packet_rules(packet)
        
        # Apply dynamic resolution if needed
        resolved_rules = self._resolve_dynamic_rules(record, base_rules)
        
        return resolved_rules

    def _resolve_dynamic_rules(
        self, record: dict[str, Any], base_rules: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Apply discriminant-based rule selection for dynamic instruments.

        Currently handles C2/C2T discriminant variable. In the unified loader,
        all rules are already loaded, so this method doesn't need to load
        additional files - it only needs to filter or adjust rules based on
        discriminant values if needed.

        For now, since all rules are merged and the validation engine handles
        allow_unknown=True, we can simply return the base rules. The existing
        dynamic routing logic in HierarchicalRuleResolver will continue to work.

        Args:
            record: Data record that may contain discriminant variables
            base_rules: Base rules loaded for the packet

        Returns:
            Rules dictionary (potentially filtered or adjusted)
        """
        # Future enhancement: Implement discriminant-based filtering here
        # For now, return all rules and let the validation engine handle it
        # with allow_unknown=True
        
        # Check if record has C2/C2T discriminant
        if "loc_c2_or_c2t" in record:
            discriminant = record["loc_c2_or_c2t"]
            logger.debug(
                f"Record contains C2/C2T discriminant: {discriminant}. "
                "Dynamic routing will be handled by HierarchicalRuleResolver."
            )
        
        return base_rules

    def clear_cache(self) -> None:
        """Clear the rule cache."""
        self._packet_cache.clear()
        logger.debug("Rule cache cleared")

    def get_cache_stats(self) -> dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache hit/miss counts
        """
        return {
            "hits": self._cache_stats["hits"],
            "misses": self._cache_stats["misses"],
            "cached_packets": len(self._packet_cache),
        }
