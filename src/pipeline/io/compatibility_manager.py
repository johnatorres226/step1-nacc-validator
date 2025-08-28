"""
Backward compatibility and migration management for packet-based routing.

This module provides temporary compatibility features to enable gradual migration
from legacy single-path rule loading to packet-based routing. All components in
this module are marked for future removal once migration is complete.

DEPRECATION WARNING: This entire module is temporary and will be removed in a
future version once migration to packet-based routing is complete.
"""

from typing import Dict, Any, Optional, Union
from enum import Enum
import warnings
from dataclasses import dataclass

from ..config_manager import QCConfig, get_config
from ..logging_config import get_logger
from ..utils.instrument_mapping import load_json_rules_for_instrument
from .packet_router import PacketRuleRouter
from .hierarchical_router import HierarchicalRuleResolver

logger = get_logger(__name__)


class RoutingMode(Enum):
    """Routing mode enumeration for migration control."""
    LEGACY = "legacy"                    # Single-path rule loading (deprecated)
    PACKET_BASIC = "packet_basic"        # Phase 1 packet routing
    PACKET_HIERARCHICAL = "hierarchical" # Phase 2 hierarchical routing
    AUTO_DETECT = "auto_detect"          # Automatic detection based on config


@dataclass
class MigrationSettings:
    """
    Configuration for migration behavior.
    
    DEPRECATION WARNING: This class is temporary and will be removed once
    migration to packet-based routing is complete.
    """
    # Migration control
    force_legacy: bool = False           # Force legacy mode (for rollback)
    enable_a_b_testing: bool = False     # Enable A/B testing between modes
    migration_warnings: bool = True      # Show deprecation warnings
    
    # Performance monitoring
    track_performance: bool = True       # Track performance metrics
    log_routing_decisions: bool = False  # Log routing mode decisions
    
    # Fallback behavior
    strict_mode: bool = False           # Fail fast on missing packet configs
    default_packet: str = "I"          # Default packet for legacy fallback


