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
        """
        packet = record.get('packet', '').upper()
        
        if not packet:
            logger.warning(f"No packet value found in record for {instrument_name}, using default rules")
            packet = 'I'  # Default fallback
        
        cache_key = f"{packet}_{instrument_name}"
        
        if cache_key not in self._rule_cache:
            rules_path = self.config.get_rules_path_for_packet(packet)
            self._rule_cache[cache_key] = self._load_rules(rules_path, instrument_name, packet)
            logger.debug(f"Loaded rules for {cache_key} from {rules_path}")
        
        return self._rule_cache[cache_key]
    
    def _load_rules(self, rules_path: str, instrument_name: str, packet: str) -> Dict[str, Any]:
        """
        Load rules from specific packet directory.
        
        Args:
            rules_path: Path to the packet-specific rules directory
            instrument_name: Name of the instrument
            packet: Packet type (I, I4, F)
            
        Returns:
            Dictionary containing the loaded rules
        """
        if not rules_path or not Path(rules_path).exists():
            logger.error(f"Rules path not found for packet '{packet}': {rules_path}")
            logger.info(f"Falling back to default rules for {instrument_name}")
            # Fallback to default rules using the original JSON_RULES_PATH
            return self._load_default_rules(instrument_name)
        
        try:
            # Use existing instrument mapping logic with packet-specific path
            # This leverages existing dynamic instrument handling
            return self._load_rules_from_path(rules_path, instrument_name)
        except Exception as e:
            logger.error(f"Failed to load rules for {instrument_name} from {rules_path}: {e}")
            logger.info(f"Falling back to default rules for {instrument_name}")
            return self._load_default_rules(instrument_name)
    
    def _load_rules_from_path(self, rules_path: str, instrument_name: str) -> Dict[str, Any]:
        """
        Load rules from a specific path using the existing instrument mapping.
        
        Args:
            rules_path: Path to the rules directory
            instrument_name: Name of the instrument
            
        Returns:
            Dictionary containing the loaded rules
        """
        # Get the rule files for this instrument from the mapping
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
    
    def _load_default_rules(self, instrument_name: str) -> Dict[str, Any]:
        """
        Load default rules as fallback.
        
        Args:
            instrument_name: Name of the instrument
            
        Returns:
            Dictionary containing the default rules
        """
        try:
            return load_json_rules_for_instrument(instrument_name)
        except Exception as e:
            logger.error(f"Failed to load default rules for {instrument_name}: {e}")
            return {}
    
    def clear_cache(self):
        """Clear the rule cache."""
        self._rule_cache.clear()
        logger.debug("Rule cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the rule cache."""
        return {
            'cache_size': len(self._rule_cache),
            'cached_keys': list(self._rule_cache.keys())
        }
    
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


def create_packet_router(config: Optional[QCConfig] = None) -> PacketRuleRouter:
    """
    Factory function to create a PacketRuleRouter instance.
    
    Args:
        config: Optional QCConfig instance
        
    Returns:
        PacketRuleRouter instance
    """
    return PacketRuleRouter(config)
