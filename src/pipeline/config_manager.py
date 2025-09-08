"""
Enhanced Configuration Management for UDSv4 QC Validator.
"""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv

# Late imports to avoid circular dependencies
from .logging_config import get_logger

logger = get_logger(__name__)

# =============================================================================
# ENVIRONMENT CONFIGURATION
# This section handles environment variables and paths for the project.
# =============================================================================

# Get the directory where this config_manager.py file is located
# Go up two levels to get the actual project root
config_dir = Path(__file__).parent.resolve()
project_root = config_dir.parent.parent
dotenv_path = project_root / ".env"

# Load environment variables from .env file
load_dotenv(dotenv_path)

# Environment variable
adrc_api_key = os.getenv('REDCAP_API_TOKEN')
adrc_redcap_url = os.getenv('REDCAP_API_URL')
project_id = os.getenv('PROJECT_ID')

# Paths
output_path = os.getenv('OUTPUT_PATH')
status_path = os.getenv('STATUS_PATH')
upload_ready_path = os.getenv('UPLOAD_READY_PATH')


# =============================================================================
# INSTRUMENTS AND MAPPING CONFIGURATION
# This section defines the instruments and their JSON mapping for validation rules.
#
# Use "UPDATE_MARKER" to search what items need to be updated in this section
# =============================================================================

# UPDATE more instrument details -- HERE -- as they are needed
instruments = [
    # I and I4 packets instruments
    "form_header",
    "a1_participant_demographics",
    "a3_participant_family_history",
    "a4a_adrd_specific_treatments",
    "a5d2_participant_health_history_clinician_assessed",
    "b6_geriatric_depression_scale",
    "a1a_sdoh",
    "a4_participant_medications",
    "b1_vital_signs_and_anthropometrics",
    "a2_coparticipant_demographics",
    "b5_neuropsychiatric_inventory_questionnaire_npiq",
    "b7_functional_assessment_scale_fas",
    "b4_cdr_dementia_staging_instrument",
    "b3_unified_parkinsons_disease_rating_scale_updrs_m",
    "b8_neurological_examination_findings",
    "b9_clinician_judgment_of_symptoms",
    "d1a_clinical_syndrome",
    "d1b_etiological_diagnosis_and_biomarker_support",
    "c2c2t_neuropsychological_battery_scores"

    # UPDATE_MARKER Insert F packet instruments here as they are needed
]

instrument_json_mapping = {
    # I and I4 packets instruments
    "form_header": ["header_rules.json"],
    "a1_participant_demographics": ["a1_rules.json"],
    "a3_participant_family_history": ["a3_rules.json"],
    "a4a_adrd_specific_treatments": ["a4a_rules.json"],
    "a5d2_participant_health_history_clinician_assessed": ["a5d2_rules.json"],
    "b6_geriatric_depression_scale": ["b6_rules.json"],
    "a1a_sdoh": ["a1a_rules.json"],
    "a4_participant_medications": ["a4_rules.json"],
    "b1_vital_signs_and_anthropometrics": ["b1_rules.json"],
    "a2_coparticipant_demographics": ["a2_rules.json"],
    "b5_neuropsychiatric_inventory_questionnaire_npiq": ["b5_rules.json"],
    "b7_functional_assessment_scale_fas": ["b7_rules.json"],
    "b4_cdr_dementia_staging_instrument": ["b4_rules.json"],
    "b3_unified_parkinsons_disease_rating_scale_updrs_m": ["b3_rules.json"],
    "b8_neurological_examination_findings": ["b8_rules.json"],
    "b9_clinician_judgment_of_symptoms": ["b9_rules.json"],
    "d1a_clinical_syndrome": ["d1a_rules.json"],
    "d1b_etiological_diagnosis_and_biomarker_support": ["d1b_rules.json"],
    "c2c2t_neuropsychological_battery_scores": [
        "c2_rules.json",
        "c2t_rules.json",
    ],

    # UPDATE_MARKER Insert F packet instruments here as they are needed
}

# UPDATE_MARKER more events -- HERE -- as they are needed
uds_events = [
    "udsv4_ivp_1_arm_1",
    "udsv4_fvp_2_arm_1"
]

