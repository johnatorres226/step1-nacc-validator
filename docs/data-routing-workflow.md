# Data Routing and Workflow System

## Overview

The Data Routing and Workflow System is the orchestration engine of the UDSv4 REDCap QC Validator, responsible for intelligently directing data through appropriate processing pathways based on configuration modes, packet types, and data characteristics. This system implements a sophisticated multi-stage pipeline that ensures each record receives the correct validation rules and processing logic based on its attributes and the system's operational context.

## System Architecture

### Design Philosophy

The routing system is built on several key architectural principles:

1. **Intelligent Routing**: Automatic determination of processing pathways based on data characteristics
2. **Hierarchical Rule Resolution**: Multi-level rule selection combining packet-based and dynamic routing
3. **Mode-Based Processing**: Different operational modes for different use cases
4. **Pipeline Orchestration**: Coordinated execution of multiple processing stages
5. **Error Recovery**: Robust fallback mechanisms and error handling

### Core Components

The routing system consists of several interconnected components:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Data Routing and Workflow System                 │
├─────────────────────────────────────────────────────────────────────┤
│  Processing Mode Router                                             │
│  • Complete Visits • Incomplete Visits                             │
├─────────────────────────────────────────────────────────────────────┤
│  Packet Classification System                                       │
│  • Initial Visit (I) • Initial Visit Form 4 (I4) • Follow-up (F)    │
├─────────────────────────────────────────────────────────────────────┤
│  Hierarchical Rule Resolution                                       │
│  • Packet-Based Routing • Dynamic Instrument Routing                │
├─────────────────────────────────────────────────────────────────────┤
│  Pipeline Orchestration Engine                                      │
│  • Stage Management • Context Preservation • Error Handling         │
└─────────────────────────────────────────────────────────────────────┘
```

## Processing Modes and Routing Logic

### Complete Visits Mode

**File Location**: `src/pipeline/core/pipeline_orchestrator.py` (lines 275-310)
**Functions**: `_execute_data_preparation_stage()`, `build_complete_visits_df()`

#### Purpose and Scope

Complete Visits Mode is designed for production quality control of finalized data. It processes only visits where all required instruments have been completed and marked as finished in REDCap.

#### Processing Logic

```python
# From pipeline_orchestrator.py
if self.config.mode == "complete_visits" and not data_df.empty:
    complete_visits_df, complete_visits_tuples = build_complete_visits_df(
        data_df, self.config.instruments
    )
    
    # Filter data to complete visits only
    if not complete_visits_df.empty:
        complete_visits_mask = data_df.set_index([primary_key, 'redcap_event_name']).index.isin(
            complete_visits_df.set_index([primary_key, 'redcap_event_name']).index
        )
        data_df = data_df[complete_visits_mask].copy()
```

#### Workflow Steps

1. **Visit Identification**: Scans all data to identify unique participant-event combinations
2. **Completion Assessment**: Evaluates each visit to determine if all instruments are marked complete (status = '2')
3. **Quality Control Filter**: Excludes visits that have already undergone quality control review
4. **Data Filtering**: Restricts processing to only complete visits
5. **Validation Routing**: Routes complete visit data through full validation pipeline

#### File Dependencies

- **Visit Processing**: `src/pipeline/core/visit_processing.py`
  - `build_complete_visits_df()`: Main orchestration function
  - `identify_complete_visits()`: Identifies truly complete visits
  - `create_completion_mask()`: Creates vectorized completion assessment

#### Assumptions and Requirements

- All required instruments must have completion status variables (e.g., `a1_participant_demographics_complete`)
- Completion status must be coded as '2' for complete instruments
- REDCap event names must be properly configured
- Packet information must be available for routing

#### Use Cases

- **Production QC**: Daily quality control review of completed visits
- **NACC Submission**: Preparation of clean data for NACC submission
- **Final Review**: Comprehensive validation of finalized assessments

### Complete Instruments Mode

**File Location**: `src/pipeline/core/data_processing.py` (instrument subset transformation)
**Functions**: `apply_instrument_subset_transformation()`, `prepare_instrument_data_cache()`

#### Purpose and Scope

Complete Instruments Mode processes individual instruments as they are completed, regardless of overall visit completion status. This mode is useful for progressive quality control during ongoing data collection.

#### Processing Logic

```python
# From data_processing.py (conceptual - in data transformer)
for index, row in transformed_df.iterrows():
    for instrument in instrument_list:
        completion_var = f"{instrument}_complete"
        
        if (completion_var in row and 
            pd.notna(row[completion_var]) and 
            str(row[completion_var]) != '2'):
            
            # Nullify all variables for incomplete instruments
            instrument_vars = instrument_to_vars_map.get(instrument, [])
            for var in instrument_vars:
                if var in transformed_df.columns:
                    transformed_df.at[index, var] = pd.NA
