"""Configuration management for UDSv4 QC Validator."""

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Late imports to avoid circular dependencies
from ..logging.logging_config import get_logger

logger = get_logger(__name__)

# =============================================================================
# ENVIRONMENT CONFIGURATION
# This section handles environment variables and paths for the project.
# =============================================================================

# Get the directory where this config_manager.py file is located
# Go up three levels to get the actual project root
config_dir = Path(__file__).parent.resolve()
project_root = config_dir.parent.parent.parent
dotenv_path = project_root / ".env"

# Load environment variables from .env file
load_dotenv(dotenv_path)


# =============================================================================
# INSTRUMENTS AND MAPPING CONFIGURATION
# =============================================================================

# Instrument registry used for data fetch filtering and completion tracking
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
    "c2c2t_neuropsychological_battery_scores",
]

# Namespace (from rule filename stem) → Instrument name
# Rule files are named like "a1_rules.json" → namespace "a1"
namespace_to_instrument = {
    "header": "form_header",
    "a1": "a1_participant_demographics",
    "a1a": "a1a_sdoh",
    "a2": "a2_coparticipant_demographics",
    "a3": "a3_participant_family_history",
    "a4": "a4_participant_medications",
    "a4a": "a4a_adrd_specific_treatments",
    "a5d2": "a5d2_participant_health_history_clinician_assessed",
    "b1": "b1_vital_signs_and_anthropometrics",
    "b3": "b3_unified_parkinsons_disease_rating_scale_updrs_m",
    "b4": "b4_cdr_dementia_staging_instrument",
    "b5": "b5_neuropsychiatric_inventory_questionnaire_npiq",
    "b6": "b6_geriatric_depression_scale",
    "b7": "b7_functional_assessment_scale_fas",
    "b8": "b8_neurological_examination_findings",
    "b9": "b9_clinician_judgment_of_symptoms",
    "c2": "c2c2t_neuropsychological_battery_scores",
    "c2t": "c2c2t_neuropsychological_battery_scores",
    "d1a": "d1a_clinical_syndrome",
    "d1b": "d1b_etiological_diagnosis_and_biomarker_support",
}

uds_events = ["udsv4visit_arm_1"]


# =============================================================================
# JSON SCHEMA TO CERBERUS MAPPING
# =============================================================================

# Map JSON rule keys to Cerberus schema keywords
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
    "compatibility": "compatibility",
    "temporalrules": "temporalrules",
}


# =============================================================================
# QC CONFIGURATION DATACLASS
# =============================================================================