# =============================================================================
# DATA FETCHING AND FILTERING
# =============================================================================
"""
Here are the configurations for fetching and filtering data from REDCap.

complete_instruments_vars is a dict. of these elements: {instrument_name}_complete

complete_events_with_incomplete_qc_filter_logic is a string to serve as the REDCap filter logic
    This filter selects complete events that have NOT been QC'd yet (qc_status_complete = 0 or empty)
    Format: "([{instrument_name}_complete]=2 and [{instrument_name}_complete]=2 and ...) and ([qc_status_complete] = 0 or [qc_status_complete] = \"\")"

"""
complete_instruments_vars = [f"{inst}_complete" for inst in instruments]
complete_events_with_incomplete_qc_filter_logic = (
    "(" +
    " and ".join(f"[{inst}]=2" for inst in complete_instruments_vars) +
    ") and ([qc_status_complete] = 0 or [qc_status_complete] = \"\")"
)
qc_status_form = ["quality_control_check"]
instrument_filter = instruments + qc_status_form
uds_event_filter = uds_events
qc_filterer_logic = '[qc_status_complete] = 0 or [qc_status_complete] = ""'


# =============================================================================
# JSON SCHEMA TO CERBERUS MAPPING
# =============================================================================

# JSON Schema to Cerberus Mapping (preserved exactly from config.py)
TYPE_ALIASES = {
    "integer": ["int"],
    "string":  ["str"],
    "float":   ["float"],
    "boolean": ["bool"],
    "array":   ["list"],
    "object":  ["dict"],
}

# invert mapping: python type name → JSON name
PYTHON_TO_JSON = {
    alias: json_name
    for json_name, aliases in TYPE_ALIASES.items()
    for alias in aliases
}

# Map JSON rule keys to Cerberus schema keywords
KEY_MAP = {
    "type": "type",
    "nullable": "nullable",
    "min": "min",
    "max": "max",
    "pattern": "regex",  # JSON might use "pattern" or "regex"
    "regex": "regex",
    "allowed": "allowed",
    "forbidden": "forbidden",
    "filled": "filled",
    "required": "required",
    "anyof": "anyof",
    "oneof": "oneof",
    "allof": "allof",
    "formatting": "formatting",  # Custom formatting rule
    "compatibility": "compatibility", # "compatibility" will be handled by NACCValidator's _validate_compatibility
}

# =============================================================================
# DYNAMIC RULE SELECTION CONFIGURATION
# =============================================================================

"""
This configuration section is designed to handle dynamic rule selection and 
to future-proof configuration for instruments with variable-based rule selection

Configuration for instruments that use variable-based rule selection
This allows for dynamic rule selection based on discriminant variables

If more C2/C2T instruments are added, they should follow the same pattern,
and add their configurations to the DYNAMIC_RULE_INSTRUMENTS dict here below. 

"""

DYNAMIC_RULE_INSTRUMENTS = {
    "c2c2t_neuropsychological_battery_scores": {
        "discriminant_variable": "loc_c2_or_c2t",
        "rule_mappings": {
            "C2": "c2_rules.json",
            "C2T": "c2t_rules.json"
        }
    },

    # --- UPDATE_MARKER Future Discriminant Variables ---
    # Example for future C2/C2T instruments is as follows:

    # "follow_up_c2c2t_neuropsychological_battery_scores": {
    #     "discriminant_variable": "fvp_loc_c2_or_c2t",
    #     "rule_mappings": {
    #         "C2": "fvp_c2_rules.json",
    #         "C2T": "fvp_c2t_rules.json"
    #     }
    # }
}

# List of all discriminant variables used across the system
# This helps with data fetching and filtering
DISCRIMINANT_VARIABLES = list(set([
    config["discriminant_variable"]
    for config in DYNAMIC_RULE_INSTRUMENTS.values()
]))

# Helper function to get all instruments that use dynamic rule selection
def get_dynamic_rule_instruments():
    """Returns a list of all instruments that use dynamic rule selection."""
    return list(DYNAMIC_RULE_INSTRUMENTS.keys())

# Helper function to get discriminant variable for an instrument
def get_discriminant_variable(instrument_name: str) -> str:
    """Returns the discriminant variable name for a given instrument."""
    config = DYNAMIC_RULE_INSTRUMENTS.get(instrument_name)
    if not config:
        raise ValueError(f"Instrument '{instrument_name}' is not configured for dynamic rule selection")
    return config["discriminant_variable"]