```

#### Workflow Steps

1. **Instrument Assessment**: Evaluates completion status for each individual instrument
2. **Data Nullification**: Nullifies data for incomplete instruments to prevent validation errors
3. **Selective Processing**: Processes only completed instruments
4. **Individual Validation**: Applies instrument-specific validation rules
5. **Progressive QC**: Enables quality control as data collection progresses

#### File Dependencies

- **Data Processing**: `src/pipeline/core/data_processing.py`
  - `prepare_instrument_data_cache()`: Prepares instrument-specific data subsets
  - `get_variables_for_instrument()`: Maps instruments to their variables

#### Assumptions and Requirements

- Individual instruments can be validated independently
- Incomplete instruments should be excluded from validation
- Instrument-to-variable mappings are properly configured
- Rules exist for each instrument being processed

#### Use Cases

- **Progressive QC**: Quality control during active data collection
- **Instrument Focus**: Targeted validation of specific assessment tools
- **Workflow Management**: Identifying which instruments need completion

## Packet Classification System

### Packet Types and Routing

**File Location**: `src/pipeline/io/packet_router.py`
**Functions**: `PacketRuleRouter.get_rules_for_record()`, `_load_rules_from_path()`

#### Packet Categories

The system recognizes three primary packet types for UDSv4 data:

1. **Initial Visit (I)**: First assessment visit for participants
2. **Initial Visit Form 4 (I4)**: Specialized initial visit variant
3. **Follow-up Visit (F)**: Subsequent assessment visits

#### Packet Detection Logic

```python
# From packet_router.py
def get_rules_for_record(self, record: Dict[str, Any], instrument_name: str) -> Dict[str, Any]:
    packet_value = record.get('packet', '').upper().strip()
    
    if not packet_value:
        logger.warning(f"Missing packet value for record, cannot route to rules")
        return {}
    
    if packet_value not in ['I', 'I4', 'F']:
        logger.warning(f"Unknown packet value: {packet_value}")
        return {}
    
    rules_path = self.config.get_rules_path_for_packet(packet_value)
    return self._load_rules_from_path(rules_path, instrument_name)
```

#### Rule Path Configuration

Each packet type maps to a specific rule directory:

- **I Packet**: `JSON_RULES_PATH_I` environment variable
- **I4 Packet**: `JSON_RULES_PATH_I4` environment variable  
- **F Packet**: `JSON_RULES_PATH_F` environment variable

#### File Dependencies

- **Configuration**: `src/pipeline/config_manager.py`
  - `get_rules_path_for_packet()`: Returns appropriate rules path for packet type
- **Rule Loading**: JSON rule files in packet-specific directories

### Packet-Based Rule Selection

#### Rule File Organization

Rules are organized in packet-specific directories:

```
config/
├── I/                     # Initial Visit rules
│   ├── a1_rules.json
│   ├── b1_rules.json
│   └── ...
├── I4/                    # Initial Visit Form 4 rules
│   ├── a1_rules.json
│   ├── b1_rules.json
│   └── ...
└── F/                     # Follow-up Visit rules
    ├── a1_rules.json
    ├── b1_rules.json
    └── ...
