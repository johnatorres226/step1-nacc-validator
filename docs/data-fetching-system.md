# Data Fetching System

## Overview

The Data Fetching System is a modern, robust ETL (Extract, Transform, Load) pipeline designed for retrieving and processing REDCap data for the UDSv4 Quality Control Validator. The system implements a clean, object-oriented architecture that follows a linear pipeline pattern: fetch → validate → transform → save. It provides comprehensive error handling, data validation, filtering capabilities, and performance optimization features.

## Architecture

### Design Philosophy

The system is built on the following principles:

1. **Linear Pipeline Pattern**: Clear separation of concerns with distinct stages
2. **Object-Oriented Design**: Modular components with single responsibilities
3. **Robust Error Handling**: Comprehensive error detection and recovery mechanisms
4. **Data Integrity**: Extensive validation at each pipeline stage
5. **Performance Optimization**: Efficient data processing and memory management
6. **Configuration-Driven**: Behavior controlled through centralized configuration

### Core Components

1. **RedcapETLPipeline**: Main orchestrator class that coordinates the entire ETL process
2. **RedcapApiClient**: Handles REDCap API communication with authentication and error handling
3. **DataValidator**: Performs data validation and quality checks
4. **DataTransformer**: Applies data transformations based on business rules
5. **DataSaver**: Manages data persistence with consistent naming conventions
6. **FilterLogicManager**: Determines appropriate REDCap filtering logic
7. **ETLContext**: Encapsulates execution context and metadata

## Data Structures

### ETLContext

The `ETLContext` class encapsulates execution metadata and configuration:

```python
@dataclass
class ETLContext:
    config: QCConfig
    run_date: str
    time_stamp: str
    output_path: Optional[Path] = None
```

**Purpose**: Provides consistent execution context across all pipeline components, ensuring proper timestamping and path management.

### ETLResult

The `ETLResult` class encapsulates pipeline execution results:

```python
@dataclass
class ETLResult:
    data: pd.DataFrame
    records_processed: int
    execution_time: float
    saved_files: List[Path]
```

**Purpose**: Provides structured access to pipeline outputs and execution metadata for monitoring and reporting.

### DataContract

The `DataContract` class defines expected data structure and validation rules:

```python
class DataContract:
    REQUIRED_FIELDS = ['ptid', 'redcap_event_name']
    
    @staticmethod
    def validate_required_fields(df: pd.DataFrame) -> List[str]:
        # Validation logic
```

**Purpose**: Ensures data integrity by defining and enforcing required data structure contracts.

## REDCap API Integration

### RedcapApiClient

The `RedcapApiClient` class manages all REDCap API interactions:

#### Authentication and Session Management

```python
class RedcapApiClient:
    def __init__(self, config: QCConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json'
        })
```

#### API Request Handling

The client implements robust error handling for various failure scenarios:

1. **Timeout Handling**: Configurable timeout with clear error messages
2. **Network Errors**: Graceful handling of connection issues
3. **HTTP Errors**: Proper handling of HTTP status codes
4. **JSON Parsing**: Validation of API response format
5. **Empty Responses**: Appropriate handling of empty result sets

#### Security Considerations

- **Token Management**: Secure handling of REDCap API tokens
- **Session Management**: Proper session initialization and cleanup
- **SSL/TLS**: Secure communication with REDCap servers
- **Error Sanitization**: Preventing sensitive data exposure in error messages

## API Payload Construction

### Payload Building Process

The `_build_api_payload` method constructs REDCap API requests with the following parameters:

```python
def _build_api_payload(self, instruments: List[str], filter_logic: Optional[str]) -> Dict[str, Any]:
    payload = {
        'token': self.config.api_token,
        'content': 'record',
        'format': 'json',
        'type': 'flat',
        'rawOrLabel': 'raw',
        'rawOrLabelHeaders': 'raw',
        'exportCheckboxLabel': 'false',
        'exportSurveyFields': 'false',
        'exportDataAccessGroups': 'false',
        'returnFormat': 'json',
    }
```