@dataclass
class QCConfig:
    """
    Structured configuration class for the QC pipeline.

    This class centralizes all configuration parameters, provides type hints,
    and allows for default values and environment variable overrides.
    """

    # --- Core REDCap API Configuration ---
    api_token: str | None = field(default_factory=lambda: os.getenv("REDCAP_API_TOKEN") or None)
    api_url: str | None = field(default_factory=lambda: os.getenv("REDCAP_API_URL") or None)
    project_id: str | None = field(default_factory=lambda: os.getenv("PROJECT_ID"))
    report_id: str | None = field(default_factory=lambda: os.getenv("REDCAP_REPORT_ID"))

    # --- Path Configuration ---
    output_path: str = field(
        default_factory=lambda: os.getenv("OUTPUT_PATH", str(project_root / "output"))
    )
    log_path: str | None = field(default_factory=lambda: os.getenv("LOG_PATH"))
    status_path: str | None = field(default_factory=lambda: os.getenv("STATUS_PATH"))
    upload_ready_path: str | None = field(default_factory=lambda: os.getenv("UPLOAD_READY_PATH"))

    # --- Packet-based Rule Paths (Required) ---
    json_rules_path_i: str = field(default_factory=lambda: os.getenv("JSON_RULES_PATH_I", ""))
    json_rules_path_i4: str = field(default_factory=lambda: os.getenv("JSON_RULES_PATH_I4", ""))
    json_rules_path_f: str = field(default_factory=lambda: os.getenv("JSON_RULES_PATH_F", ""))

    # --- Primary Key Configuration ---
    primary_key_field: str = "ptid"

    # --- QC Pipeline Behavior ---
    # Only 'complete_visits' mode is currently supported
    mode: str = "complete_visits"
    test_mode: bool = False  # Use test database instead of production database
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    user_initials: str | None = None
    ptid_list: list[str] | None = None
    # Generate detailed outputs (Validation_Logs, Completed_Visits, Reports,
    # Generation_Summary)
    detailed_run: bool = False
    # Generate comprehensive Rules Validation log (large file, slow generation)
    passed_rules: bool = False

    # --- Performance & Retries ---
    max_workers: int = field(default_factory=lambda: int(os.getenv("MAX_WORKERS", "4")))
    timeout: int = field(default_factory=lambda: int(os.getenv("TIMEOUT", "300")))
    retry_attempts: int = field(default_factory=lambda: int(os.getenv("RETRY_ATTEMPTS", "3")))

    # --- Report Generation ---
    generate_html_report: bool = field(
        default_factory=lambda: os.getenv("GENERATE_HTML_REPORT", "true").lower() == "true"
    )

    # --- Instrument & Event Configuration ---
    instruments: list[str] = field(default_factory=lambda: instruments)
    events: list[str] = field(default_factory=lambda: uds_events)

    def __post_init__(self):
        """Post-initialization path resolution."""
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

    def to_dict(self) -> dict[str, Any]:
        """Converts the configuration to a dictionary."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def to_file(self, file_path: str | Path) -> None:
        """Saves configuration to a JSON file."""
        p = Path(file_path)
        with p.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(self.to_dict(), indent=4))

    @classmethod
    def from_file(cls, file_path: str | Path) -> "QCConfig":
        """Loads configuration from a JSON file."""
        p = Path(file_path)
        if not p.exists():
            return cls()  # Return default config if file not found
        with p.open(encoding="utf-8") as fh:
            data = json.loads(fh.read())
        return cls(**data)

    def get_rules_path_for_packet(self, packet: str) -> str:
        """Get the required rules path for a packet type."""
        packet_paths = {
            "I": self.json_rules_path_i,
            "I4": self.json_rules_path_i4,
            "F": self.json_rules_path_f,
        }
        path = packet_paths.get(packet.upper())
        if not path:
            msg = (
                "No rules path configured for packet '%s'. "
                "Required environment variables: JSON_RULES_PATH_I, "
                "JSON_RULES_PATH_I4, JSON_RULES_PATH_F" % packet
            )
            raise ValueError(msg)
        return path

    def validate(self) -> list[str]:
        """
        Validates the configuration and returns a list of errors.
        An empty list indicates a valid configuration.
        """
        errors = []

        # Validate required fields
        if not self.api_token:
            errors.append("REDCAP_API_TOKEN is required")
        if not self.api_url:
            errors.append("REDCAP_API_URL is required")

        # Require ALL packet rule paths
        required_packet_paths = {
            "JSON_RULES_PATH_I": self.json_rules_path_i,
            "JSON_RULES_PATH_I4": self.json_rules_path_i4,
            "JSON_RULES_PATH_F": self.json_rules_path_f,
        }

        for env_var, path in required_packet_paths.items():
            if not path:
                errors.append(f"Missing required environment variable: {env_var}")

        # Validate packet-specific rules paths
        for env_var, path in required_packet_paths.items():
            if path and not Path(path).is_dir():
                errors.append(f"{env_var} '{path}' is not a valid directory.")

        # Validate and create output path if needed
        if self.output_path and not Path(self.output_path).is_dir():
            try:
                Path(self.output_path).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(
                    f"OUTPUT_PATH '{self.output_path}' is not a valid directory "
                    f"and could not be created: {e}"
                )

        # Validate and create log path if needed
        if self.log_path and not Path(self.log_path).is_dir():
            try:
                Path(self.log_path).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(
                    f"LOG_PATH '{self.log_path}' is not a valid directory "
                    f"and could not be created: {e}"
                )

        # Validate performance settings
        if self.max_workers < 1:
            errors.append("max_workers must be at least 1")
        if self.timeout < 30:
            errors.append("timeout must be at least 30 seconds")
        if self.retry_attempts < 0:
            errors.append("retry_attempts cannot be negative")

        # Validate instrument consistency
        if len(self.instruments) != len(set(self.instruments)):
            errors.append("Duplicate instruments found in configuration.")

        return errors


# =============================================================================
# CONFIGURATION ACCESSOR FUNCTIONS
# Provides a clean, consistent way to access configuration settings
# =============================================================================

# Singleton instance of the configuration
_config_instance: QCConfig | None = None


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
                # Use a simple print for critical config errors, as logging may not be
                # configured yet
                print("Configuration errors found. Cannot continue.")
                for error in errors:
                    print(f"  - {error}")
                raise SystemExit(1)  # Exit if configuration is invalid
    return _config_instance


def get_core_columns() -> list[str]:
    """Returns the core REDCap columns."""
    config = get_config()
    return [config.primary_key_field, "redcap_event_name", "packet"]