```

#### Rule Loading Process

1. **Packet Identification**: Extract packet value from record
2. **Path Resolution**: Determine appropriate rules directory
3. **File Mapping**: Map instrument to corresponding JSON rule files
4. **Rule Loading**: Load and parse JSON validation rules
5. **Rule Validation**: Validate rule syntax and completeness

#### Error Handling

- **Missing Packet**: Warning logged, no rules returned
- **Invalid Packet**: Warning logged with packet value
- **Missing Rules**: Warning logged, empty rules returned
- **Invalid JSON**: Error logged with file path and JSON error details

## Hierarchical Rule Resolution

### Two-Stage Resolution Process

**File Location**: `src/pipeline/io/hierarchical_router.py`
**Functions**: `HierarchicalRuleResolver.resolve_rules()`, `_apply_dynamic_routing()`

The system implements a sophisticated two-stage rule resolution process:

#### Stage 1: Packet-Based Routing

```python
# From hierarchical_router.py
def resolve_rules(self, record: Dict[str, Any], instrument_name: str) -> Dict[str, Any]:
    packet_value = record.get('packet', '').upper().strip()
    
    if not packet_value:
        return {}
    
    # First stage: Get packet-specific base rules
    base_rules = self.packet_router.get_rules_for_record(record, instrument_name)
    
    if not base_rules:
        return {}
```

#### Stage 2: Dynamic Instrument Routing

```python
# Continuation from hierarchical_router.py
    # Second stage: Apply dynamic routing if needed
    if is_dynamic_rule_instrument(instrument_name):
        final_rules = self._apply_dynamic_routing(
            base_rules, record, instrument_name, packet_value
        )
        return final_rules
    
    return base_rules
```

### Dynamic Instrument Routing

#### Purpose and Scope

Dynamic routing handles instruments that require different validation rules based on data values within the record. The primary example is the C2/C2T neuropsychological battery, which uses different rule sets based on the cognitive assessment tool used.

#### Configuration

**File Location**: `src/pipeline/config_manager.py` (lines 134-155)

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

#### Dynamic Resolution Logic

```python
# From hierarchical_router.py
def _apply_dynamic_routing(self, base_rules, record, instrument_name, packet):
    discriminant_var = get_discriminant_variable(instrument_name)
    discriminant_value = record.get(discriminant_var, '').upper()
    
    if not discriminant_value:
        # Use default variant when discriminant is missing
        if isinstance(base_rules, dict) and base_rules:
            default_variant = list(base_rules.keys())[0]
            return base_rules[default_variant]
        return base_rules
    
    # Check if discriminant value exists in rules
    if discriminant_value in base_rules:
        return base_rules[discriminant_value]
    else:
        logger.warning(f"No variant rules found for {discriminant_var}={discriminant_value}")
        return base_rules
```

#### File Dependencies

- **Configuration Functions**: `src/pipeline/config_manager.py`
  - `is_dynamic_rule_instrument()`: Checks if instrument uses dynamic routing
  - `get_discriminant_variable()`: Returns discriminant variable name
  - `get_rule_mappings()`: Returns rule mapping configuration

### Rule Resolution Workflow

1. **Instrument Analysis**: Determine if instrument requires dynamic routing
2. **Packet Resolution**: Load base rules for the record's packet type
3. **Discriminant Evaluation**: Examine discriminant variable values
4. **Variant Selection**: Select appropriate rule variant based on discriminant
5. **Rule Finalization**: Return resolved, flat rule set for validation

## Pipeline Orchestration Engine

### Five-Stage Pipeline Architecture

**File Location**: `src/pipeline/core/pipeline_orchestrator.py`
**Main Function**: `PipelineOrchestrator.run_pipeline()`

The pipeline orchestrator manages the complete workflow through five distinct stages:

#### Stage 1: Data Fetching

**Function**: `_execute_data_fetch_stage()`
**Purpose**: Extract data from REDCap using configured parameters

```python
def _execute_data_fetch_stage(self, output_dir, date_tag, time_tag):
    pipeline = RedcapETLPipeline(self.config)
    etl_result = pipeline.run(output_dir, date_tag, time_tag)
    
    return DataFetchResult(
        data=etl_result.data,
        records_processed=etl_result.records_processed,
        execution_time=execution_time,
        # ... additional metadata
    )
