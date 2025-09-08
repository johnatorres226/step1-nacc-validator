"""
Hierarchical rule resolution for enhanced dynamic routing.

This module provides the HierarchicalRuleResolver class that combines packet-based routing
with dynamic instrument routing (e.g., C2/C2T forms) to provide intelligent rule resolution
with multiple layers of routing logic.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from ..config_manager import (
    QCConfig, get_config, is_dynamic_rule_instrument,
    get_discriminant_variable, get_rule_mappings
)
from ..logging_config import get_logger
from .packet_router import PacketRuleRouter

logger = get_logger(__name__)


class HierarchicalRuleResolver:
    """
    Resolves rules with packet + dynamic instrument routing.
    
    This class combines the packet-based routing from Phase 1 with the existing
    dynamic instrument routing to provide a comprehensive rule resolution system
    that handles both packet types (I, I4, F) and instrument variants (C2, C2T).
    """

    def __init__(self, config: Optional[QCConfig] = None):
        """
        Initialize the hierarchical rule resolver.
        
        Args:
            config: Optional QCConfig instance. If not provided, will use get_config()
        """
        self.config = config if config is not None else get_config()
        self.packet_router = PacketRuleRouter(self.config)
        self._resolution_cache = {}
        self._f_rules_warning_logged = False  # Track if F rules warning has been logged
        logger.debug("HierarchicalRuleResolver initialized")

    def resolve_rules(self, record: Dict[str, Any], instrument_name: str) -> Dict[str, Any]:
        """
        Resolve rules using both packet and dynamic instrument routing.
        
        This method implements a hierarchical resolution strategy:
        1. First, determine the packet type (I, I4, F) and get packet-specific base rules
        2. Then, if the instrument supports dynamic routing, apply variant-specific rules
        3. Return the most specific rule set applicable to the record
        
        Args:
            record: The data record containing packet and discriminant values
            instrument_name: Name of the instrument to get rules for
            
        Returns:
            Dictionary containing the resolved validation rules
        """
        # Step 1: Get packet-specific base rules
        packet = record.get('packet', 'I').upper()

        # Create cache key for performance optimization
        discriminant_value = ''
        if is_dynamic_rule_instrument(instrument_name):
            discriminant_var = get_discriminant_variable(instrument_name)
            discriminant_value = record.get(discriminant_var, '').upper()

        cache_key = f"{packet}_{instrument_name}_{discriminant_value}"

        if cache_key in self._resolution_cache:
            logger.debug(f"Using cached rules for {cache_key}")
            return self._resolution_cache[cache_key]

        # Get packet-specific base rules
        base_rules = self.get_packet_rules(packet, instrument_name)

        # Step 2: Apply dynamic routing if applicable
        resolved_rules = base_rules
        if is_dynamic_rule_instrument(instrument_name):
            resolved_rules = self._apply_dynamic_routing(
                base_rules, record, instrument_name, packet, is_rules_loading=False
            )

        # Cache the resolved rules
        self._resolution_cache[cache_key] = resolved_rules

        logger.debug(f"Resolved rules for {instrument_name} in packet {packet}: {type(resolved_rules)}")
        return resolved_rules

    def load_all_rules_for_instrument(self, instrument_name: str) -> Dict[str, Any]:
        """
        Load all possible rule variants for an instrument during rules loading phase.
        
        This method is specifically designed for the rules loading stage and:
        1. Loads rules for all packet types (I, I4, F)
        2. For dynamic instruments, loads all variants
        3. Returns a comprehensive rule structure for runtime resolution
        4. Suppresses warnings about missing discriminant variables
        
        Args:
            instrument_name: Name of the instrument to load rules for
            
        Returns:
            Dictionary containing all rule variants organized by packet and variant
        """
        all_rules = {}

        # Load rules for all packet types
        for packet in ['I', 'I4', 'F']:
            try:
                base_rules = self.get_packet_rules(packet, instrument_name)

                if is_dynamic_rule_instrument(instrument_name):
                    # For dynamic instruments during rules loading, return the base_rules
                    # which should contain all variants (C2, C2T, etc.)
                    if isinstance(base_rules, dict) and base_rules:
                        all_rules[packet] = base_rules
                        logger.debug(
                            f"Rules loading: Loaded {len(base_rules)} variants for {instrument_name} "
                            f"in packet {packet}: {list(base_rules.keys())}"
                        )
                    else:
                        all_rules[packet] = base_rules
                else:
                    # For non-dynamic instruments, store directly
                    all_rules[packet] = base_rules

            except Exception as e:
                logger.debug(f"Could not load rules for {instrument_name} in packet {packet}: {e}")
                continue

        # Return the most comprehensive rule set found
        # Priority: I4 > I > F (or return the first available)
        for packet in ['I4', 'I', 'F']:
            if packet in all_rules and all_rules[packet]:
                logger.debug(f"Rules loading complete for {instrument_name}, using packet {packet} as template")
                return all_rules[packet]

        logger.warning(f"No rules found for instrument {instrument_name} in any packet")
        return {}

    def get_packet_rules(self, packet: str, instrument_name: str) -> Dict[str, Any]:
        """
        Get packet-specific base rules.
        
        This method delegates to the PacketRuleRouter from Phase 1 to get
        the appropriate rule set for the given packet type.
        
        Args:
            packet: Packet type (I, I4, F)
            instrument_name: Name of the instrument
            
        Returns:
            Dictionary containing packet-specific rules
        """
        # Create a dummy record with the packet value for the PacketRuleRouter
        dummy_record = {'packet': packet}
        return self.packet_router.get_rules_for_record(dummy_record, instrument_name)

    def _apply_dynamic_routing(
        self,
        base_rules: Dict[str, Any],
        record: Dict[str, Any],
        instrument_name: str,
        packet: str,
        is_rules_loading: bool = False
    ) -> Dict[str, Any]:
        """
        Apply dynamic instrument routing to base rules.
        
        Args:
            base_rules: Base rules from packet routing
            record: Data record containing discriminant values
            instrument_name: Name of the instrument
            packet: Packet type for logging purposes
            is_rules_loading: Flag indicating if this is called during rules loading phase
            
        Returns:
            Dictionary containing variant-specific rules
        """
        discriminant_var = get_discriminant_variable(instrument_name)
        discriminant_value = record.get(discriminant_var, '').upper()

        if not discriminant_value:
            # During rules loading, use debug level to avoid false warnings
            # During actual validation, use warning level for data quality issues
            if is_rules_loading:
                logger.debug(
                    f"Rules loading: Missing {discriminant_var} value for {instrument_name} "
                    f"in packet {packet}. Loading all variants for runtime resolution."
                )
            else:
                logger.warning(
                    f"Missing {discriminant_var} value in record for {instrument_name} "
                    f"in packet {packet}. Using default variant rules. "
                    f"Recommendation: Ensure {discriminant_var} field is properly populated in data export."
                )
            # For dynamic instruments, base_rules is a dict with variant keys
            # When discriminant is missing, use the first available variant as default
            if isinstance(base_rules, dict) and base_rules:
                default_variant = list(base_rules.keys())[0]
                logger.info(f"Using default variant '{default_variant}' for {instrument_name}")
                logger.debug(f"base_rules keys: {list(base_rules.keys())}")
                logger.debug(f"Returning rules for variant '{default_variant}': {type(base_rules[default_variant])}")
                return base_rules[default_variant]
            return base_rules

        # Check if the discriminant value exists in the base rules
        if discriminant_value in base_rules:
            logger.debug(
                f"Found variant-specific rules for {discriminant_var}={discriminant_value} "
                f"in {instrument_name} (packet {packet})"
            )
            return base_rules[discriminant_value]
        else:
            logger.warning(
                f"No variant rules found for {discriminant_var}={discriminant_value} "
                f"in packet {packet} for {instrument_name}. Using base rules. "
                f"Action: Verify rules file contains {discriminant_value} variant or check data export."
            )
            return base_rules

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring and optimization.
        
        Returns:
            Dictionary containing cache performance metrics
        """
        packet_cache_stats = self.packet_router.get_cache_stats()
        return {
            'hierarchical_cache_size': len(self._resolution_cache),
            'hierarchical_cache_keys': list(self._resolution_cache.keys()),
            'packet_router_stats': packet_cache_stats
        }

    def clear_cache(self) -> None:
        """
        Clear all cached rules for memory management.
        
        This method clears both the hierarchical cache and the underlying
        packet router cache.
        """
        self._resolution_cache.clear()
        self.packet_router.clear_cache()
        logger.info("Cleared all hierarchical rule resolver caches")

    def preload_rules_for_packet(self, packet: str, instrument_names: list) -> None:
        """
        Preload rules for a specific packet and list of instruments.
        
        This method can be used to warm up the cache for better performance
        when processing large batches of data.
        
        Args:
            packet: Packet type to preload (I, I4, F)
            instrument_names: List of instrument names to preload
        """
        logger.info(f"Preloading rules for packet {packet} and {len(instrument_names)} instruments")

        for instrument_name in instrument_names:
            try:
                # Preload base packet rules
                self.get_packet_rules(packet, instrument_name)

                # If dynamic instrument, preload variant rules
                if is_dynamic_rule_instrument(instrument_name):
                    rule_mappings = get_rule_mappings(instrument_name)
                    discriminant_var = get_discriminant_variable(instrument_name)

                    for variant in rule_mappings.keys():
                        dummy_record = {'packet': packet, discriminant_var: variant}
                        self.resolve_rules(dummy_record, instrument_name)

            except Exception as e:
                logger.error(
                    f"Failed to preload rules for {instrument_name} in packet {packet}: {e}. "
                    f"Action: Verify rules directory structure and file accessibility for packet {packet}."
                )

        logger.info(f"Preloading completed for packet {packet}")
