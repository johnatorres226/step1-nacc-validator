"""
Consolidated rule loading for the QC pipeline.

Delegates to :class:`NamespacedRulePool` for auto-discovered, O(1) per-variable
rule lookup.  Maintains backward-compatible public API (``load_rules_for_packet``,
``get_rules_for_record``, ``clear_cache``).
"""

import json
from pathlib import Path
from typing import Any

from ..config.config_manager import QCConfig, get_config
from ..logging.logging_config import get_logger
from .rule_pool import get_pool, reset_pool

logger = get_logger(__name__)

_packet_cache: dict[str, dict] = {}

_VALID_PACKETS = {"I", "I4", "F"}

# ---------------------------------------------------------------------------
# Minimal discriminant config — replaces DYNAMIC_RULE_INSTRUMENTS
# ---------------------------------------------------------------------------

_NAMESPACE_DISCRIMINANTS: dict[str, str] = {
    "c2c2t_neuropsychological_battery_scores": "loc_c2_or_c2t",
}

_DISCRIMINANT_VALUE_TO_NAMESPACE: dict[str, str] = {
    "C2": "c2",
    "C2T": "c2t",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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


def _resolve_namespace(record: dict, instrument_name: str) -> str | None:
    """Resolve namespace for instruments with conflicting variables."""
    disc_var = _NAMESPACE_DISCRIMINANTS.get(instrument_name)
    if not disc_var:
        return None
    value = str(record.get(disc_var, "")).upper().strip()
    return _DISCRIMINANT_VALUE_TO_NAMESPACE.get(value)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


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


def get_rules_for_record(
    record: dict, instrument_name: str, config: QCConfig | None = None
) -> dict:
    """Main entry point: load rules from pool, resolve namespace for conflicts."""
    packet = _validate_packet(record.get("packet", ""))
    cfg = _get_config(config)

    pool = get_pool(cfg)
    if packet not in pool.loaded_packets:
        pool.load_packet(packet, cfg)

    namespace = _resolve_namespace(record, instrument_name)
    return pool.get_resolved_rules_dict(namespace=namespace)


def clear_cache() -> None:
    """Reset the module-level cache and pool state."""
    _packet_cache.clear()
    reset_pool()
    logger.debug("Rule loader cache cleared")