```

**Key Operations**:
- REDCap API connection and authentication
- Filter logic application based on processing mode
- Data extraction and initial validation
- Basic data transformation and cleaning

#### Stage 2: Rules Loading

**Function**: `_execute_rules_loading_stage()`
**Purpose**: Load and prepare validation rules using packet routing

```python
def _execute_rules_loading_stage(self):
    packet_router = PacketRuleRouter(self.config)
    hierarchical_resolver = HierarchicalRuleResolver(self.config)
    
    rules_cache = {}
    for instrument in self.config.instruments:
        # Use hierarchical resolver for comprehensive rule loading
        instrument_rules = hierarchical_resolver.resolve_rules(sample_record, instrument)
        if instrument_rules:
            rules_cache[instrument] = instrument_rules
```

**Key Operations**:
- Packet router initialization
- Hierarchical rule resolver setup
- Rule loading for all configured instruments
- Variable mapping generation

#### Stage 3: Data Preparation

**Function**: `_execute_data_preparation_stage()`
**Purpose**: Prepare data based on processing mode

```python
def _execute_data_preparation_stage(self, data_fetch_result, rules_loading_result):
    data_df = data_fetch_result.data
    
    # Handle complete visits mode
    if self.config.mode == "complete_visits" and not data_df.empty:
        complete_visits_df, complete_visits_tuples = build_complete_visits_df(
            data_df, self.config.instruments
        )
        # Filter to complete visits only
        data_df = data_df[complete_visits_mask].copy()
    
    # Prepare instrument data cache
    instrument_data_cache = prepare_instrument_data_cache(
        data_df, self.config.instruments, # ... additional parameters
    )
```

**Key Operations**:
- Mode-specific data processing
- Complete visits identification and filtering
- Instrument data cache preparation
- Data subset generation for each instrument

#### Stage 4: Validation Processing

**Function**: `_execute_validation_stage()`
**Purpose**: Apply validation rules with appropriate routing

The validation stage uses different routing strategies based on configuration:

- **Hierarchical Routing**: `validate_data_with_hierarchical_routing()` (Phase 2)
- **Packet Routing**: `validate_data_with_packet_routing()` (Phase 1)

**Key Operations**:
- Rule resolution for each record
- Schema building from resolved rules
- Validation execution using QualityCheck engine
- Error categorization and logging

#### Stage 5: Report Generation

**Function**: `_execute_report_generation_stage()`
**Purpose**: Generate output files and reports

**Key Operations**:
- Error report generation
- Validation log compilation
- Summary report creation
- File export and organization

### Pipeline Context Management

#### ETL Context

**File Location**: `src/pipeline/core/fetcher.py` (lines 31-47)

```python
@dataclass
class ETLContext:
    config: QCConfig
    run_date: str
    time_stamp: str
    output_path: Optional[Path] = None
    
    @classmethod
    def create(cls, config, output_path=None, date_tag=None, time_tag=None):
        # Timestamp management and path resolution
```

#### Pipeline Results

**File Location**: `src/pipeline/core/pipeline_results.py`

The system uses structured result objects to maintain execution context:

- **DataFetchResult**: Data extraction results and metadata
- **RulesLoadingResult**: Rule loading success/failure information
- **DataPreparationResult**: Data preparation outcomes
- **ValidationResult**: Comprehensive validation results
- **ReportGenerationResult**: Output generation summary

### Error Handling and Recovery

#### Stage-Level Error Handling

Each pipeline stage implements comprehensive error handling:

```python
try:
    # Stage execution
    result = self._execute_stage(...)
    return result
except Exception as e:
    self.logger.error(f"Stage failed: {e}")
    raise StageSpecificError(f"Failed to execute stage: {e}", e)
```

#### Pipeline-Level Recovery

```python
def run_pipeline(self):
    try:
        # Execute all stages
        return successful_result
    except Exception as e:
        total_time = time.time() - self.start_time
        failed_result = self._create_failed_result(e, total_time, output_dir)
        return failed_result
