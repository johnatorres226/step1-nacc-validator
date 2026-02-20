"""
Builds Cerberus validation schemas from JSON rule definitions.

This module translates the custom JSON rule format into a schema dictionary
compatible with the Cerberus validation library. It handles both standard
instruments and those requiring dynamic rule selection based on a discriminant
variable in the data.
"""

from typing import Any

from ..config.config_manager import KEY_MAP


def _build_schema_from_raw(
    rules_dict: dict[str, Any],
    include_temporal_rules: bool = True,
    include_compatibility_rules: bool = True,
) -> dict[str, dict[str, Any]]:
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
    schema: dict[str, dict[str, Any]] = {}

    for var, json_rules in rules_dict.items():
        cerberus_rules: dict[str, Any] = {}
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
            # Unrecognized keys (e.g., metadata like 'description') are
            # ignored.

        if cerberus_rules:
            schema[var] = cerberus_rules

    return schema
