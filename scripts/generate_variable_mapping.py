"""
Generate variable-to-instrument mapping from rule files.

This script scans all rule JSON files in the config directories and creates
a mapping of variable names to their source instruments. This is useful for
maintaining instrument context in the unified validation approach.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def extract_instrument_from_filename(filename: str) -> str | None:
    """
    Extract instrument name from rule filename.
    
    Examples:
        a1_rules.json -> a1_participant_demographics
        b1_rules_optional.json -> b1_evaluation_form
        header_rules.json -> form_header
    
    Args:
        filename: Name of the rule file
        
    Returns:
        Instrument name or None if cannot determine
    """
    # Remove .json extension
    name = filename.replace(".json", "")
    
    # Remove _rules suffix
    if name.endswith("_rules"):
        name = name[:-6]
    
    # Remove _optional suffix
    if name.endswith("_optional"):
        name = name[:-9]
    
    # Special cases
    if name == "header":
        return "form_header"
    
    # For standard forms (a1, b1, etc.), map to full instrument name
    # This mapping should align with the original instruments list
    instrument_mapping = {
        "a1": "a1_participant_demographics",
        "a1a": "a1a_participant_demographics_adrc_only",
        "a2": "a2_informant_demographics",
        "a3": "a3_subject_family_history",
        "a4": "a4_medications",
        "a4a": "a4a_atypical_antipsychotic_medications_adrc_only",
        "a5d2": "a5d2_subject_health_history",
        "b1": "b1_evaluation_form_physical",
        "b3": "b3_updrs",
        "b6": "b6_behavioral_assessment_gds",
        "b7": "b7_functional_assessment_faq",
        "b8": "b8_neurological_examination_findings",
        "b9": "b9_clinician_judgment_of_symptoms",
        "c2c2t": "c2c2t_neuropsychological_battery_scores",
        "d1a": "d1a_clinician_diagnosis",
        "d1b": "d1b_clinician_diagnosis_method_of_evaluation",
    }
    
    return instrument_mapping.get(name, name)


def generate_variable_mapping(config_dir: Path) -> dict[str, str]:
    """
    Generate a mapping of variable names to instrument names.
    
    Args:
        config_dir: Path to config directory containing packet subdirectories
        
    Returns:
        Dictionary mapping variable name to instrument name
    """
    variable_map = {}
    
    # Process all packet directories
    for packet_dir in [config_dir / "I", config_dir / "I4", config_dir / "F"]:
        rules_dir = packet_dir / "rules"
        
        if not rules_dir.exists():
            logger.warning(f"Rules directory not found: {rules_dir}")
            continue
        
        logger.info(f"Scanning {rules_dir}")
        
        # Process all JSON files
        for rule_file in rules_dir.glob("*.json"):
            try:
                # Load rules
                with rule_file.open("r", encoding="utf-8") as f:
                    rules = json.load(f)
                
                if not isinstance(rules, dict):
                    logger.warning(f"Skipping {rule_file.name}: not a dictionary")
                    continue
                
                # Extract instrument name from filename
                instrument = extract_instrument_from_filename(rule_file.name)
                
                if not instrument:
                    logger.warning(f"Could not determine instrument for {rule_file.name}")
                    continue
                
                # Map each variable to its instrument
                for variable_name in rules.keys():
                    if variable_name in variable_map:
                        # Check if consistent
                        if variable_map[variable_name] != instrument:
                            logger.warning(
                                f"Variable {variable_name} appears in multiple instruments: "
                                f"{variable_map[variable_name]} and {instrument}"
                            )
                    else:
                        variable_map[variable_name] = instrument
                
                logger.debug(
                    f"Processed {rule_file.name}: {len(rules)} variables -> {instrument}"
                )
                
            except Exception as e:
                logger.error(f"Error processing {rule_file}: {e}")
                continue
    
    return variable_map


def save_variable_mapping(
    variable_map: dict[str, str],
    output_file: Path
) -> None:
    """
    Save variable mapping to JSON file.
    
    Args:
        variable_map: Dictionary mapping variables to instruments
        output_file: Path to output JSON file
    """
    # Sort by variable name for readability
    sorted_map = dict(sorted(variable_map.items()))
    
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(sorted_map, f, indent=2, sort_keys=True)
    
    logger.info(f"Saved {len(variable_map)} variable mappings to {output_file}")


def generate_instrument_summary(
    variable_map: dict[str, str]
) -> dict[str, int]:
    """
    Generate summary statistics by instrument.
    
    Args:
        variable_map: Dictionary mapping variables to instruments
        
    Returns:
        Dictionary with instrument -> variable count
    """
    instrument_counts = {}
    
    for variable, instrument in variable_map.items():
        instrument_counts[instrument] = instrument_counts.get(instrument, 0) + 1
    
    return dict(sorted(instrument_counts.items()))


def main():
    """Main execution function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    # Determine paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    config_dir = repo_root / "config"
    output_file = repo_root / "config" / "variable_instrument_mapping.json"
    
    if not config_dir.exists():
        logger.error(f"Config directory not found: {config_dir}")
        return
    
    logger.info("=" * 60)
    logger.info("Variable-to-Instrument Mapping Generator")
    logger.info("=" * 60)
    
    # Generate mapping
    logger.info("Scanning rule files...")
    variable_map = generate_variable_mapping(config_dir)
    
    # Generate summary
    summary = generate_instrument_summary(variable_map)
    
    logger.info("\nSummary by Instrument:")
    logger.info("-" * 60)
    for instrument, count in summary.items():
        logger.info(f"  {instrument:50s} {count:4d} variables")
    
    logger.info("-" * 60)
    logger.info(f"  {'TOTAL':50s} {len(variable_map):4d} variables")
    
    # Save mapping
    save_variable_mapping(variable_map, output_file)
    
    logger.info("\n" + "=" * 60)
    logger.info("Mapping generation complete!")
    logger.info(f"Output: {output_file}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
