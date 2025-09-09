"""
Rule loading and management for the QC pipeline.

This module provides functions for loading JSON validation rules, managing rule caches,
and handling both standard and dynamic instruments.
"""
import json
from pathlib import Path
from typing import Any

from ..config_manager import (
    get_config,
    instrument_json_mapping,
)
from ..logging_config import get_logger


logger = get_logger(__name__)


# =============================================================================
# CORE ERRORS
# =============================================================================

class RulesLoadingError(Exception):
    """Error loading validation rules."""


# =============================================================================
# BROKEN DOWN RULE LOADING FUNCTIONS
# =============================================================================

def resolve_rule_file_paths(instrument_name: str) -> list[Path]:
    """
    Resolve file paths for an instrument's rule files.

    Args:
        instrument_name: The name of the instrument.

    Returns:
        List of Path objects for the instrument's rule files.

    Raises:
        RulesLoadingError: If no rule files are configured for the instrument.
    """
    config = get_config()
    json_rules_path = Path(config.json_rules_path)

    # Get the list of JSON files for the instrument
    rule_files = instrument_json_mapping.get(instrument_name, [])
    if not rule_files:
        _msg = f"No JSON rule files configured for instrument: {instrument_name}"
        raise RulesLoadingError(_msg)

    return [json_rules_path / file_name for file_name in rule_files]


def load_json_file(file_path: Path) -> dict[str, Any]:
    """
    Load and parse a single JSON file with proper error handling.

    Args:
        file_path: Path to the JSON file to load.

    Returns:
        Dictionary containing the parsed JSON data.

    Raises:
        RulesLoadingError: If the file cannot be loaded or parsed.
    """
    try:
        if not file_path.exists():
            _msg = f"Rule file not found: {file_path}"
            raise RulesLoadingError(_msg)

        # Use Path.open with explicit encoding for cross-platform consistency
        with Path(file_path).open("r", encoding="utf-8") as f:
            return json.load(f)

    except json.JSONDecodeError as e:
        _msg = "Invalid JSON in %s: %s" % (file_path, e)
        raise RulesLoadingError(_msg) from e
    except OSError as e:
        _msg = "Cannot read file %s: %s" % (file_path, e)
        raise RulesLoadingError(_msg) from e


def merge_rule_dictionaries(
        rule_dicts: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Merge multiple rule dictionaries into one.

    Args:
        rule_dicts: List of rule dictionaries to merge.

    Returns:
        Single dictionary containing all merged rules.
    """
    combined_rules = {}
    for rules in rule_dicts:
        combined_rules.update(rules)
    return combined_rules


def load_json_rules_for_instrument(instrument_name: str) -> dict[str, Any]:
    """
    Loads all JSON validation rules for a given instrument.

    Orchestrates loading of all rule files for an instrument and merges them
    into a single dictionary.

    Args:
        instrument_name: The name of the instrument.

    Returns:
        A dictionary containing the combined validation rules.

    Raises:
        RulesLoadingError: If rules cannot be loaded for the instrument.
    """
    try:
        file_paths = resolve_rule_file_paths(instrument_name)

        # Load all rule files
        rule_dicts = []
        for file_path in file_paths:
            try:
                rules = load_json_file(file_path)
                rule_dicts.append(rules)
            except RulesLoadingError as e:
                logger.warning("Skipping rule file %s: %s", file_path, e)
                continue

        if not rule_dicts:
            logger.warning("No valid rule files loaded for instrument: %s", instrument_name)
            return {}

        return merge_rule_dictionaries(rule_dicts)

    except RulesLoadingError as e:
        logger.exception("Failed to load rules for instrument %s: %s", instrument_name, e)
        return {}


# =============================================================================
# RULES CACHE MANAGEMENT
# =============================================================================

class RulesCache:
    """Manages caching of instrument rules."""

    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}

    def get_rules(self, instrument: str) -> dict[str, Any]:
        """
        Get rules for instrument, loading if not cached.

        Args:
            instrument: Name of the instrument.

        Returns:
            Dictionary of rules for the instrument.
        """
        if instrument not in self._cache:
            self._cache[instrument] = load_json_rules_for_instrument(
                instrument)
        return self._cache[instrument]

    def load_multiple(self, instruments: list[str]) -> None:
        """
        Load rules for multiple instruments into cache.

        Args:
            instruments: List of instrument names to load.
        """
        for instrument in instruments:
            self.get_rules(instrument)  # This will cache if not already cached

    def clear(self) -> None:
        """Clear the rules cache."""
        self._cache.clear()

    def get_cache_dict(self) -> dict[str, dict[str, Any]]:
        """
        Get the underlying cache dictionary.

        Returns:
            The complete cache dictionary.
        """
        return self._cache.copy()


def load_rules_for_instruments(
        instrument_list: list[str]) -> dict[str, dict[str, Any]]:
    """
    Load rules for multiple instruments using cache.

    Args:
        instrument_list: A list of instrument names.

    Returns:
        A dictionary (cache) mapping instrument names to their validation rules.
    """
    cache = RulesCache()
    cache.load_multiple(instrument_list)
    return cache.get_cache_dict()


# =============================================================================
# LEGACY COMPATIBILITY (DEPRECATED)
# =============================================================================

# Keep the original function for backward compatibility during transition
def load_json_rules_for_instrument_legacy(
        instrument_name: str) -> dict[str, Any]:
    """
    DEPRECATED: Use load_json_rules_for_instrument() instead.

    Legacy function maintained for backward compatibility during refactoring.
    """
    import warnings
    warnings.warn(
        "load_json_rules_for_instrument_legacy is deprecated. "
        "Use load_json_rules_for_instrument() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return load_json_rules_for_instrument(instrument_name)
