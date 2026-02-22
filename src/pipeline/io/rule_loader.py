"""
Consolidated rule loading for the QC pipeline.

Replaces: rules.py, packet_router.py, hierarchical_router.py, unified_rule_loader.py.
Provides packet-based rule loading with caching and dynamic instrument resolution.
"""

import json
from pathlib import Path
from typing import Any

from ..config.config_manager import (
    QCConfig,
    get_config,
    get_discriminant_variable,
    get_rule_mappings,
    instrument_json_mapping,
    is_dynamic_rule_instrument,
)
from ..logging.logging_config import get_logger

logger = get_logger(__name__)

_packet_cache: dict[str, dict] = {}

_VALID_PACKETS = {"I", "I4", "F"}


def _validate_packet(packet: str) -> str:
    """Normalize and validate a packet value."""
    packet = packet.upper()
    if packet not in _VALID_PACKETS:
        raise ValueError(
            f"Invalid packet value '{packet}'. Valid values: {', '.join(sorted(_VALID_PACKETS))}"
        )
    return packet


def _get_config(config: QCConfig | None) -> QCConfig:
    return config if config is not None else get_config()


def load_rules_for_packet(packet: str, config: QCConfig | None = None) -> dict:
    """Load all JSON rule files for a packet directory, merge into flat variable->rules dict.

    Handles caching per packet. Returns {variable_name: {rule_dict}} for all
    instruments in that packet.
    """
    packet = _validate_packet(packet)
    if packet in _packet_cache:
        return _packet_cache[packet]

    cfg = _get_config(config)
    rules_path = cfg.get_rules_path_for_packet(packet)
    rules_dir = Path(rules_path)

    if not rules_dir.exists():
        raise FileNotFoundError(f"Rules path for packet '{packet}' does not exist: {rules_path}")

    rule_files = sorted(rules_dir.glob("*.json"))
    if not rule_files:
        logger.warning("No rule files found in %s", rules_dir)
        _packet_cache[packet] = {}
        return {}

    merged: dict[str, Any] = {}
    for rule_file in rule_files:
        try:
            with rule_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in rule file %s, skipping", rule_file.name)
            continue

        if not isinstance(data, dict):
            logger.warning("Rule file %s does not contain a dict, skipping", rule_file.name)
            continue

        merged.update(data)

    logger.debug(
        "Loaded %d rules for packet %s from %d files", len(merged), packet, len(rule_files)
    )
    _packet_cache[packet] = merged
    return merged


def load_rules_for_instrument(instrument_name: str, config: QCConfig | None = None) -> dict:
    """Load rules for a specific instrument from its JSON rule files.

    For dynamic instruments, returns nested {variant: {rules}} structure.
    For standard instruments, returns flat {variable: {rule}} dict.
    """
    cfg = _get_config(config)
    rules_dir = Path(cfg.json_rules_path_i)

    if is_dynamic_rule_instrument(instrument_name):
        mappings = get_rule_mappings(instrument_name)
        variant_rules: dict[str, dict] = {}
        for variant, filename in mappings.items():
            path = rules_dir / filename
            try:
                with path.open("r", encoding="utf-8") as f:
                    variant_rules[variant] = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                logger.exception("Failed to load variant %s from %s", variant, path)
                raise
        return variant_rules

    file_list = instrument_json_mapping.get(instrument_name, [])
    if not file_list:
        logger.warning("No rule files configured for instrument: %s", instrument_name)
        return {}

    combined: dict[str, Any] = {}
    for filename in file_list:
        path = rules_dir / filename
        if not path.exists():
            logger.warning("Rule file not found: %s", path)
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                combined.update(json.load(f))
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in %s, skipping", path)
    return combined


def resolve_dynamic_rules(record: dict, base_rules: dict, instrument_name: str) -> dict:
    """Handle C2/C2T discrimination.

    If the instrument is not dynamic, returns base_rules unchanged.
    For dynamic instruments, checks the discriminant variable in the record and
    returns the matching variant's rules from base_rules.
    """
    if not is_dynamic_rule_instrument(instrument_name):
        return base_rules

    discriminant_var = get_discriminant_variable(instrument_name)
    value = record.get(discriminant_var, "").upper()

    if value and value in base_rules:
        logger.debug(
            "Resolved dynamic variant %s=%s for %s", discriminant_var, value, instrument_name
        )
        return base_rules[value]

    if not value:
        logger.warning(
            "Missing %s in record for %s. Falling back to first variant.",
            discriminant_var,
            instrument_name,
        )
    else:
        logger.warning(
            "No variant rules for %s=%s in %s. Falling back to first variant.",
            discriminant_var,
            value,
            instrument_name,
        )

    # Default: return first variant
    return next(iter(base_rules.values())) if base_rules else {}


def _load_dynamic_variant_rules(instrument_name: str, config: QCConfig | None = None) -> dict:
    """Load the nested {variant: {rules}} structure for a dynamic instrument
    using the I-packet rules directory."""
    cfg = _get_config(config)
    rules_dir = Path(cfg.json_rules_path_i)
    mappings = get_rule_mappings(instrument_name)
    variant_rules: dict[str, dict] = {}
    for variant, filename in mappings.items():
        path = rules_dir / filename
        try:
            with path.open("r", encoding="utf-8") as f:
                variant_rules[variant] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.exception("Failed to load dynamic variant %s from %s", variant, path)
            raise
    return variant_rules


def get_rules_for_record(
    record: dict, instrument_name: str, config: QCConfig | None = None
) -> dict:
    """Main entry point: determine packet from record, load rules, apply dynamic resolution."""
    packet = _validate_packet(record.get("packet", ""))
    rules = load_rules_for_packet(packet, config)

    if is_dynamic_rule_instrument(instrument_name):
        variant_rules = _load_dynamic_variant_rules(instrument_name, config)
        return resolve_dynamic_rules(record, variant_rules, instrument_name)

    return rules


def load_rules_for_instruments(
    instrument_list: list[str], config: QCConfig | None = None
) -> dict[str, dict]:
    """Load rules for multiple instruments. Returns {instrument: {rules}} mapping.

    For dynamic instruments, loads all variants.
    """
    return {name: load_rules_for_instrument(name, config) for name in instrument_list}


def clear_cache() -> None:
    """Reset the module-level cache."""
    _packet_cache.clear()
    logger.debug("Rule loader cache cleared")
