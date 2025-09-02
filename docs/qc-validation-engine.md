# QC Validation Engine Documentation

## Overview

The QC Validation Engine is the core validation component of the UDSv4 REDCap QC Validator system. Built upon the Cerberus validation library and extended with custom NACC-specific validation methods, it provides comprehensive data quality checking for neurological assessment forms. The engine processes individual records through a multi-stage validation pipeline, applying packet-specific rules and generating detailed validation results.

## System Architecture

### Core Components

```
QualityCheck (Coordinator)
    ├── NACCValidator (Custom Validator)
    │   ├── Cerberus Base Validator
    │   ├── Custom Validation Methods
    │   └── Error Handling System
    ├── ValidationResult (Result Model)
    └── Error Management System
```

### Validation Flow

1. **Record Reception**: Individual records received from data routing system
2. **Schema Loading**: Packet-specific validation rules loaded from JSON rule files
3. **Validation Execution**: Multi-stage validation process with custom methods
4. **Result Generation**: Comprehensive validation results with error details
5. **Error Reporting**: Structured error messages with NACC-specific codes

## QualityCheck Class

### Purpose
The `QualityCheck` class serves as the coordination layer for the validation engine, managing the interaction between the data routing system and the underlying validation components.

### Key Responsibilities

- **Validation Orchestration**: Coordinates the validation process for individual records
- **Schema Management**: Loads and manages packet-specific validation schemas
- **Result Processing**: Processes validation outcomes and generates structured results
- **Error Handling**: Manages system-level errors and validation failures

### Core Methods

```python
def quality_check(self, packet_type: str, record: Dict[str, Any]) -> ValidationResult:
    """
    Performs quality checking on a single record using packet-specific rules.
    
    Args:
        packet_type: The packet identifier (I, I4, F) determining rule set
        record: Dictionary containing field values to validate
        
    Returns:
        ValidationResult: Comprehensive validation outcome with error details
    """
```

### Integration Points

- **Data Routing**: Receives records from PacketRuleRouter
- **Configuration**: Uses QCConfig for schema file locations
- **Pipeline**: Integrates with PipelineOrchestrator for batch processing

## NACCValidator Class

### Overview
The `NACCValidator` class extends Cerberus's base validator with custom validation methods specific to neurological assessment requirements. It implements over 20 specialized validation functions covering temporal logic, compatibility rules, computed scores, and medical data validation.

### Custom Validation Methods

#### 1. Compatibility Validation (`_validate_compatibility`)
```python
def _validate_compatibility(self, rule_config, field, value):
    """
    Validates compatibility rules using JSON Logic expressions.
    
    Rule Format:
    {
        "compatibility": {
            "rule_id": "C001", 
            "expression": {"if": [condition, then_clause, else_clause]}
        }
    }
    """
```

**Features:**
- JSON Logic-based conditional validation
- Support for complex if-then-else logic
- Cross-field dependency validation
- Rule identification for error tracking

#### 2. Temporal Rules (`_validate_temporalrules`)
```python
def _validate_temporalrules(self, rule_config, field, value):
    """
    Validates temporal consistency across visits.
    
    Ensures data consistency between current and previous visits
    based on longitudinal study requirements.
    """
```

**Features:**
- Cross-visit data comparison
- Primary key validation
- Previous visit retrieval
- Temporal logic evaluation

#### 3. Logic Validation (`_validate_logic`)
```python
def _validate_logic(self, rule_config, field, value):
    """
    Applies complex logical expressions for field validation.
    
    Supports mathematical computations and conditional logic
    using JSON Logic expressions.
    """
```

**Features:**
- Formula evaluation
- Mathematical computations
- Conditional logic processing
- Expression error handling

#### 4. GDS Score Computation (`_validate_compute_gds`)
```python
def _validate_compute_gds(self, rule_config, field, value):
    """
    Validates Geriatric Depression Scale (GDS) scoring.
    
    Implements complex GDS scoring rules including:
    - Total score calculation
    - Prorated scoring for partial responses
    - Minimum response requirements
    """
```

**Features:**
- Automated score calculation
- Prorated scoring logic
- Response completeness validation
- Clinical scoring standards

#### 5. Cross-Field Comparison (`_validate_compare_with`)
```python
def _validate_compare_with(self, rule_config, field, value):
    """
    Compares field values with other fields in the same record.
    
    Supports various comparison operations and conditional logic.
    """
```

#### 6. Previous Visit Comparison (`_validate_compare_with_prev`)
```python
def _validate_compare_with_prev(self, rule_config, field, value):
    """
    Compares current visit values with previous visit data.
    
    Enables longitudinal data consistency validation.
    """
```