### Payload Parameters Explained

#### Core Parameters

- **token**: REDCap API authentication token from configuration
- **content**: Set to 'record' to export data records
- **format**: 'json' for structured data format
- **type**: 'flat' for flattened data structure suitable for analysis

#### Data Format Parameters

- **rawOrLabel**: 'raw' to export raw coded values rather than labels
- **rawOrLabelHeaders**: 'raw' to use variable names as column headers
- **exportCheckboxLabel**: 'false' to export checkbox values as 0/1 rather than labels
- **exportSurveyFields**: 'false' to exclude survey metadata fields
- **exportDataAccessGroups**: 'false' to exclude data access group information
- **returnFormat**: 'json' for JSON response format

#### Conditional Parameters

- **forms**: Comma-separated list of instruments/forms to export
- **events**: Comma-separated list of REDCap events to include
- **filterLogic**: REDCap filter logic for targeted data retrieval

### Instrument Selection Logic

The system determines which instruments to include in the API request:

1. **Base Instruments**: Starts with configured instruments from `config.instruments`
2. **Quality Control Form**: Adds 'quality_control_check' form when filtering is applied
3. **Dynamic Expansion**: May include additional forms based on processing requirements

### Filter Logic Application

The system applies filter logic based on configuration mode:

- **complete_events**: Fetches complete events that haven't been QC'd
- **complete_visits**: Same as complete_events (alias)
- **complete_instruments**: Uses QC status filter only
- **custom**: Conditional filtering based on `include_qced` setting
- **none**: No filtering (fetches all records)

## Data Validation and Processing

### DataValidator Class

The `DataValidator` handles data validation and initial processing:

#### Validation Process

1. **Empty Data Check**: Validates that data was returned from REDCap
2. **DataFrame Conversion**: Converts JSON response to pandas DataFrame
3. **Column Mapping**: Maps REDCap fields to expected column names
4. **Required Field Validation**: Ensures critical fields are present
5. **Data Type Validation**: Validates data types and formats

#### Column Mapping Logic

```python
def _handle_column_mapping(df: pd.DataFrame) -> pd.DataFrame:
    # Map record_id to ptid if needed
    if 'record_id' in df.columns and 'ptid' not in df.columns:
        df = df.rename(columns={'record_id': 'ptid'})
        
    # Validate critical fields
    if 'ptid' not in df.columns:
        raise ValueError("Critical error: 'ptid' column missing from REDCap data")
```

#### Error Handling

The validator implements strict error handling:

- **Missing Critical Fields**: Immediate failure if required fields are absent
- **Data Type Mismatches**: Clear error messages for type validation failures
- **Structural Issues**: Detection and reporting of data structure problems

## Data Transformation

### DataTransformer Class

The `DataTransformer` applies business logic transformations to the data:

#### Transformation Types

1. **Instrument Subset Transformation**: Nullifies data for incomplete instruments
2. **PTID Filtering**: Filters data for specific participant IDs
3. **Basic Filtering**: Applies general filtering rules

#### Instrument Subset Logic

For the 'complete_instruments' mode, the transformer:

1. **Loads Validation Rules**: Retrieves rule sets for each instrument
2. **Maps Variables**: Creates instrument-to-variables mapping
3. **Checks Completion Status**: Examines completion variables for each instrument
4. **Nullifies Incomplete Data**: Sets incomplete instrument data to null values

```python
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

#### PTID Filtering

When a PTID list is provided in configuration:

1. **Validation**: Ensures PTID column exists in data
2. **Type Conversion**: Converts PTID list to string format for matching
3. **Filtering**: Retains only records matching the PTID list
4. **Logging**: Reports filtering statistics

## Filter Logic Management

### FilterLogicManager Class

The `FilterLogicManager` determines appropriate REDCap filter logic based on configuration:

#### Mode-Based Logic Selection

```python
def get_filter_logic(config: QCConfig) -> Optional[str]:
    mode_filters = {
        'complete_events': complete_events_with_incomplete_qc_filter_logic,
        'complete_visits': complete_events_with_incomplete_qc_filter_logic,
        'complete_instruments': qc_filterer_logic,
        'none': None
    }