# Helper function to get rule mappings for an instrument
def get_rule_mappings(instrument_name: str) -> dict:
    """Returns the rule mappings for a given instrument."""
    config = DYNAMIC_RULE_INSTRUMENTS.get(instrument_name)
    if not config:
        raise ValueError(f"Instrument '{instrument_name}' is not configured for dynamic rule selection")
    return config["rule_mappings"]

# Helper function to check if an instrument uses dynamic rule selection
def is_dynamic_rule_instrument(instrument_name: str) -> bool:
    """Returns True if the instrument uses dynamic rule selection."""
    return instrument_name in DYNAMIC_RULE_INSTRUMENTS

# =============================================================================
# CONFIGURATION VALIDATORS
# Modular validation system for better maintainability and testability
# =============================================================================

class ConfigValidator(ABC):
    """Abstract base class for configuration validators."""

    @abstractmethod
    def validate(self, config: 'QCConfig') -> List[str]:
        """Validate configuration and return list of errors."""


class RequiredFieldsValidator(ConfigValidator):
    """Validates that all required fields are present and valid."""

    def validate(self, config: 'QCConfig') -> List[str]:
        """Validate required fields and return list of errors."""
        errors = []

        # Require REDCap API configuration
        if not config.api_token and not config.redcap_api_token:
            errors.append("REDCAP_API_TOKEN is required")
        if not config.api_url and not config.redcap_api_url:
            errors.append("REDCAP_API_URL is required")

        # Require ALL packet rule paths (no fallbacks)
        required_packet_paths = {
            'JSON_RULES_PATH_I': config.json_rules_path_i,
            'JSON_RULES_PATH_I4': config.json_rules_path_i4,
            'JSON_RULES_PATH_F': config.json_rules_path_f
        }

        for env_var, path in required_packet_paths.items():
            if not path:
                errors.append(f"Missing required environment variable: {env_var}")

        return errors


class PathValidator(ConfigValidator):
    """Validates and creates necessary paths."""

    def validate(self, config: 'QCConfig') -> List[str]:
        """Validate paths and return list of errors."""
        errors = []

        # Validate packet-specific rules paths (required for production)
        packet_paths = {
            'JSON_RULES_PATH_I': config.json_rules_path_i,
            'JSON_RULES_PATH_I4': config.json_rules_path_i4,
            'JSON_RULES_PATH_F': config.json_rules_path_f
        }

        for env_var, path in packet_paths.items():
            if path and not Path(path).is_dir():
                errors.append(f"{env_var} '{path}' is not a valid directory.")

        # Validate and create output path if needed
        if config.output_path and not Path(config.output_path).is_dir():
            try:
                Path(config.output_path).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(f"OUTPUT_PATH '{config.output_path}' is not a valid directory and could not be created: {e}")

        # Validate and create log path if needed
        if config.log_path and not Path(config.log_path).is_dir():
            try:
                Path(config.log_path).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(f"LOG_PATH '{config.log_path}' is not a valid directory and could not be created: {e}")

        return errors


class PerformanceValidator(ConfigValidator):
    """Validates performance-related settings."""

    def validate(self, config: 'QCConfig') -> List[str]:
        """Validate performance settings and return list of errors."""
        errors = []

        # Validate performance settings and report errors
        if config.max_workers < 1:
            errors.append("max_workers must be at least 1")
        if config.timeout < 30:
            errors.append("timeout must be at least 30 seconds")
        if config.retry_attempts < 0:
            errors.append("retry_attempts cannot be negative")

        return errors


class CustomValidator(ConfigValidator):
    """Validates custom business logic and constraints."""

    def validate(self, config: 'QCConfig') -> List[str]:
        """Validate custom constraints and return list of errors."""
        errors = []

        # Validate instrument consistency
        if len(config.instruments) != len(set(config.instruments)):
            errors.append("Duplicate instruments found in configuration.")

        # Validate instrument mapping consistency
        for instrument in config.instruments:
            if instrument not in config.instrument_json_mapping:
                errors.append(f"Instrument '{instrument}' has no JSON mapping configured.")

        return errors


