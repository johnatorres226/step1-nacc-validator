"""
This module handles the loading and mapping of validation rules from JSON files.

It supports both static and dynamic rule loading based on the instrument's
configuration. For dynamic instruments, it can load different sets of rules
for the same instrument based on a discriminant variable in the data.
"""

import json
from pathlib import Path
from typing import Any

from src.pipeline.config_manager import (
    get_config,
    get_rule_mappings,
    instrument_json_mapping,
    is_dynamic_rule_instrument,
)
from src.pipeline.logging_config import get_logger


logger = get_logger(__name__)


def load_dynamic_rules_for_instrument(
        instrument_name: str) -> dict[str, dict[str, Any]]:
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
            with file_path.open("r") as f:
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


def load_json_rules_for_instrument(instrument_name: str) -> dict[str, Any]:
    """
    Loads all JSON validation rules for a given standard instrument.

    It looks up the required JSON files from the `instrument_json_mapping`
    in the configuration and merges them into a single dictionary.

    Args:
        instrument_name: The name of the instrument.

    Returns:
        A dictionary containing the combined validation rules.
    """
    config = get_config()
    # Use I packet path as default for general rule loading
    json_rules_dir = config.json_rules_path_i
    if not json_rules_dir:
        msg = "JSON_RULES_PATH_I is not configured. Please check your environment settings."
        raise ValueError(msg)

    rule_files = instrument_json_mapping.get(instrument_name, [])
    if not rule_files:
        logger.warning("No JSON rule files found for instrument: %s", instrument_name)
        return {}

    combined_rules = {}
    for file_name in rule_files:
        file_path = Path(json_rules_dir) / file_name
        if file_path.exists():
            try:
                with file_path.open("r") as f:
                    rules = json.load(f)
                    combined_rules.update(rules)
            except json.JSONDecodeError:
                logger.exception("Could not decode JSON from %s", file_path)
            except Exception:
                logger.exception("Error reading rule file %s", file_path)
        else:
            logger.warning("JSON rule file not found: %s", file_path)

    return combined_rules