```

#### Filter Logic Rationale

Each filter logic serves a specific purpose:

- **complete_events_with_incomplete_qc_filter_logic**: Selects fully completed visits that haven't undergone quality control review
- **qc_filterer_logic**: Focuses on records requiring quality control attention
- **None**: Retrieves all available data without filtering

### Filter Logic Construction

The filter logic strings are constructed in the configuration manager:

#### Complete Events Filter

```python
complete_events_with_incomplete_qc_filter_logic = (
    "(" +
    " and ".join(f"[{inst}]=2" for inst in complete_instruments_vars) +
    ") and ([qc_status_complete] = 0 or [qc_status_complete] = \"\")"
)
```

This filter ensures:

1. All instruments are marked as complete (status = 2)
2. Quality control has not been completed (status = 0 or empty)

#### QC Status Filter

```python
qc_filterer_logic = '[qc_status_complete] = 0 or [qc_status_complete] = ""'
```

This filter targets records needing quality control review.

## Data Persistence

### DataSaver Class

The `DataSaver` manages data persistence with consistent naming and organization:

#### File Organization

1. **Directory Structure**: Creates 'Data_Fetched' subdirectory under output path
2. **Naming Convention**: Uses timestamp-based naming for uniqueness
3. **Format**: Saves data in CSV format for broad compatibility

#### Naming Convention

```python
filename = f"{filename_prefix}_{self.context.run_date}_{self.context.time_stamp}.csv"
```

Example: `ETL_ProcessedData_02SEP2025_143022.csv`

#### File Management

- **Directory Creation**: Automatically creates necessary directories
- **Conflict Resolution**: Timestamp-based naming prevents file conflicts
- **Path Tracking**: Maintains list of saved files for reporting
- **Error Handling**: Graceful handling of file system errors

## ETL Pipeline Orchestration

### RedcapETLPipeline Class

The main `RedcapETLPipeline` class orchestrates the entire ETL process:

#### Pipeline Execution Flow

```python
def run(self, output_path=None, date_tag=None, time_tag=None) -> ETLResult:
    # 1. Initialize context and components
    self._initialize_components(output_path, date_tag, time_tag)
    
    # 2. Fetch data from REDCap
    raw_data = self._fetch_data()
    
    # 3. Validate and process data
    validated_data = self._validate_data(raw_data)
    
    # 4. Transform data based on configuration
    transformed_data = self._transform_data(validated_data)
    
    # 5. Save processed data
    saved_files = self._save_data(transformed_data)
    
    return ETLResult(...)
```

#### Component Initialization

The pipeline initializes all components with proper context:

1. **ETLContext**: Creates execution context with timestamps
2. **RedcapApiClient**: Initializes API client with configuration
3. **DataTransformer**: Creates transformer with context
4. **DataSaver**: Sets up data persistence handler

#### Error Handling Strategy

The pipeline implements comprehensive error handling:

1. **Stage Isolation**: Errors in one stage don't corrupt others
2. **Context Preservation**: Error messages include execution context
3. **Resource Cleanup**: Proper cleanup of resources on failure
4. **Logging Integration**: Detailed error logging for debugging

## Fallback Mechanisms

### Data Fetch Fallback

The system implements intelligent fallback when initial data fetch fails:

```python
try:
    raw_data = self.api_client.fetch_data(payload)
    if not raw_data and filter_logic:
        logger.info("Attempting fallback fetch without filters")
        fallback_payload = self._build_api_payload(
            [inst for inst in fetch_instruments if inst != "quality_control_check"],
            None
        )
        raw_data = self.api_client.fetch_data(fallback_payload)
except Exception as e:
    logger.error(f"Data fetch failed: {str(e)}")
    raise