#### 7. Age Comparison (`_validate_compare_age`)
```python
def _validate_compare_age(self, rule_config, field, value):
    """
    Validates age-related constraints and calculations.
    
    Handles date arithmetic and age-based validation rules.
    """
```

#### 8. Date Range Validation
```python
def _validate_curr_date_max(self, rule_config, field, value)
def _validate_curr_date_min(self, rule_config, field, value)
def _validate_curr_year_max(self, rule_config, field, value)
def _validate_curr_year_min(self, rule_config, field, value)
```

**Features:**
- Current date boundary validation
- Year-based constraints
- Date format validation
- Temporal boundary enforcement

#### 9. Fill Requirements (`_validate_filled`)
```python
def _validate_filled(self, rule_config, field, value):
    """
    Validates field completion requirements.
    
    Enforces conditional field completion based on other field values.
    """
```

#### 10. External Data Validation (`_validate_check_with`)
```python
def _validate_check_with(self, rule_config, field, value):
    """
    Validates values against external data sources.
    
    Currently supports RXNORM drug code validation.
    """
```

## ValidationResult Model

### Structure
```python
@dataclass
class ValidationResult:
    passed: bool                              # Overall validation status
    sys_failure: bool                         # System-level failure indicator
    errors: Dict[str, List[str]]             # Field-specific error messages
    error_tree: Optional[DocumentErrorTree]   # Detailed error structure
```

### Attributes

#### `passed: bool`
- **Purpose**: Indicates whether the record satisfied all validation rules
- **Values**: `True` for valid records, `False` for validation failures
- **Usage**: Primary indicator for data quality assessment

#### `sys_failure: bool`
- **Purpose**: Indicates system-level errors preventing reliable validation
- **Triggers**: Database connection issues, rule parsing errors, missing schemas
- **Usage**: Distinguishes between data quality issues and system problems

#### `errors: Dict[str, List[str]]`
- **Purpose**: Human-readable error messages organized by field
- **Structure**: Field names as keys, lists of error messages as values
- **Usage**: User-facing error reporting and quality reports

#### `error_tree: Optional[DocumentErrorTree]`
- **Purpose**: Detailed hierarchical error structure from Cerberus
- **Usage**: Debugging rule logic and technical error analysis
- **Format**: Cerberus DocumentErrorTree object with nested error details

## Error Management System

### Error Definitions (`ErrorDefs`)

The system defines custom error codes for NACC-specific validation scenarios:

```python
class ErrorDefs:
    CURR_DATE_MAX = ErrorDefinition(0x1000, "max")
    CURR_YEAR_MAX = ErrorDefinition(0x1001, "max")
    COMPATIBILITY = ErrorDefinition(0x1008, "compatibility")
    TEMPORAL = ErrorDefinition(0x2000, "temporalrules")
    FORMULA = ErrorDefinition(0x2003, "logic")
    # ... additional error definitions
```

### Custom Error Handler (`CustomErrorHandler`)

Extends Cerberus's BasicErrorHandler to provide domain-specific error messages:

```python
class CustomErrorHandler(BasicErrorHandler):
    def __init__(self, schema: Mapping = None, tree: ErrorTree = None):
        super().__init__()
        self.__set_custom_error_codes()
        self._custom_schema = schema
```

**Features:**
- NACC-specific error messages
- Error code mapping for QC check codes
- Contextual error information
- Multilingual error support potential

### Error Code Categories

#### Data Range Errors (0x1000-0x1999)
- Date and year boundary validations
- Fill requirement violations
- Basic data type constraints

#### Logic Errors (0x2000-0x2999)
- Temporal rule violations
- Compatibility rule failures
- Formula evaluation errors
- Computed score discrepancies

#### Advanced Validation Errors (0x3000-0x3999)
- External data validation failures
- Complex comparison errors
- Age calculation problems
- System-level validation issues

## Schema Integration

### Rule File Structure
The validation engine uses JSON rule files organized by packet type:

```
config/
├── I/          # Initial visit rules
├── I4/         # Four-month follow-up rules
├── F/          # Annual follow-up rules
└── json_rules/ # Common rule definitions
```

### Rule Application Process

1. **Schema Loading**: Packet-specific JSON rules loaded into Cerberus schema format
2. **Rule Compilation**: JSON Logic expressions compiled for efficient evaluation
3. **Validation Execution**: Rules applied in dependency order
4. **Error Collection**: Validation failures collected and categorized
5. **Result Generation**: Comprehensive ValidationResult created

### Rule Types Supported

