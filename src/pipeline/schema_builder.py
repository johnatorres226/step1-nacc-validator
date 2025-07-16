"""
Builds Cerberus validation schemas from JSON rule definitions.

This module translates the custom JSON rule format into a schema dictionary
compatible with the Cerberus validation library. It handles both standard
instruments and those requiring dynamic rule selection based on a discriminant
variable in the data.
"""

from typing import Any, Dict, Union

from pipeline.config_manager import KEY_MAP, is_dynamic_rule_instrument
from pipeline.instrument_mapping import (
    load_dynamic_rules_for_instrument,
    load_json_rules_for_instrument,
)


def build_cerberus_schema_for_instrument(
    instrument_name: str,
    include_temporal_rules: bool = True,
    include_compatibility_rules: bool = True
) -> Dict[str, Any]:
    """
    Loads JSON rules and builds a Cerberus schema for a given instrument.

    - For standard instruments, it returns a single schema dictionary.
    - For dynamic instruments (e.g., C2/C2T), it returns a nested dictionary
      where keys are variants (e.g., 'C2', 'C2T') and values are their
      corresponding schemas.

    Args:
        instrument_name: The name of the instrument.
        include_temporal_rules: Whether to include temporal rules in the schema.
                               Set to False when datastore is not available.
        include_compatibility_rules: Whether to include compatibility rules.
                                   Set to False for simple validation only.

    Returns:
        A dictionary representing the Cerberus schema. For dynamic instruments,
        this will be a dictionary of schemas.
    """
    if is_dynamic_rule_instrument(instrument_name):
        # Load all rule variants for the dynamic instrument
        raw_rule_map = load_dynamic_rules_for_instrument(instrument_name)
        # Build a schema for each variant
        return {
            variant: _build_schema_from_raw(
                raw_rules, 
                include_temporal_rules=include_temporal_rules,
                include_compatibility_rules=include_compatibility_rules
            )
            for variant, raw_rules in raw_rule_map.items()
        }

    # For standard instruments, load rules and build a single schema
    raw_rules = load_json_rules_for_instrument(instrument_name)
    return _build_schema_from_raw(
        raw_rules, 
        include_temporal_rules=include_temporal_rules,
        include_compatibility_rules=include_compatibility_rules
    )


def _build_schema_from_raw(
    rules_dict: Dict[str, Any],
    include_temporal_rules: bool = True,
    include_compatibility_rules: bool = True
) -> Dict[str, Dict[str, Any]]:
    """
    Transforms a dictionary of raw JSON rules into a Cerberus schema.

    This function iterates through variables and their associated rules, mapping
    the custom JSON rule keys (e.g., "pattern") to their Cerberus equivalents
    (e.g., "regex").

    Args:
        rules_dict: A dictionary where keys are variable names and values are
                    dictionaries of their JSON validation rules.
                    Example: `{ "VAR1": { "type": "integer", "min": 0 }, ... }`
        include_temporal_rules: Whether to include temporal rules in the schema.
                               Set to False when datastore is not available.
        include_compatibility_rules: Whether to include compatibility rules.
                                   Set to False for simple validation only.

    Returns:
        A dictionary formatted as a Cerberus schema.
        Example: `{ "VAR1": { "type": "integer", "min": 0 }, ... }`
    """
    schema: Dict[str, Dict[str, Any]] = {}

    for var, json_rules in rules_dict.items():
        cerberus_rules: Dict[str, Any] = {}
        for json_key, rule_value in json_rules.items():
            # Skip temporal rules if datastore is not available
            if json_key == "temporalrules" and not include_temporal_rules:
                continue
            
            # Skip compatibility rules if not needed
            if json_key == "compatibility" and not include_compatibility_rules:
                continue
            
            # Map the JSON key to a Cerberus key
            cerberus_key = KEY_MAP.get(json_key)

            if cerberus_key:
                # If a mapping exists, add the rule to the schema
                cerberus_rules[cerberus_key] = rule_value
            # Unrecognized keys (e.g., metadata like 'description') are ignored.

        if cerberus_rules:
            schema[var] = cerberus_rules

    return schema
