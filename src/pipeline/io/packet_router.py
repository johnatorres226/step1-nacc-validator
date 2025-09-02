"""
Packet-based rule routing for the QC pipeline.

This module provides functionality to route records to appropriate rule sets based on their
packet value (I, I4, F) while maintaining compatibility with existing dynamic instrument routing.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json

from ..config_manager import QCConfig, get_config
from ..logging_config import get_logger
from ..utils.instrument_mapping import load_json_rules_for_instrument

logger = get_logger(__name__)


class PacketRuleRouter:
    """Routes records to appropriate rule sets based on packet value."""
    
    def __init__(self, config: Optional[QCConfig] = None):
        """
        Initialize the packet rule router.
        
        Args:
            config: Optional QCConfig instance. If not provided, will use get_config()
        """
        self.config = config if config is not None else get_config()
        self._rule_cache = {}
        logger.debug("PacketRuleRouter initialized")
    
    def get_rules_for_record(self, record: Dict[str, Any], instrument_name: str) -> Dict[str, Any]:
        """
        Get appropriate rules for a record based on its packet value.
        
        Args:
            record: The data record containing the packet value
            instrument_name: Name of the instrument to get rules for
            
        Returns:
            Dictionary containing the validation rules for the record
            
        Raises:
            ValueError: If packet value is missing or invalid
        """
        packet = record.get('packet', '').upper()
        
        if not packet:
            raise ValueError(
                f"Missing packet value in record for {instrument_name}. "
                f"Packet-based routing requires valid packet field (I, I4, or F)."
            )
        
        if packet not in ['I', 'I4', 'F']:
            raise ValueError(
                f"Invalid packet value '{packet}' for {instrument_name}. "
                f"Valid packet values are: I, I4, F"
            )
        
        cache_key = f"{packet}_{instrument_name}"
        
        if cache_key not in self._rule_cache:
            rules_path = self.config.get_rules_path_for_packet(packet)
            self._rule_cache[cache_key] = self._load_rules(rules_path, instrument_name, packet)
            logger.debug(f"Loaded rules for {cache_key} from {rules_path}")
        
        return self._rule_cache[cache_key]
        
        return self._rule_cache[cache_key]
    
    def _load_rules(self, rules_path: str, instrument_name: str, packet: str) -> Dict[str, Any]:
        """Load rules from specific packet directory - no fallbacks."""
        if not rules_path or not Path(rules_path).exists():
            raise FileNotFoundError(
                f"Required rules path not found for packet '{packet}': {rules_path}. "
                f"Ensure environment variable JSON_RULES_PATH_{packet} is properly configured."
            )
        
        try:
            return self._load_rules_from_path(rules_path, instrument_name)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load rules for {instrument_name} from {rules_path}: {e}"
            ) from e
    
    def _load_rules_from_path(self, rules_path: str, instrument_name: str) -> Dict[str, Any]:
        """
        Load rules from a specific path using the existing instrument mapping.
        
        For dynamic instruments, this builds the nested structure that 
        HierarchicalRuleResolver expects.
        
        Args:
            rules_path: Path to the rules directory
            instrument_name: Name of the instrument
            
        Returns:
            Dictionary containing the loaded rules
        """
        from ..config_manager import is_dynamic_rule_instrument, get_rule_mappings
        
        # Handle dynamic instruments differently - they need nested structure
        if is_dynamic_rule_instrument(instrument_name):
            return self._load_dynamic_rules_from_path(rules_path, instrument_name)
        
        # Standard instruments - merge all rule files as before
        rule_files = self.config.get_instrument_json_mapping().get(instrument_name, [])
        
        if not rule_files:
            logger.warning(f"No JSON rule files found for instrument: {instrument_name}")
            return {}
        
        combined_rules = {}
        rules_dir = Path(rules_path)
        
        for file_name in rule_files:
            file_path = rules_dir / file_name
            if file_path.exists():
                try:
                    with file_path.open('r') as f:
                        file_rules = json.load(f)
                        combined_rules.update(file_rules)
                        logger.debug(f"Loaded {len(file_rules)} rules from {file_path}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in rule file: {file_path} - {e}")
                except Exception as e:
                    logger.error(f"Error loading rule file: {file_path} - {e}")
            else:
                logger.warning(f"Rule file not found: {file_path}")
        
        return combined_rules

    def _load_dynamic_rules_from_path(self, rules_path: str, instrument_name: str) -> Dict[str, Any]:
        """
        Load dynamic instrument rules with nested structure for HierarchicalRuleResolver.
        
        Args:
            rules_path: Path to the rules directory
            instrument_name: Name of the dynamic instrument
            
        Returns:
            Dictionary with variant keys (C2, C2T) containing their respective rules
        """
        from ..config_manager import get_rule_mappings
        
        rule_mappings = get_rule_mappings(instrument_name)
        rule_map = {}
        rules_dir = Path(rules_path)
        
        for variant, filename in rule_mappings.items():
            file_path = rules_dir / filename
            if file_path.exists():
                try:
                    with file_path.open('r') as f:
                        rules = json.load(f)
                        rule_map[variant] = rules
                        logger.debug(f"Loaded {len(rules)} rules for {variant} from {file_path}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in rule file: {file_path} - {e}")
                except Exception as e:
                    logger.error(f"Error loading rule file: {file_path} - {e}")
            else:
                logger.warning(f"Rule file not found for {variant}: {file_path}")
        
        logger.debug(f"Loaded dynamic rules for {instrument_name}: {list(rule_map.keys())}")
        return rule_map
    
    def is_packet_supported(self, packet: str) -> bool:
        """
        Check if a packet type is supported.
        
        Args:
            packet: Packet type to check
            
        Returns:
            True if the packet type is supported
        """
        packet = packet.upper()
        supported_packets = ['I', 'I4', 'F']
        return packet in supported_packets
    
    def get_available_packets(self) -> list[str]:
        """
        Get list of available packet types based on configured paths.
        
        Returns:
            List of available packet types
        """
        available = []
        if self.config.json_rules_path_i and Path(self.config.json_rules_path_i).exists():
            available.append('I')
        if self.config.json_rules_path_i4 and Path(self.config.json_rules_path_i4).exists():
            available.append('I4')
        if self.config.json_rules_path_f and Path(self.config.json_rules_path_f).exists():
            available.append('F')
        return available
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring and optimization.
        
        Returns:
            Dictionary containing cache performance metrics
        """
        return {
            'cache_size': len(self._rule_cache),
            'cached_keys': list(self._rule_cache.keys())
        }
    
    def clear_cache(self) -> None:
        """
        Clear all cached rules for memory management.
        """
        self._rule_cache.clear()
        logger.info("Cleared packet rule router cache")


def create_packet_router(config: Optional[QCConfig] = None) -> PacketRuleRouter:
    """
    Factory function to create a PacketRuleRouter instance.
    
    Args:
        config: Optional QCConfig instance
        
    Returns:
        PacketRuleRouter instance
    """
    return PacketRuleRouter(config)