- **Basic Validation**: Data types, required fields, allowed values
- **Range Validation**: Numeric ranges, date boundaries, string lengths
- **Compatibility Rules**: Cross-field logical dependencies
- **Temporal Rules**: Cross-visit consistency requirements
- **Computed Fields**: Automated calculations and score validation
- **External Validation**: Third-party data source verification

## Performance Considerations

### Optimization Strategies

#### 1. Schema Caching
- Rule schemas cached after initial load
- Reduces file I/O for repeated validations
- Memory-efficient schema storage

#### 2. Lazy Evaluation
- Complex rules evaluated only when triggered
- Previous visit data retrieved on-demand
- External validations cached when possible

#### 3. Batch Processing
- Records processed in configurable batches
- Memory usage optimized for large datasets
- Progress tracking for long-running validations

#### 4. Error Short-Circuiting
- Validation stops on system failures
- Non-critical errors accumulated efficiently
- Early termination for invalid record structures

### Memory Management

- **Record Processing**: Individual records processed independently
- **Schema Storage**: Shared schema instances across validations
- **Error Accumulation**: Efficient error collection and reporting
- **Cleanup**: Automatic cleanup of temporary validation objects

## Integration with Pipeline

### Input Processing
```python
# Records received from PacketRuleRouter
record = {
    'field1': 'value1',
    'field2': 'value2',
    'packet_type': 'I'
}

# Validation execution
result = quality_check.quality_check('I', record)
```

### Output Generation
```python
# ValidationResult structure
{
    'passed': False,
    'sys_failure': False,
    'errors': {
        'field1': ['Value exceeds maximum allowed'],
        'field2': ['Required field cannot be empty']
    },
    'error_tree': <DocumentErrorTree object>
}
```

### Error Propagation
- Field-level errors propagated to record level
- System failures escalated to batch level
- Comprehensive error logging throughout pipeline

## Extensibility

### Adding Custom Validation Methods

1. **Method Definition**: Create new `_validate_*` method in NACCValidator
2. **Error Definition**: Add corresponding error code in ErrorDefs
3. **Error Message**: Define user-friendly message in CustomErrorHandler
4. **Rule Integration**: Update JSON rule files to use new validation type

### Example Custom Validator
```python
def _validate_custom_rule(self, rule_config, field, value):
    """
    Custom validation method example.
    
    Args:
        rule_config: Rule configuration from JSON schema
        field: Field name being validated
        value: Field value to validate
    """
    try:
        # Custom validation logic
        if not self._custom_validation_logic(value, rule_config):
            self._error(field, ErrorDefs.CUSTOM_ERROR.code, rule_config)
    except Exception as e:
        self._error(field, ErrorDefs.SYSTEM_ERROR.code, str(e))
```

### Schema Extension
```json
{
    "field_name": {
        "type": "string",
        "custom_rule": {
            "parameter1": "value1",
            "parameter2": "value2"
        }
    }
}
```

## Monitoring and Debugging

### Validation Metrics
- **Pass Rate**: Percentage of records passing validation
- **Error Distribution**: Frequency of different error types
- **Performance Metrics**: Validation time per record
- **System Health**: System failure rate and causes

### Debug Features
- **Detailed Error Trees**: Hierarchical error structure for rule debugging
- **Rule Tracing**: Track which rules triggered for specific records
- **Schema Validation**: Validate rule files before processing
- **Performance Profiling**: Identify bottleneck validation methods

### Logging Integration
```python
import logging

logger = logging.getLogger('qc_validation')

# Validation start
logger.info(f"Starting validation for record {record_id}")

# Validation results
logger.debug(f"Validation result: {result.passed}")

# Error details
if result.errors:
    logger.warning(f"Validation errors: {result.errors}")
```

## Error Recovery and Resilience

### System Failure Handling
- **Graceful Degradation**: Continue processing when possible
- **Error Isolation**: Prevent individual record failures from affecting batch
- **Retry Logic**: Automatic retry for transient system failures
- **Fallback Validation**: Basic validation when advanced rules fail

### Data Quality Assurance
- **Schema Validation**: Ensure rule files are valid before processing
- **Rule Testing**: Automated testing of validation rules
- **Regression Testing**: Prevent rule changes from breaking existing validation
- **Quality Metrics**: Continuous monitoring of validation effectiveness

## Conclusion

The QC Validation Engine provides a robust, extensible framework for neurological assessment data validation. Through its combination of standard Cerberus validation capabilities and custom NACC-specific methods, it ensures comprehensive data quality checking while maintaining high performance and reliability. The modular architecture enables easy extension for new validation requirements while preserving the integrity of existing validation logic.

The engine's integration with the broader UDSv4 system through the QualityCheck coordinator ensures seamless operation within the data processing pipeline, providing essential data quality assurance for neurological research and clinical assessment workflows.
