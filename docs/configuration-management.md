# Configuration Management System

## Overview

The Configuration Management System is the central configuration hub for the UDSv4 REDCap Quality Control Validator. It provides structured, environment-aware configuration management with type safety, validation, and modern design patterns. The system centralizes all configuration parameters, handles environment variable loading, and provides validated access to configuration settings throughout the application.

## Architecture

### Core Components

1. **QCConfig Class**: Modern dataclass-based configuration with type hints and validation
2. **Configuration Validators**: Modular validation system for configuration integrity
3. **Environment Management**: Automatic environment variable loading and path resolution
4. **Instrument Configuration**: Mapping between REDCap instruments and validation rules
5. **Dynamic Rule System**: Support for variable-based rule selection

### Design Principles

- **Type Safety**: All configuration parameters are type-hinted and validated
- **Environment Awareness**: Automatic loading from environment variables with fallbacks
- **Validation First**: Configuration is validated before use to prevent runtime errors
- **Modular Validation**: Separate validators for different concern areas
- **Backward Compatibility**: Legacy configuration access patterns are preserved

## Configuration Structure

### Environment Variables

The system loads configuration from environment variables with the following priority:

1. Explicit environment variables (`.env` file or system environment)
2. Default values defined in the configuration class
3. Computed defaults based on project structure

#### Required Environment Variables

```
REDCAP_API_TOKEN          # REDCap API authentication token
REDCAP_API_URL            # REDCap API endpoint URL
PROJECT_ID                # REDCap project identifier
JSON_RULES_PATH_I         # Path to Initial Visit validation rules
JSON_RULES_PATH_I4        # Path to Initial Visit (Form 4) validation rules  
JSON_RULES_PATH_F         # Path to Follow-up Visit validation rules
```

#### Optional Environment Variables

```
OUTPUT_PATH               # Output directory for processed data (default: project_root/output)
LOG_PATH                  # Logging directory path
STATUS_PATH               # Status tracking file path
UPLOAD_READY_PATH         # Upload-ready data staging path
LOG_LEVEL                 # Logging verbosity (default: INFO)
MAX_WORKERS               # Concurrent processing threads (default: 4)
TIMEOUT                   # API request timeout in seconds (default: 300)
RETRY_ATTEMPTS            # Number of retry attempts for failed operations (default: 3)
GENERATE_HTML_REPORT      # Enable HTML report generation (default: true)
```

### Instrument Configuration

#### Instruments List

The `instruments` list defines all REDCap form instruments that are processed by the quality control system:

```python
instruments = [
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
]
```

#### Instrument-to-JSON Mapping

The `instrument_json_mapping` dictionary maps each instrument to its corresponding validation rule files:

```python
instrument_json_mapping = {
    "form_header": ["header_rules.json"],
    "a1_participant_demographics": ["a1_rules.json"],
    # ... additional mappings
    "c2c2t_neuropsychological_battery_scores": [
        "c2_rules.json",
        "c2t_rules.json",
    ],
}
```

#### Purpose and Rationale

The instrument configuration serves multiple critical purposes despite the fact that these instrument names do not directly correspond to REDCap database fields:

1. **Organizational Structure**: Instruments provide a logical grouping mechanism for related REDCap fields and variables. This organizational structure makes the system maintainable and comprehensible.

2. **Rule File Organization**: Each instrument maps to specific JSON validation rule files. This mapping allows the system to apply the correct validation rules to the appropriate data subsets.

3. **Processing Logic**: The instrument concept enables the system to:
   - Determine which validation rules to load
   - Group related variables for processing
   - Apply instrument-specific transformations
   - Generate meaningful logging and error messages
   - Track completion status per logical form group

4. **Data Integrity**: By mapping instruments to their completion status variables (e.g., `a1_participant_demographics_complete`), the system can determine which data should be validated and which should be excluded from processing.

5. **Modular Validation**: Different instruments may require different validation approaches, rule sets, or processing pipelines. The instrument mapping enables this modularity.

6. **Audit and Reporting**: Instrument-based organization enables detailed reporting on validation results, error tracking, and quality metrics at the form level.

### Dynamic Rule Selection

For instruments with variable validation requirements, the system supports dynamic rule selection:

```python
DYNAMIC_RULE_INSTRUMENTS = {
    "c2c2t_neuropsychological_battery_scores": {
        "discriminant_variable": "loc_c2_or_c2t",
        "rule_mappings": {
            "C2": "c2_rules.json",
            "C2T": "c2t_rules.json"
        }
    }
}
```

This configuration allows the system to select different validation rules based on the value of discriminant variables in the data.

## Configuration Class (QCConfig)

### Class Definition

The `QCConfig` class is a modern dataclass that centralizes all configuration parameters with type safety and automatic validation:

```python
@dataclass
class QCConfig:
    # Core REDCap API Configuration
    api_token: Optional[str]
    api_url: Optional[str]
    project_id: Optional[str]
    
    # Path Configuration
    output_path: str
    log_path: Optional[str]
    
    # Performance Configuration
    max_workers: int = 4
    timeout: int = 300
    
    # Processing Configuration
    mode: str = 'complete_visits'
    test_mode: bool = False
    # ... additional fields
```

### Key Features

1. **Automatic Environment Loading**: Fields are automatically populated from environment variables
2. **Type Validation**: All fields are type-hinted and validated
3. **Path Resolution**: Relative paths are automatically resolved to absolute paths
4. **Default Values**: Sensible defaults are provided for optional parameters
5. **Validation**: Configuration is validated before use

### Configuration Methods

#### `get_config(force_reload=False, skip_validation=False)`

Returns a singleton instance of the configuration. On first call, loads and validates the configuration.

