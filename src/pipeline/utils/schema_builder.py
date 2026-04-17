"""
Builds Cerberus validation schemas from JSON rule definitions.

This module translates the custom JSON rule format into a schema dictionary
compatible with the Cerberus validation library. It handles both standard
instruments and those requiring dynamic rule selection based on a discriminant
variable in the data.
"""

from typing import Any

from ..config.config_manager import KEY_MAP


def _strip_temporal_compare_with(value: Any) -> Any | None:
    """Remove compare_with entries that reference the previous record.

    Returns the cleaned value, or None if the entire compare_with should be
    dropped (i.e. every entry was a previous-record reference).
    """
    if isinstance(value, dict):
        return None if value.get("previous_record") else value
    if isinstance(value, list):
        kept = [
            item for item in value if not (isinstance(item, dict) and item.get("previous_record"))
        ]
        return kept if kept else None
    return value


def _strip_temporal_from_compatibility(compat_rules: Any) -> list:
    """Remove temporalrules from THEN/ELSE clauses of compatibility rules.

    Compatibility rules can embed temporalrules inside their THEN/ELSE clause
    per-variable constraint dicts.  Those nested rules bypass the top-level
    ``include_temporal_rules`` flag and must be stripped separately.

    Rules whose THEN clause becomes entirely empty after stripping are dropped
    from the list — an empty ``then: {}`` is rejected by Cerberus schema
    validation.
    """
    if not isinstance(compat_rules, list):
        return compat_rules

    cleaned = []
    for rule in compat_rules:
        if not isinstance(rule, dict):
            cleaned.append(rule)
            continue

        rule_copy = dict(rule)
        for clause_key in ("then", "else"):
            if not isinstance(rule_copy.get(clause_key), dict):
                continue
            clause: dict[str, Any] = {}
            for field, constraints in rule_copy[clause_key].items():
                if isinstance(constraints, dict):
                    stripped = {k: v for k, v in constraints.items() if k != "temporalrules"}
                    if stripped:
                        clause[field] = stripped
                else:
                    clause[field] = constraints
            if clause:
                rule_copy[clause_key] = clause
            else:
                # Empty clause — remove the key entirely so Cerberus does not
                # see ``then: {}`` which it rejects as "empty values not allowed"
                del rule_copy[clause_key]

        # Drop the entire compatibility rule if it has no remaining THEN/ELSE
        # constraints (it was purely a temporal check)
        if rule_copy.get("then") or rule_copy.get("else"):
            cleaned.append(rule_copy)

    return cleaned


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
                               Also strips ``compare_with`` rules that reference
                               the previous record and ``temporalrules`` embedded
                               inside compatibility rule THEN/ELSE clauses.
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
            # Skip top-level temporal rules when datastore is unavailable
            if json_key == "temporalrules" and not include_temporal_rules:
                continue

            # Skip compatibility rules if not needed
            if json_key == "compatibility" and not include_compatibility_rules:
                continue

            if not include_temporal_rules:
                # compare_with with previous_record=True is a temporal check;
                # drop it (or filter out previous-record entries from a list)
                if json_key == "compare_with":
                    rule_value = _strip_temporal_compare_with(rule_value)
                    if rule_value is None:
                        continue

                # Compatibility rules may embed temporalrules in their THEN/ELSE
                # clauses — strip those nested references as well
                elif json_key == "compatibility":
                    rule_value = _strip_temporal_from_compatibility(rule_value)

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
