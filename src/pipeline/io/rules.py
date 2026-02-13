"""
Rule loading and management for the QC pipeline.

This module provides functions for loading JSON validation rules, managing rule caches,
and handling both standard and dynamic instruments.
"""

import json
from pathlib import Path
from typing import Any

from ..config.config_manager import (
    get_config,
    get_rule_mappings,
    instrument_json_mapping,
    is_dynamic_rule_instrument,
)
from ..logging.logging_config import get_logger

logger = get_logger(__name__)


# =============================================================================
# CORE ERRORS
# =============================================================================


class RulesLoadingError(Exception):
    """Error loading validation rules."""


# =============================================================================
# DYNAMIC INSTRUMENT RULE LOADING
# =============================================================================


def load_dynamic_rules_for_instrument(instrument_name: str) -> dict[str, dict[str, Any]]:
    """
    Loads rules for instruments that use dynamic rule selection.

    For a given dynamic instrument, this function reads the rule mappings from
    the configuration, finds the corresponding JSON files, and loads them into
    a dictionary.

    Args:
        instrument_name: The name of the instrument.

    Returns:
        A dictionary mapping each rule variant (e.g., 'C2', 'C2T') to its
        corresponding rule dictionary.

    Raises:
        ValueError: If the instrument is not configured for dynamic rules or
                    if the JSON rules path is not configured.
        FileNotFoundError: If a specified rule file does not exist.
        json.JSONDecodeError: If a rule file contains invalid JSON.
    """
    if not is_dynamic_rule_instrument(instrument_name):
        msg = f"Instrument '{instrument_name}' is not configured for dynamic rule selection."
        raise ValueError(msg)

    config = get_config()
    # Use I packet path as default for dynamic instruments
    json_rules_dir = config.json_rules_path_i
    if not json_rules_dir:
        msg = "JSON_RULES_PATH_I is not configured. Please check your environment settings."
        raise ValueError(msg)

    json_rules_path = Path(json_rules_dir)
    rule_mappings = get_rule_mappings(instrument_name)
    rule_map = {}
    routes_loaded = []

    for variant, filename in rule_mappings.items():
        file_path = json_rules_path / filename
        try:
            with file_path.open("r", encoding="utf-8") as f:
                rules = json.load(f)
                rule_map[variant] = rules
            routes_loaded.append(f"{variant} ({len(rules)} rules)")
        except FileNotFoundError:
            logger.exception("Rule file not found: %s", file_path)
            raise
        except json.JSONDecodeError:
            logger.exception("Invalid JSON in rule file: %s", file_path)
            raise
        except Exception:
            logger.exception("An unexpected error occurred while loading %s", file_path)
            raise

    logger.debug("Loaded dynamic rules for %s: %s", instrument_name, ", ".join(routes_loaded))
    return rule_map


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


def merge_rule_dictionaries(rule_dicts: list[dict[str, Any]]) -> dict[str, Any]:
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
            self._cache[instrument] = load_json_rules_for_instrument(instrument)
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


def load_rules_for_instruments(instrument_list: list[str]) -> dict[str, dict[str, Any]]:
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