#### `validate()`

Performs comprehensive validation using modular validators and returns a list of errors.

#### `to_dict()` / `to_file()`

Serialization methods for configuration persistence and debugging.

#### `get_rules_path_for_packet(packet)`

Returns the appropriate validation rules path for a given packet type (I, I4, F).

## Validation System

### Modular Validators

The system uses a modular validation approach with specialized validators:

1. **RequiredFieldsValidator**: Validates presence of required configuration
2. **PathValidator**: Validates and creates necessary directory paths
3. **PerformanceValidator**: Validates performance-related settings
4. **CustomValidator**: Validates business logic and constraints

### Validation Process

```python
def validate(self) -> List[str]:
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
```

### Error Handling

Configuration validation errors result in immediate application termination with clear error messages, preventing runtime failures due to misconfiguration.

## Data Fetching Configuration

### REDCap Events

The system is configured to process specific REDCap events:

```python
uds_events = [
    "udsv4_ivp_1_arm_1",  # Initial Visit 
    "udsv4_fvp_2_arm_1"   # Follow-up Visit
]
```

### Filter Logic Configuration

#### Complete Events Filter

The `complete_events_with_incomplete_qc_filter_logic` defines REDCap filter logic that selects:
- Events where all instruments are marked as complete (status = 2)
- Records that have not yet been quality checked (qc_status_complete = 0 or empty)

```python
complete_events_with_incomplete_qc_filter_logic = (
    "(" +
    " and ".join(f"[{inst}]=2" for inst in complete_instruments_vars) +
    ") and ([qc_status_complete] = 0 or [qc_status_complete] = \"\")"
)
```

#### Quality Control Filter

The `qc_filterer_logic` targets records requiring quality control review:

```python
qc_filterer_logic = '[qc_status_complete] = 0 or [qc_status_complete] = ""'
```

## JSON Schema to Cerberus Mapping

The configuration includes mapping between JSON Schema validation rules and Cerberus validator syntax:

```python
KEY_MAP = {
    "type": "type",
    "nullable": "nullable",
    "min": "min",
    "max": "max",
    "pattern": "regex",
    "allowed": "allowed",
    "forbidden": "forbidden",
    "required": "required",
    "anyof": "anyof",
    "oneof": "oneof",
    "allof": "allof",
    "formatting": "formatting",
    "compatibility": "compatibility",
}
```

This mapping enables the system to convert JSON-based validation rules into Cerberus validation schemas.

## Configuration Access Patterns

### Singleton Pattern

The configuration system uses a singleton pattern to ensure consistent configuration access across the application:

```python
def get_config(force_reload: bool = False, skip_validation: bool = False) -> QCConfig:
    global _config_instance
    if _config_instance is None or force_reload:
        _config_instance = load_config_from_env()
        if not skip_validation:
            errors = _config_instance.validate()
            if errors:
                # Exit if configuration is invalid
                raise SystemExit(1)
    return _config_instance
```

### Helper Functions

The system provides convenience functions for common configuration access patterns:

- `get_instruments()`: Returns the list of configured instruments
- `get_instrument_json_mapping()`: Returns the instrument-to-JSON mapping
- `get_output_path()`: Returns the configured output directory path
- `get_core_columns()`: Returns core REDCap columns (ptid, redcap_event_name, packet)
- `get_completion_columns()`: Returns completion status columns for all instruments

## Integration with Data Fetching

The configuration system provides essential parameters for the data fetching pipeline:

1. **API Credentials**: REDCap API token and URL for authentication
2. **Instrument Lists**: Defines which forms to fetch from REDCap
3. **Event Filtering**: Specifies which REDCap events to include
4. **Filter Logic**: Provides REDCap filter logic for targeted data retrieval
5. **Processing Mode**: Determines data transformation and validation approach
6. **Output Configuration**: Specifies where processed data should be saved

## Best Practices

### Configuration Management

1. **Environment Variables**: Store sensitive configuration in environment variables
2. **Validation**: Always validate configuration before use
3. **Error Handling**: Handle configuration errors gracefully with clear messages
4. **Documentation**: Keep configuration documentation current with code changes

### Extension and Maintenance

1. **Adding New Instruments**: Update both `instruments` list and `instrument_json_mapping`
2. **New Configuration Parameters**: Add to `QCConfig` class with appropriate defaults
3. **Validation Rules**: Add custom validators for new configuration constraints
4. **Backward Compatibility**: Maintain aliases for configuration changes

### Testing

1. **Isolated Testing**: Use `skip_validation=True` for unit tests
2. **Configuration Mocking**: Mock configuration for component testing
3. **Validation Testing**: Test each validator independently
4. **Integration Testing**: Test complete configuration loading and validation

## Security Considerations

1. **API Token Protection**: Never commit API tokens to version control
2. **Environment Isolation**: Use separate configurations for development, testing, and production
3. **Path Validation**: Validate all file paths to prevent directory traversal attacks
4. **Access Control**: Ensure configuration files have appropriate permissions

## Troubleshooting

### Common Configuration Issues

1. **Missing Environment Variables**: Check that all required environment variables are set
2. **Invalid Paths**: Ensure all specified paths exist and are accessible
3. **API Connectivity**: Verify REDCap API URL and token are correct
4. **Permission Issues**: Check file system permissions for output directories

### Diagnostic Commands

```python
# Check current configuration
config = get_config()
print(config.to_dict())

# Validate configuration
errors = config.validate()
if errors:
    for error in errors:
        print(f"Configuration error: {error}")

# Test API connectivity
from src.pipeline.core.fetcher import RedcapApiClient
client = RedcapApiClient(config)
# Test API call...
```