```

#### Fallback Logic

1. **Primary Attempt**: Uses full configuration with filters
2. **Fallback Trigger**: Activates when primary attempt returns no data
3. **Filter Removal**: Removes filtering logic for broader data retrieval
4. **Form Adjustment**: Removes quality control form from fallback request
5. **Success Reporting**: Logs successful fallback operations

## Performance Considerations

### Memory Management

1. **DataFrame Operations**: Efficient pandas operations for large datasets
2. **Memory Monitoring**: Tracking of memory usage during processing
3. **Garbage Collection**: Proper cleanup of large data structures
4. **Streaming**: Potential for streaming large datasets

### Network Optimization

1. **Session Reuse**: HTTP session reuse for multiple requests
2. **Timeout Configuration**: Configurable timeouts for different network conditions
3. **Retry Logic**: Built-in retry mechanisms for transient failures
4. **Compression**: Support for compressed data transfer

### Processing Efficiency

1. **Vectorized Operations**: Using pandas vectorized operations where possible
2. **Concurrent Processing**: Multi-threading support for parallel processing
3. **Lazy Loading**: Deferred loading of large rule sets
4. **Caching**: Intelligent caching of frequently accessed data

## Integration with Configuration System

### Configuration Dependencies

The data fetching system relies heavily on the configuration system:

#### Core Configuration Elements

1. **API Credentials**: REDCap API token and URL
2. **Instrument Configuration**: List of instruments and their mappings
3. **Event Configuration**: REDCap events to process
4. **Processing Mode**: Determines transformation and filtering behavior
5. **Output Configuration**: File paths and naming conventions

#### Dynamic Configuration

The system adapts behavior based on configuration:

1. **Mode-Based Processing**: Different processing logic for different modes
2. **Filter Selection**: Automatic filter logic selection based on mode
3. **Instrument Inclusion**: Dynamic instrument list based on requirements
4. **Path Resolution**: Automatic path resolution and validation

### Configuration Validation Impact

Configuration validation directly affects data fetching:

1. **API Connectivity**: Validates API credentials before attempting requests
2. **Path Validation**: Ensures output paths are accessible
3. **Instrument Validation**: Verifies instrument-to-rule mappings
4. **Performance Limits**: Validates performance-related settings

## Logging and Monitoring

### Logging Strategy

The system implements comprehensive logging:

#### Log Levels

1. **DEBUG**: Detailed execution information for troubleshooting
2. **INFO**: General operational information and progress updates
3. **WARNING**: Non-critical issues that don't prevent operation
4. **ERROR**: Critical errors that may cause operation failure

#### Log Content

1. **Operation Progress**: Start/completion of major operations
2. **Data Statistics**: Record counts, processing times, file sizes
3. **Configuration Details**: Applied settings and parameters
4. **Error Details**: Comprehensive error information with context

#### Performance Metrics

1. **Execution Time**: Total pipeline execution time
2. **Record Counts**: Input/output record counts at each stage
3. **Memory Usage**: Peak memory consumption during processing
4. **API Performance**: Request/response times and success rates

## Error Handling and Recovery

### Error Categories

The system handles several categories of errors:

#### Network Errors

1. **Connection Failures**: Network connectivity issues
2. **Timeout Errors**: Request timeout scenarios
3. **Authentication Errors**: Invalid or expired API credentials
4. **Rate Limiting**: REDCap API rate limit enforcement

#### Data Errors

1. **Empty Results**: No data returned from REDCap
2. **Invalid Format**: Malformed or unexpected data structure
3. **Missing Fields**: Required fields absent from data
4. **Data Type Issues**: Unexpected data types or formats

#### System Errors

1. **File System Errors**: Path or permission issues
2. **Memory Errors**: Insufficient memory for processing
3. **Configuration Errors**: Invalid or missing configuration
4. **Processing Errors**: Errors in data transformation logic

### Recovery Strategies

#### Automatic Recovery

1. **Retry Logic**: Automatic retry for transient failures
2. **Fallback Processing**: Alternative processing paths for common failures
3. **Graceful Degradation**: Continued operation with reduced functionality

#### Manual Recovery

1. **Error Reporting**: Detailed error information for manual intervention
2. **Partial Results**: Saving partial results when possible
3. **Resume Capability**: Ability to resume from failure points

## Testing and Validation

### Unit Testing

Each component is designed for independent testing:

1. **Mock API Responses**: Testing with simulated REDCap responses
2. **Data Validation Testing**: Comprehensive validation rule testing
3. **Transformation Testing**: Testing of data transformation logic
4. **Error Scenario Testing**: Testing error handling paths

### Integration Testing

1. **End-to-End Testing**: Complete pipeline testing with test data
2. **Configuration Testing**: Testing with various configuration scenarios
3. **Performance Testing**: Load and stress testing with large datasets
4. **Error Recovery Testing**: Testing fallback and recovery mechanisms

### Data Quality Validation

1. **Schema Validation**: Ensuring output data matches expected schema
2. **Completeness Checks**: Verifying all expected data is present
3. **Consistency Validation**: Checking data consistency across pipeline stages
4. **Business Rule Validation**: Ensuring business logic is correctly applied

## Best Practices

### Development Guidelines

1. **Error Handling**: Always implement comprehensive error handling
2. **Logging**: Log all significant operations and errors
3. **Configuration**: Use configuration-driven behavior rather than hard-coding
4. **Testing**: Write tests for all major functionality

### Operational Guidelines

1. **Monitoring**: Monitor pipeline execution and performance
2. **Backup**: Maintain backups of critical configuration and data
3. **Documentation**: Keep documentation current with code changes
4. **Security**: Protect API credentials and sensitive data

### Performance Guidelines

1. **Resource Management**: Monitor and optimize resource usage
2. **Scalability**: Design for growth in data volume
3. **Efficiency**: Use efficient algorithms and data structures
4. **Caching**: Implement appropriate caching strategies

## Troubleshooting Guide

### Common Issues

#### No Data Retrieved

1. Check REDCap API credentials
2. Verify filter logic syntax
3. Confirm instrument and event configuration
4. Check REDCap server availability

#### Validation Errors

1. Verify required fields are present in REDCap export
2. Check data type consistency
3. Validate column mapping logic
4. Review REDCap export configuration

#### Performance Issues

1. Monitor memory usage during processing
2. Check network connectivity and latency
3. Review timeout configuration
4. Consider data volume and processing limits

#### File System Errors

1. Verify output path permissions
2. Check available disk space
3. Validate path configuration
4. Review file naming conventions

### Diagnostic Procedures

#### Configuration Validation

```python
from src.pipeline.config_manager import get_config

config = get_config()
errors = config.validate()
if errors:
    for error in errors:
        print(f"Configuration error: {error}")
```

#### API Connectivity Testing

```python
from src.pipeline.core.fetcher import RedcapApiClient

client = RedcapApiClient(config)
test_payload = {
    'token': config.api_token,
    'content': 'project',
    'format': 'json'
}
response = client.fetch_data(test_payload)
```

#### Pipeline Testing

```python
from src.pipeline.core.fetcher import RedcapETLPipeline

pipeline = RedcapETLPipeline(config)
result = pipeline.run()
print(f"Processed {result.records_processed} records in {result.execution_time:.2f} seconds")
```

## Future Enhancements

### Planned Improvements

1. **Streaming Processing**: Support for processing very large datasets
2. **Advanced Caching**: Intelligent caching of processed data
3. **Parallel Processing**: Enhanced multi-threading support
4. **Real-time Monitoring**: Live monitoring and alerting capabilities

### Extensibility Points

1. **Custom Transformers**: Plugin architecture for custom data transformations
2. **Output Formats**: Support for additional output formats
3. **Data Sources**: Support for additional data sources beyond REDCap
4. **Validation Rules**: Dynamic validation rule loading and application