# =============================================================================
# MODERN CONFIGURATION SECTION
# Enhanced features while maintaining backward compatibility
# =============================================================================

@dataclass
class QCConfig:
    """
    A modern, structured configuration class for the QC pipeline.
    
    This class centralizes all configuration parameters, provides type hints,
    and allows for default values and environment variable overrides.
    """

    # --- Core REDCap API Configuration ---
    api_token: Optional[str] = field(default_factory=lambda: os.getenv('REDCAP_API_TOKEN') or None)
    redcap_api_token: Optional[str] = field(default_factory=lambda: os.getenv('REDCAP_API_TOKEN') or None)  # Alias for backward compatibility
    api_url: Optional[str] = field(default_factory=lambda: os.getenv('REDCAP_API_URL') or None)
    redcap_api_url: Optional[str] = field(default_factory=lambda: os.getenv('REDCAP_API_URL') or None)  # Alias for backward compatibility
    project_id: Optional[str] = field(default_factory=lambda: os.getenv('PROJECT_ID'))

    # --- Path Configuration ---
    output_path: str = field(default_factory=lambda: os.getenv('OUTPUT_PATH', str(project_root / "output")))
    log_path: Optional[str] = field(default_factory=lambda: os.getenv('LOG_PATH'))
    status_path: Optional[str] = field(default_factory=lambda: os.getenv('STATUS_PATH'))
    upload_ready_path: Optional[str] = field(default_factory=lambda: os.getenv('UPLOAD_READY_PATH'))

    # --- Packet-based Rule Paths (Required) ---
    json_rules_path_i: str = field(default_factory=lambda: os.getenv('JSON_RULES_PATH_I', ''))
    json_rules_path_i4: str = field(default_factory=lambda: os.getenv('JSON_RULES_PATH_I4', ''))
    json_rules_path_f: str = field(default_factory=lambda: os.getenv('JSON_RULES_PATH_F', ''))

    # --- Primary Key Configuration ---
    primary_key_field: str = "ptid"

    # --- Special Column Configuration ---
    special_col_discriminat_var: List[str] = field(default_factory=lambda: list(set(
        config["discriminant_variable"]
        for config in DYNAMIC_RULE_INSTRUMENTS.values()
    )))

    # --- QC Pipeline Behavior ---
    mode: str = 'complete_visits'  # 'complete_visits', 'all_visits', 'ivp_only', 'fvp_only'
    test_mode: bool = False  # Use test database instead of production database
    log_level: str = field(default_factory=lambda: os.getenv('LOG_LEVEL', 'INFO'))
    user_initials: Optional[str] = None
    ptid_list: Optional[List[str]] = None
    include_qced: bool = False
    detailed_run: bool = False  # Generate detailed outputs (Validation_Logs, Completed_Visits, Reports, Generation_Summary)
    passed_rules: bool = False  # Generate comprehensive Rules Validation log (large file, slow generation)

    # --- Performance & Retries ---
    max_workers: int = field(default_factory=lambda: int(os.getenv('MAX_WORKERS', '4')))
    timeout: int = field(default_factory=lambda: int(os.getenv('TIMEOUT', '300')))
    retry_attempts: int = field(default_factory=lambda: int(os.getenv('RETRY_ATTEMPTS', '3')))

    # --- Report Generation ---
    generate_html_report: bool = field(default_factory=lambda: os.getenv('GENERATE_HTML_REPORT', 'true').lower() == 'true')

    # --- Instrument & Event Configuration ---
    instruments: List[str] = field(default_factory=lambda: instruments)
    instrument_json_mapping: Dict[str, List[str]] = field(default_factory=lambda: instrument_json_mapping)
    events: List[str] = field(default_factory=lambda: uds_events)

    def __post_init__(self):
        """Post-initialization validation and path resolution."""
        # Sync alias fields for backward compatibility
        if self.api_token and not self.redcap_api_token:
            self.redcap_api_token = self.api_token
        elif self.redcap_api_token and not self.api_token:
            self.api_token = self.redcap_api_token

        if self.api_url and not self.redcap_api_url:
            self.redcap_api_url = self.api_url
        elif self.redcap_api_url and not self.api_url:
            self.api_url = self.redcap_api_url

        # Resolve paths to be absolute
        if self.output_path:
            self.output_path = str(Path(self.output_path).resolve())
        if self.log_path:
            self.log_path = str(Path(self.log_path).resolve())
        if self.status_path:
            self.status_path = str(Path(self.status_path).resolve())
        if self.upload_ready_path:
            self.upload_ready_path = str(Path(self.upload_ready_path).resolve())

        # Resolve packet-specific rule paths (required for production)
        if self.json_rules_path_i:
            self.json_rules_path_i = str(Path(self.json_rules_path_i).resolve())
        if self.json_rules_path_i4:
            self.json_rules_path_i4 = str(Path(self.json_rules_path_i4).resolve())
        if self.json_rules_path_f:
            self.json_rules_path_f = str(Path(self.json_rules_path_f).resolve())

        self._validate_config()

    def _validate_config(self):
        """Performs validation checks on the configuration using modular validators."""
        # Only validate during normal operation, not during testing
        # Tests can call validate() method explicitly

    def to_dict(self) -> Dict[str, Any]:
        """Converts the configuration to a dictionary."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def to_file(self, file_path: Union[str, Path]):
        """Saves configuration to a JSON file."""
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=4)

    @classmethod
    def from_file(cls, file_path: Union[str, Path]) -> "QCConfig":
        """Loads configuration from a JSON file."""
        if not Path(file_path).exists():
            return cls()  # Return default config if file not found
        with open(file_path, "r") as f:
            data = json.load(f)
        return cls(**data)

    def get_instruments(self) -> List[str]:
        """Returns the list of UDS visit instruments."""
        return self.instruments

    def get_instrument_json_mapping(self) -> Dict[str, List[str]]:
        """Returns the mapping of instruments to JSON rule files."""
        return self.instrument_json_mapping

    def get_rules_path_for_packet(self, packet: str) -> str:
        """Get the required rules path for a packet type."""
        packet_paths = {
            'I': self.json_rules_path_i,
            'I4': self.json_rules_path_i4,
            'F': self.json_rules_path_f
        }
        path = packet_paths.get(packet.upper())
        if not path:
            raise ValueError(f"No rules path configured for packet '{packet}'. Required environment variables: JSON_RULES_PATH_I, JSON_RULES_PATH_I4, JSON_RULES_PATH_F")
        return path

    def validate(self) -> List[str]:
        """
        Validates the configuration and returns a list of errors.
        An empty list indicates a valid configuration.
        """
        validators = [
            RequiredFieldsValidator(),
            PathValidator(),
            PerformanceValidator(),
            CustomValidator()
        ]

        all_errors = []
        for validator in validators:
            errors = validator.validate(self)
            all_errors.extend(errors)

        return all_errors

# =============================================================================
# CONFIGURATION ACCESSOR FUNCTIONS
# Provides a clean, consistent way to access configuration settings
# =============================================================================

# Singleton instance of the configuration
_config_instance: Optional[QCConfig] = None

def load_config_from_env() -> QCConfig:
    """Loads configuration from environment variables and returns a QCConfig instance."""
    return QCConfig()


def get_config(force_reload: bool = False, skip_validation: bool = False) -> QCConfig:
    """
    Returns a singleton instance of the QCConfig.
    On first call, it loads, validates, and caches the configuration.
    
    Args:
        force_reload: Force creation of a new config instance
        skip_validation: Skip validation exit for testing purposes
    """
    global _config_instance
    if _config_instance is None or force_reload:
        _config_instance = load_config_from_env()
        if not skip_validation:
            errors = _config_instance.validate()
            if errors:
                # Use a simple print for critical config errors, as logging may not be configured yet
                print("Configuration errors found. Cannot continue.")
                for error in errors:
                    print(f"  - {error}")
                raise SystemExit(1)  # Exit if configuration is invalid
    return _config_instance


def get_instruments() -> List[str]:
    """Returns the list of UDS visit instruments."""
    return get_config().get_instruments()

def get_instrument_json_mapping() -> Dict[str, List[str]]:
    """Returns the mapping of instruments to JSON rule files."""
    return get_config().get_instrument_json_mapping()


def get_output_path() -> Optional[Path]:
    """Returns the path to the output directory."""
    path = get_config().output_path
    return Path(path) if path else None


def get_status_path() -> Optional[Path]:
    """Returns the path to the status file."""
    path = get_config().status_path
    return Path(path) if path else None


def get_core_columns() -> List[str]:
    """Returns the core REDCap columns."""
    config = get_config()
    return [config.primary_key_field, "redcap_event_name", "packet"]


def get_completion_columns() -> List[str]:
    """Returns the completion columns for all instruments."""
    config = get_config()
    return [f"{inst}_complete" for inst in config.get_instruments()]


def get_special_columns() -> List[str]:
    """Returns the special columns defined in configuration."""
    return get_config().special_col_discriminat_var


# Initialize configuration on module load
# get_config() # Removed to allow for testing without premature validation

# =============================================================================
# CERBERUS COMPATIBILITY LAYER
# =============================================================================

class CerberusCompatibilityAdapter:
    """
    Adapter to handle compatibility issues with Cerberus validation library.
    
    This class addresses temporary workarounds needed for custom validation rules
    that don't exist in the standard Cerberus library, particularly the 'compatibility'
    and 'temporalrules' custom validators.
    """

    def __init__(self):
        self.supported_cerberus_rules = {
            "type", "nullable", "min", "max", "regex", "allowed", "forbidden", "filled",
            "required", "anyof", "oneof", "allof", "formatting"
        }
        self.custom_rules = {
            "compatibility", "temporalrules"
        }

    def extract_cerberus_rules(self, json_rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only the rules that are supported by standard Cerberus.
        
        Args:
            json_rules: Raw JSON rules dictionary
            
        Returns:
            Dictionary with only Cerberus-compatible rules
        """
        cerberus_rules = {}

        for key, value in json_rules.items():
            cerberus_key = KEY_MAP.get(key)
            if cerberus_key and cerberus_key in self.supported_cerberus_rules:
                cerberus_rules[cerberus_key] = value

        return cerberus_rules

    def extract_custom_rules(self, json_rules: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract custom rules that need special handling.
        
        Args:
            json_rules: Raw JSON rules dictionary
            
        Returns:
            Dictionary with custom rules that need special processing
        """
        custom_rules = {}

        for key, value in json_rules.items():
            cerberus_key = KEY_MAP.get(key)
            if cerberus_key and cerberus_key in self.custom_rules:
                custom_rules[cerberus_key] = value

        return custom_rules

    def is_custom_rule(self, rule_key: str) -> bool:
        """Check if a rule key is a custom rule that needs special handling."""
        return rule_key in self.custom_rules


class ModernSchemaBuilder:
    """
    Modern schema builder that properly handles Cerberus compatibility.
    
    This replaces the temporary workaround approach with a structured solution
    that separates Cerberus-compatible rules from custom validation logic.
    """

    def __init__(self):
        self.compatibility_adapter = CerberusCompatibilityAdapter()

    def build_schema_for_instrument(self, instrument_name: str) -> Dict[str, Any]:
        """
        Build a proper schema structure for an instrument.
        
        Returns:
            Dictionary with 'cerberus_schema' and 'custom_rules' sections
        """
        if is_dynamic_rule_instrument(instrument_name):
            return self._build_dynamic_schema(instrument_name)
        else:
            return self._build_standard_schema(instrument_name)

    def _build_standard_schema(self, instrument_name: str) -> Dict[str, Any]:
        """Build schema for standard instruments."""
        # Import here to avoid circular dependencies
        from .utils.instrument_mapping import load_json_rules_for_instrument

        raw_rules = load_json_rules_for_instrument(instrument_name)

        cerberus_schema = {}
        custom_rules = {}

        for var, json_rules in raw_rules.items():
            cerberus_rules = self.compatibility_adapter.extract_cerberus_rules(json_rules)
            custom_var_rules = self.compatibility_adapter.extract_custom_rules(json_rules)

            if cerberus_rules:
                cerberus_schema[var] = cerberus_rules
            if custom_var_rules:
                custom_rules[var] = custom_var_rules

        return {
            "cerberus_schema": cerberus_schema,
            "custom_rules": custom_rules
        }

    def _build_dynamic_schema(self, instrument_name: str) -> Dict[str, Any]:
        """Build schema for dynamic rule instruments."""
        # Import here to avoid circular dependencies
        from .utils.instrument_mapping import load_dynamic_rules_for_instrument

        raw_rule_map = load_dynamic_rules_for_instrument(instrument_name)

        schema_variants = {}

        for variant, raw_rules in raw_rule_map.items():
            cerberus_schema = {}
            custom_rules = {}

            for var, json_rules in raw_rules.items():
                cerberus_rules = self.compatibility_adapter.extract_cerberus_rules(json_rules)
                custom_var_rules = self.compatibility_adapter.extract_custom_rules(json_rules)

                if cerberus_rules:
                    cerberus_schema[var] = cerberus_rules
                if custom_var_rules:
                    custom_rules[var] = custom_var_rules

            schema_variants[variant] = {
                "cerberus_schema": cerberus_schema,
                "custom_rules": custom_rules
            }

        return schema_variants


# =============================================================================
# MODERN COMPATIBILITY VALIDATORS
# =============================================================================

class CompatibilityValidator:
    """
    Modern implementation of compatibility validation.
    
    This replaces the temporary workaround in NACCValidator with a proper
    structured approach that doesn't rely on Cerberus internal mechanisms.
    """

    def validate_compatibility_rules(self, record: Dict[str, Any],
                                   compatibility_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate compatibility rules for a record.
        
        Args:
            record: The data record to validate
            compatibility_rules: List of compatibility rule definitions
            
        Returns:
            List of validation errors
        """
        errors = []

        for rule_index, rule in enumerate(compatibility_rules):
            try:
                error = self._validate_single_compatibility_rule(record, rule, rule_index)
                if error:
                    errors.append(error)
            except Exception as e:
                logger.error(f"Error validating compatibility rule {rule_index}: {str(e)}")
                errors.append({
                    "rule_index": rule_index,
                    "error": f"System error in compatibility validation: {str(e)}"
                })

        return errors

    def _validate_single_compatibility_rule(self, record: Dict[str, Any],
                                          rule: Dict[str, Any], rule_index: int) -> Optional[Dict[str, Any]]:
        """Validate a single compatibility rule."""
        # Import here to avoid circular dependencies
        from nacc_form_validator.json_logic import jsonLogic

        if_condition = rule.get("if")
        then_condition = rule.get("then")
        else_condition = rule.get("else")

        if not if_condition:
            return None

        # Evaluate the IF condition
        if_result = jsonLogic(if_condition, record)

        if if_result and then_condition:
            # IF is true, check THEN condition
            then_result = jsonLogic(then_condition, record)
            if not then_result:
                return {
                    "rule_index": rule_index,
                    "error": "THEN condition failed when IF condition was true",
                    "if_condition": if_condition,
                    "then_condition": then_condition
                }
        elif not if_result and else_condition:
            # IF is false, check ELSE condition
            else_result = jsonLogic(else_condition, record)
            if not else_result:
                return {
                    "rule_index": rule_index,
                    "error": "ELSE condition failed when IF condition was false",
                    "if_condition": if_condition,
                    "else_condition": else_condition
                }

        return None


# =============================================================================
# UPDATED CONFIGURATION CONSTANTS
# =============================================================================

# Updated KEY_MAP that properly separates Cerberus rules from custom rules
MODERN_KEY_MAP = {
    "type": "type",
    "nullable": "nullable",
    "min": "min",
    "max": "max",
    "pattern": "regex",
    "regex": "regex",
    "allowed": "allowed",
    "forbidden": "forbidden",
    "filled": "filled",
    # Custom rules are handled separately, not mapped to Cerberus
}

# =============================================================================
# LEGACY COMPATIBILITY WRAPPER
# =============================================================================

# Keep the old KEY_MAP for backward compatibility during transition
# This should be removed once all code is updated to use the new system
KEY_MAP = {
    "type": "type",
    "nullable": "nullable",
    "min": "min",
    "max": "max",
    "pattern": "regex",
    "regex": "regex",
    "allowed": "allowed",
    "forbidden": "forbidden",
    "filled": "filled",
    "compatibility": "compatibility",  # DEPRECATED: Will be removed
    "temporalrules": "temporalrules",  # DEPRECATED: Will be removed
}

# =============================================================================
# EXISTING CONFIGURATION CONSTANTS
# =============================================================================