```

#### Error Categories

1. **Configuration Errors**: Invalid or missing configuration parameters
2. **Data Fetch Errors**: REDCap API failures or network issues
3. **Rules Loading Errors**: Missing or invalid validation rules
4. **Data Processing Errors**: Data transformation or preparation failures
5. **Validation Errors**: Schema building or validation execution failures
6. **Output Errors**: File system or report generation failures

## Data Flow and Routing Decisions

### Decision Tree for Data Routing

The system follows a structured decision tree for routing each record:

```
REDCap Record Input
├── Processing Mode Check
│   ├── complete_visits → Complete Visits Filter → Validation
│   ├── complete_instruments → Instrument Subset Filter → Validation
│   └── custom → Custom Filter Logic → Validation
├── Packet Classification
│   ├── Packet = "I" → Initial Visit Rules Path
│   ├── Packet = "I4" → Initial Visit Form 4 Rules Path
│   ├── Packet = "F" → Follow-up Visit Rules Path
│   └── Unknown/Missing → Error Handling
├── Instrument Analysis
│   ├── Standard Instrument → Direct Rule Loading
│   └── Dynamic Instrument → Discriminant Variable Check
│       ├── C2 → C2 Rule Variant
│       ├── C2T → C2T Rule Variant
│       └── Unknown → Default Variant
└── Validation Execution
    ├── Schema Building
    ├── Rule Application
    ├── Error Detection
    └── Result Logging