class CompatibilityManager:
    """
    Manages backward compatibility during migration from legacy to packet-based routing.
    
    This class provides a unified interface that can operate in multiple modes:
    - Legacy mode: Original single-path rule loading (deprecated)
    - Packet mode: Phase 1 packet-based routing
    - Hierarchical mode: Phase 2 enhanced dynamic routing
    
    DEPRECATION WARNING: This class is temporary and will be removed once
    migration to packet-based routing is complete.
    
    Items marked for future removal:
    - CompatibilityManager class
    - MigrationSettings dataclass
    - RoutingMode.LEGACY enum value
    - All legacy_mode related functionality
    - get_rules_with_fallback method fallback to legacy
    - Performance comparison utilities for legacy vs packet routing
    """
    
    def __init__(self, config: Optional[QCConfig] = None, settings: Optional[MigrationSettings] = None):
        """
        Initialize the compatibility manager.
        
        Args:
            config: Optional QCConfig instance
            settings: Optional migration settings
        """
        self.config = config if config is not None else get_config()
        self.settings = settings if settings is not None else MigrationSettings()
        
        # Initialize routers
        self.packet_router = PacketRuleRouter(self.config)
        self.hierarchical_resolver = HierarchicalRuleResolver(self.config)
        
        # Determine routing mode
        self.routing_mode = self._determine_routing_mode()
        
        # Performance tracking (temporary - will be removed)
        self._performance_stats = {
            'legacy_calls': 0,
            'packet_calls': 0,
            'hierarchical_calls': 0,
            'fallback_events': 0
        }
        
        if self.settings.migration_warnings and self.routing_mode == RoutingMode.LEGACY:
            warnings.warn(
                "Using legacy routing mode. This is deprecated and will be removed. "
                "Please configure packet-specific rule paths to enable packet-based routing.",
                DeprecationWarning,
                stacklevel=2
            )
        
        logger.info(f"CompatibilityManager initialized in {self.routing_mode.value} mode")
    
    def _determine_routing_mode(self) -> RoutingMode:
        """
        Determine the appropriate routing mode based on configuration.
        
        DEPRECATED: This method will be removed once migration is complete.
        """
        if self.settings.force_legacy:
            return RoutingMode.LEGACY
        
        # Check if packet-specific paths are configured
        packet_paths_configured = all([
            self.config.json_rules_path_i,
            self.config.json_rules_path_i4,
            self.config.json_rules_path_f
        ])
        
        if packet_paths_configured:
            # Default to hierarchical mode if available
            return RoutingMode.PACKET_HIERARCHICAL
        elif any([self.config.json_rules_path_i, self.config.json_rules_path_i4, self.config.json_rules_path_f]):
            # Partial packet configuration - use basic packet routing
            return RoutingMode.PACKET_BASIC
        else:
            # No packet configuration - fall back to legacy
            return RoutingMode.LEGACY
    
    def get_rules_with_fallback(self, record: Dict[str, Any], instrument_name: str) -> Dict[str, Any]:
        """
        Get rules with fallback to legacy behavior for backward compatibility.
        
        This method provides a unified interface that automatically routes to the
        appropriate rule loading mechanism based on configuration and migration settings.
        
        DEPRECATION WARNING: The legacy fallback functionality in this method
        will be removed once migration is complete.
        
        Args:
            record: The data record (may contain packet information)
            instrument_name: Name of the instrument to get rules for
            
        Returns:
            Dictionary containing the validation rules
        """
        if self.settings.log_routing_decisions:
            logger.debug(f"Getting rules for {instrument_name} using {self.routing_mode.value} mode")
        
        try:
            if self.routing_mode == RoutingMode.LEGACY:
                # DEPRECATED: Legacy single-path rule loading (to be removed)
                self._performance_stats['legacy_calls'] += 1
                if self.settings.migration_warnings:
                    logger.warning(f"Using deprecated legacy rule loading for {instrument_name}")
                return self._load_legacy_rules(instrument_name)
            
            elif self.routing_mode == RoutingMode.PACKET_BASIC:
                # Phase 1 packet routing
                self._performance_stats['packet_calls'] += 1
                return self.packet_router.get_rules_for_record(record, instrument_name)
            
            elif self.routing_mode == RoutingMode.PACKET_HIERARCHICAL:
                # Phase 2 hierarchical routing
                self._performance_stats['hierarchical_calls'] += 1
                return self.hierarchical_resolver.resolve_rules(record, instrument_name)
            
            else:
                raise ValueError(f"Unknown routing mode: {self.routing_mode}")
                
        except Exception as e:
            logger.error(f"Failed to load rules for {instrument_name}: {e}")
            
            if self.settings.strict_mode:
                raise
            
            # Fallback to legacy if packet routing fails (temporary safety net)
            self._performance_stats['fallback_events'] += 1
            logger.warning(f"Falling back to legacy rule loading for {instrument_name}")
            return self._load_legacy_rules(instrument_name)
    
    def _load_legacy_rules(self, instrument_name: str) -> Dict[str, Any]:
        """
        Load rules using legacy single-path method.
        
        DEPRECATED: This method will be removed once migration is complete.
        """
        try:
            return load_json_rules_for_instrument(instrument_name)
        except Exception as e:
            logger.error(f"Legacy rule loading failed for {instrument_name}: {e}")
            return {}
    
    def get_routing_mode(self) -> RoutingMode:
        """Get the current routing mode."""
        return self.routing_mode
    
    def is_legacy_mode(self) -> bool:
        """
        Check if currently operating in legacy mode.
        
        DEPRECATED: This method will be removed once migration is complete.
        """
        return self.routing_mode == RoutingMode.LEGACY
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics for migration monitoring.
        
        DEPRECATED: This method will be removed once migration is complete.
        """
        return {
            'routing_mode': self.routing_mode.value,
            'stats': self._performance_stats.copy(),
            'packet_paths_configured': all([
                self.config.json_rules_path_i,
                self.config.json_rules_path_i4,
                self.config.json_rules_path_f
            ])
        }
    
    def reset_performance_stats(self) -> None:
        """
        Reset performance statistics.
        
        DEPRECATED: This method will be removed once migration is complete.
        """
        self._performance_stats = {
            'legacy_calls': 0,
            'packet_calls': 0,
            'hierarchical_calls': 0,
            'fallback_events': 0
        }
    
    def validate_migration_readiness(self) -> Dict[str, Any]:
        """
        Validate readiness for migration to packet-based routing.
        
        Returns a report on migration readiness and any issues that need
        to be addressed before migration can be completed.
        
        DEPRECATED: This method will be removed once migration is complete.
        """
        report = {
            'ready_for_migration': True,
            'current_mode': self.routing_mode.value,
            'issues': [],
            'recommendations': []
        }
        
        # Check packet path configuration
        packet_paths = {
            'I': self.config.json_rules_path_i,
            'I4': self.config.json_rules_path_i4,
            'F': self.config.json_rules_path_f
        }
        
        missing_paths = [packet for packet, path in packet_paths.items() if not path]
        if missing_paths:
            report['ready_for_migration'] = False
            report['issues'].append(f"Missing packet paths: {missing_paths}")
            report['recommendations'].append("Configure environment variables: " + 
                                           ", ".join([f"JSON_RULES_PATH_{p}" for p in missing_paths]))
        
        # Check rule file existence
        from pathlib import Path
        missing_rule_dirs = []
        for packet, path in packet_paths.items():
            if path and not Path(path).exists():
                missing_rule_dirs.append(f"{packet}: {path}")
        
        if missing_rule_dirs:
            report['ready_for_migration'] = False
            report['issues'].append(f"Missing rule directories: {missing_rule_dirs}")
            report['recommendations'].append("Create missing rule directories and populate with rule files")
        
        # Check performance impact
        if self._performance_stats['fallback_events'] > 0:
            report['issues'].append(f"Fallback events detected: {self._performance_stats['fallback_events']}")
            report['recommendations'].append("Investigate and resolve causes of fallback events")
        
        return report


class MigrationValidator:
    """
    Validates data and configuration for packet-based routing migration.
    
    DEPRECATED: This class will be removed once migration is complete.
    """
    
    def __init__(self, config: Optional[QCConfig] = None):
        """Initialize the migration validator."""
        self.config = config if config is not None else get_config()
    
    def validate_packet_data_coverage(self, data_sample: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that sample data contains expected packet values.
        
        DEPRECATED: This method will be removed once migration is complete.
        """
        packet_counts = {}
        missing_packet_count = 0
        
        # Analyze packet distribution (this would typically analyze a DataFrame)
        # For now, assume data_sample contains packet distribution info
        for packet in ['I', 'I4', 'F']:
            count = data_sample.get(f'packet_{packet}_count', 0)
            packet_counts[packet] = count
        
        missing_packet_count = data_sample.get('missing_packet_count', 0)
        
        total_records = sum(packet_counts.values()) + missing_packet_count
        
        return {
            'packet_distribution': packet_counts,
            'missing_packet_records': missing_packet_count,
            'total_records': total_records,
            'coverage_percentage': (total_records - missing_packet_count) / total_records * 100 if total_records > 0 else 0,
            'migration_safe': missing_packet_count / total_records < 0.05 if total_records > 0 else False  # Less than 5% missing
        }


def create_compatibility_manager(
    config: Optional[QCConfig] = None,
    migration_settings: Optional[MigrationSettings] = None
) -> CompatibilityManager:
    """
    Factory function to create a CompatibilityManager instance.
    
    DEPRECATED: This function will be removed once migration is complete.
    
    Args:
        config: Optional QCConfig instance
        migration_settings: Optional migration settings
        
    Returns:
        CompatibilityManager instance
    """
    return CompatibilityManager(config, migration_settings)