```

### Flow Diagram Analysis

**Source**: `flowcharts/DataRouting.txt`

The system's data routing follows this visual workflow:

1. **REDCap Data Input**: All data enters through the REDCap API
2. **Record Type Detection**: Analysis of record characteristics
3. **Form Classification**: Routing to appropriate instrument processors
4. **Rule Loading**: Dynamic loading of instrument-specific rules
5. **Tool Detection**: Special handling for instruments like C2/C2T
6. **Schema Validation**: Application of resolved validation rules
7. **Rule Found Check**: Verification that appropriate rules exist
8. **Validation Execution**: Actual validation processing
9. **Result Handling**: Processing of validation outcomes

### Routing Assumptions and Requirements

#### System Assumptions

1. **Data Integrity**: REDCap data includes required metadata fields (ptid, redcap_event_name, packet)
2. **Rule Availability**: Validation rules exist for all configured instruments and packet types
3. **Completion Status**: Instrument completion variables are properly maintained
4. **Event Configuration**: REDCap events are properly configured and accessible
5. **Network Connectivity**: Stable connection to REDCap servers

#### Configuration Requirements

1. **Environment Variables**: All required paths and credentials properly configured
2. **Rule Files**: JSON rule files exist in correct directory structure
3. **Instrument Mapping**: Complete mapping between instruments and rule files
4. **Packet Paths**: Valid paths configured for all packet types (I, I4, F)
5. **Dynamic Instruments**: Proper configuration of discriminant variables and mappings

#### Performance Requirements

1. **Memory Management**: Efficient handling of large datasets
2. **Processing Speed**: Reasonable processing times for typical data volumes
3. **Error Recovery**: Robust handling of transient failures
4. **Resource Utilization**: Optimal use of system resources

## Integration Points and Dependencies

### Configuration Integration

**Primary Integration**: `src/pipeline/config_manager.py`

The routing system relies heavily on configuration for:

- **Processing Mode**: Determines high-level routing strategy
- **Instrument Lists**: Defines which instruments to process
- **Rule Mappings**: Maps instruments to validation rule files
- **Packet Paths**: Specifies directories for packet-specific rules
- **Dynamic Configuration**: Manages variable-based rule selection

### Data Fetching Integration

**Primary Integration**: `src/pipeline/core/fetcher.py`

The routing system receives data from the fetching system and:

- **Applies Mode Filters**: Uses configuration to determine data filtering
- **Preserves Context**: Maintains execution context through pipeline stages
- **Handles Transformations**: Applies mode-specific data transformations

### Validation Engine Integration

**Primary Integration**: `nacc_form_validator/quality_check.py`

The routing system provides the validation engine with:

- **Resolved Rules**: Hierarchically resolved validation rules
- **Schema Objects**: Properly formatted Cerberus schemas
- **Context Information**: Record metadata for validation context

### Logging and Monitoring Integration

**Primary Integration**: `src/pipeline/logging_config.py`

The routing system integrates with logging for:

- **Decision Tracking**: Logging of routing decisions and rule selection
- **Performance Monitoring**: Tracking of processing times and resource usage
- **Error Reporting**: Comprehensive error logging with context
- **Audit Trails**: Complete audit trails for compliance and debugging

## Operations Manual

### Standard Routing Operations

#### Complete Visits Processing

1. **Initiate Processing**: System starts with complete_visits mode
2. **Data Extraction**: Fetch data with complete visits filter logic
3. **Visit Identification**: Scan data for complete participant-event combinations
4. **Data Filtering**: Restrict processing to identified complete visits
5. **Validation Routing**: Route filtered data through validation pipeline

#### Complete Instruments Processing

1. **Initiate Processing**: System starts with complete_instruments mode
2. **Data Extraction**: Fetch data without visit-level filtering
3. **Instrument Assessment**: Evaluate completion status for each instrument
4. **Data Nullification**: Nullify incomplete instrument data
5. **Validation Routing**: Route processed data through validation pipeline

### Troubleshooting Common Routing Issues

#### Missing Packet Information

**Symptom**: Records fail to route to validation rules
**Cause**: Missing or invalid packet values in REDCap data
**Solution**: 
1. Verify packet field is included in REDCap export
2. Check packet values are valid (I, I4, F)
3. Ensure packet field is properly populated in REDCap

#### Dynamic Routing Failures

**Symptom**: C2/C2T instruments fail validation with "no rules found" errors
**Cause**: Missing discriminant variable values or rule variants
**Solution**:
1. Verify discriminant variable (loc_c2_or_c2t) is included in export
2. Check discriminant values match configured variants (C2, C2T)
3. Ensure rule files exist for all configured variants

#### Rule Loading Errors

**Symptom**: Instruments fail with "rule file not found" errors
**Cause**: Missing rule files or incorrect path configuration
**Solution**:
1. Verify rule files exist in configured packet directories
2. Check file naming matches instrument mapping configuration
3. Validate JSON syntax in rule files

### Performance Optimization

#### Large Dataset Handling

1. **Memory Management**: Monitor memory usage during large dataset processing
2. **Batch Processing**: Consider implementing batch processing for very large datasets
3. **Caching Strategy**: Optimize rule loading and caching for repeated processing
4. **Resource Monitoring**: Track CPU and memory usage during processing

#### Processing Speed Optimization

1. **Rule Preloading**: Load rules once and cache for multiple records
2. **Vectorized Operations**: Use pandas vectorized operations where possible
3. **Parallel Processing**: Consider parallel processing for independent instruments
4. **Database Optimization**: Optimize REDCap queries for faster data extraction

## Future Enhancements

### Planned Improvements

1. **Enhanced Custom Mode**: Complete implementation of flexible custom processing
2. **Real-Time Routing**: Support for real-time data processing and routing
3. **Advanced Analytics**: Integration with analytics for routing optimization
4. **Multi-Site Support**: Enhanced support for multi-site data routing
5. **API Enhancements**: RESTful API for programmatic routing control

### Research and Development

1. **Machine Learning Integration**: ML-based rule suggestion and optimization
2. **Automated Rule Generation**: Automatic generation of validation rules
3. **Performance Analytics**: Advanced performance monitoring and optimization
4. **Cloud Integration**: Cloud-based processing and routing capabilities

## Conclusion

The Data Routing and Workflow System represents a sophisticated approach to data processing orchestration in the UDSv4 QC Validator. Through its multi-stage pipeline architecture, hierarchical rule resolution, and intelligent routing mechanisms, the system provides robust, scalable, and maintainable data processing capabilities.

The system's design enables flexible processing modes while maintaining strict data integrity and validation standards. Its modular architecture supports future enhancements and customizations while preserving backward compatibility and operational reliability.

## Related Documentation

- [Configuration Management](configuration-management.md) - System configuration and instrument mapping
- [Data Fetching System](data-fetching-system.md) - Data extraction and ETL pipeline
- [QC Validation Engine](qc-validation-engine.md) - Quality control validation mechanisms *(To be created)*
- [Logging and Monitoring](logging-monitoring.md) - System monitoring and audit trails *(To be created)*
- [Output Management and Reporting](output-reporting.md) - Report generation and output management *(To be created)*
