# Data Fetching System

## Overview

The Data Fetching System retrieves pre-filtered quality control data from REDCap using report-based exports. Rather than fetching full datasets and applying complex ETL transformations, the system leverages REDCap's built-in report filtering capabilities to obtain ready-to-validate data directly. The architecture follows a streamlined pattern: fetch report → validate fields → filter PTIDs → save. This approach eliminates the need for instrument selection logic, complex filtering operations, and data transformations, resulting in faster execution and simpler maintenance.

## Architecture

### Design Philosophy

The system is built on the following principles:

1. **Simplicity First**: Leverage REDCap's filtering to eliminate complex transformation logic
2. **Pre-filtered Data**: Reports are configured in REDCap to provide QC-ready data
3. **Minimal Processing**: Focus on validation and PTID filtering only
4. **Robust Error Handling**: Comprehensive error detection and clear messaging
5. **Data Integrity**: Field validation ensures required data is present
6. **Configuration-Driven**: Report selection and behavior controlled through configuration

### Core Components

1. **fetch_report_data()**: Main function that orchestrates report data retrieval
2. **_build_report_payload()**: Constructs REDCap API request for report export
3. **_post_api()**: Handles REDCap API communication with error handling
4. **_validate_and_map()**: Validates required fields and maps record_id to ptid
5. **_apply_ptid_filter()**: Filters data for specific participant IDs when configured

## Data Structures

### Configuration Requirements

The system requires the following configuration values:

```python
config.report_id      # REDCap report ID (required)
config.api_url       # REDCap API endpoint URL
config.api_token     # REDCap API authentication token
config.timeout       # API request timeout in seconds
config.ptid_list     # Optional list of PTIDs to filter (None = all)
```

### Required Data Fields

After fetching, the system validates presence of:

```python
REQUIRED_FIELDS = ["ptid", "redcap_event_name"]
```

These fields are essential for downstream QC validation processes.

## REDCap Report-Based Export

### fetch_report_data() Function

The `fetch_report_data()` function is the primary entry point for data retrieval:

```python
def fetch_report_data(
    config: QCConfig,
    output_path: Path | None = None,
    date_tag: str | None = None,
    time_tag: str | None = None,
) -> tuple[pd.DataFrame, int]:
    """Fetch data from a pre-configured REDCap report.
    
    Returns (dataframe, records_processed).
    """
```

#### Execution Flow

1. **Validation**: Ensures `report_id` is configured
2. **Payload Construction**: Builds REDCap API report export request
3. **API Request**: Posts to REDCap and receives JSON data
4. **Data Validation**: Validates required fields and maps columns
5. **PTID Filtering**: Applies participant ID filtering if configured
6. **Optional Save**: Saves fetched data to CSV for audit trail
7. **Return**: Returns DataFrame and record count

### _build_report_payload() Function

Constructs the REDCap API payload for report export:

```python
def _build_report_payload(config: QCConfig) -> dict[str, Any]:
    """Build the REDCap API POST payload for report export."""
    return {
        "token": config.api_token,
        "content": "report",               # Export report content type
        "report_id": config.report_id,     # Specific report to export
        "format": "json",                  # JSON response format
        "rawOrLabel": "raw",               # Use raw coded values
        "rawOrLabelHeaders": "raw",        # Use variable names as headers
        "exportCheckboxLabel": "false",    # Export checkbox as 0/1
        "returnFormat": "json",            # JSON return format
    }
```

#### Payload Parameters Explained

- **content**: Set to `"report"` to export a pre-configured REDCap report
- **report_id**: The numeric ID of the report configured in REDCap
- **format**: `"json"` for structured data format
- **rawOrLabel**: `"raw"` exports coded values (1, 2, etc.) instead of labels
- **rawOrLabelHeaders**: `"raw"` uses variable names instead of field labels
- **exportCheckboxLabel**: `"false"` returns checkbox values as 0/1 rather than labels
- **returnFormat**: `"json"` specifies JSON response format

### API Communication: _post_api() Function

Handles the actual HTTP request to REDCap:

```python
def _post_api(config: QCConfig, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """POST to REDCap and return parsed JSON list."""
    try:
        resp = requests.post(config.api_url, data=payload, timeout=config.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data if data else []
    except requests.exceptions.Timeout:
        raise RuntimeError(f"API request timed out after {config.timeout}s")
    except requests.exceptions.RequestException as exc:
        text = getattr(getattr(exc, "response", None), "text", None)
        raise RuntimeError(f"REDCap API request failed: {text or exc!s}")
    except (ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to parse JSON response: {exc!s}")
```

#### Error Handling

The API client handles several error scenarios:

1. **Timeout Errors**: Clear message when request exceeds configured timeout
2. **Network Errors**: Connection failures and HTTP errors
3. **Authentication Errors**: Invalid or missing API token
4. **JSON Parsing Errors**: Malformed responses from REDCap
5. **Empty Responses**: Graceful handling when report returns no data

#### Security Considerations

- **Token Security**: API token is passed securely in POST data
- **SSL/TLS**: HTTPS communication with REDCap servers
- **Error Sanitization**: API responses are not logged to prevent token exposure
- **Session Management**: Each request is independent, no persistent sessions

## Data Validation and Column Mapping

### _validate_and_map() Function

After receiving data from REDCap, the system validates structure and maps columns:

```python
def _validate_and_map(raw: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert raw records to DataFrame, rename record_id → ptid, validate."""
    df = pd.DataFrame(raw)
    
    # Map record_id to ptid for consistency
    if "record_id" in df.columns and "ptid" not in df.columns:
        df = df.rename(columns={"record_id": "ptid"})
    
    # Validate required fields
    missing = [f for f in REQUIRED_FIELDS if f not in df.columns]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    
    return df
```

#### Validation Process

1. **DataFrame Conversion**: Converts JSON response to pandas DataFrame
2. **Column Mapping**: Maps `record_id` to `ptid` if needed (REDCap standard field)
3. **Required Field Check**: Ensures `ptid` and `redcap_event_name` are present
4. **Error Reporting**: Provides clear error message listing missing fields

#### Column Mapping Logic

The system expects participant ID to be in a `ptid` column, but REDCap exports may use `record_id`. The validation function automatically handles this mapping to ensure consistency with downstream validation processes.

### Error Handling

The validator implements strict error handling:

- **Missing Critical Fields**: Immediate failure with clear error message
- **Empty DataFrame**: Handled gracefully, returns empty DataFrame
- **Malformed Data**: JSON parsing errors are caught by `_post_api()`

## PTID Filtering

### _apply_ptid_filter() Function

When configuration specifies a list of participant IDs to process, the system filters data accordingly:

```python
def _apply_ptid_filter(df: pd.DataFrame, config: QCConfig) -> pd.DataFrame:
    """Filter to specific PTIDs if config.ptid_list is set."""
    if not config.ptid_list or "ptid" not in df.columns:
        return df
    
    before = len(df)
    targets = [str(p) for p in config.ptid_list]
    df = df[df["ptid"].isin(targets)].reset_index(drop=True)
    
    logger.info("PTID filter: %d → %d records", before, len(df))
    return df
```

#### Filtering Process

1. **Check Configuration**: Only activates if `config.ptid_list` is set
2. **Column Validation**: Verifies `ptid` column exists in data
3. **Type Conversion**: Converts PTIDs to strings for consistent comparison
4. **Filtering**: Retains only records matching the PTID list
5. **Reset Index**: Resets DataFrame index after filtering
6. **Logging**: Reports before/after record counts

#### Use Cases

PTID filtering is useful for:

- **Targeted QC**: Processing specific participants for review
- **Testing**: Validating changes with a subset of data
- **Re-processing**: Re-running QC for specific participants
- **Troubleshooting**: Isolating problematic records for investigation

### Configuration

PTID filtering is configured via:

```python
# config.yaml or environment
PTID_LIST = ["001", "002", "003"]
```

Or left empty/None to process all records from the report.

## Data Persistence

### Optional Audit Trail Saving

The `fetch_report_data()` function optionally saves fetched data to CSV:

```python
if output_path and not df.empty:
    dt = date_tag or ""
    tt = time_tag or ""
    out_dir = Path(output_path) / "Data_Fetched"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"Report_Data_{config.report_id}_{dt}_{tt}.csv"
    df.to_csv(csv_path, index=False)
    logger.debug("Saved report data: %s (%d records)", csv_path, len(df))
```

#### File Organization

1. **Directory Structure**: Creates `Data_Fetched` subdirectory under output path
2. **Naming Convention**: `Report_Data_{report_id}_{date}_{time}.csv`
3. **Format**: CSV for broad compatibility and human readability

#### Naming Convention

Example: `Report_Data_12345_14JAN2026_183627.csv`

Components:
- `Report_Data`: Fixed prefix identifying report-based fetch
- `12345`: The REDCap report ID
- `14JAN2026`: Date tag (DDMMMYYYY format, uppercase)
- `183627`: Time tag (HHMMSS format)

#### Purpose

The saved data serves as:
- **Audit Trail**: Record of exactly what data was fetched
- **Debugging**: Compare fetched data to validation results
- **Reproducibility**: Re-run validation with same input data
- **Compliance**: Documentation trail for quality control processes

## REDCap Report Configuration

### Report Setup

The system requires a pre-configured report in REDCap with:

1. **Filtering Logic**: Report should include appropriate filters (e.g., complete events without QC)
2. **Fields Selection**: Include all variables needed for validation
3. **Event Selection**: Include relevant REDCap events
4. **Sort Order**: Optional sorting for consistent data ordering

### Report ID Configuration

Set the report ID in configuration:

```yaml
# config.yaml
REDCAP_REPORT_ID: "12345"
```

Or via environment variable:

```bash
export REDCAP_REPORT_ID=12345
```

### Advantages of Report-Based Fetching

1. **Simplified Code**: No complex filtering logic in application
2. **REDCap Native**: Leverage REDCap's tested filtering capabilities
3. **Performance**: REDCap filters data at source, reducing transfer size
4. **Maintainability**: Update filters in REDCap without code changes
5. **Flexibility**: Different reports for different QC scenarios
6. **Testing**: Easy to test with different report configurations

## Performance Considerations

### Network Optimization

1. **Single Request**: One API call to fetch pre-filtered report data
2. **Timeout Configuration**: Configurable timeout via `config.timeout`
3. **Efficient Payload**: Minimal parameters in API request
4. **HTTP POST**: Uses POST method for secure, efficient data transfer

### Memory Management

1. **DataFrame Operations**: Efficient pandas operations for data handling
2. **Minimal Processing**: No complex transformations reduce memory footprint
3. **Streaming**: Data fetched in single batch from report
4. **Garbage Collection**: pandas automatically manages DataFrame memory

### Processing Efficiency

1. **Pre-filtered at Source**: REDCap filters data before transfer
2. **Direct DataFrame**: Immediate conversion from JSON to DataFrame
3. **Vectorized Operations**: pandas vectorized filtering for PTID operations
4. **No Complex Logic**: Elimination of ETL transformations improves speed

### Performance Metrics

Typical performance characteristics:

- **API Request Time**: 2-10 seconds (depends on data size and network)
- **Validation Time**: <1 second for typical datasets
- **PTID Filtering**: <1 second (vectorized operations)
- **Total Fetch Time**: Usually <15 seconds for reports with hundreds of records

## Integration with Configuration System

### Required Configuration Values

The data fetching system requires the following configuration:

```python
# Core REDCap API Settings
config.api_url        # REDCap API endpoint URL
config.api_token      # API authentication token
config.timeout        # Request timeout (seconds, default: 300)

# Report Configuration  
config.report_id      # REDCap report ID to fetch

# Optional Filtering
config.ptid_list      # List of PTIDs to filter (None = all records)

# Output Configuration
config.output_path    # Base output directory for saved files
config.mode          # Processing mode (used in output directory naming)
config.instruments   # List of instruments (used during validation)
```

### Configuration Validation

Before fetching data, the system validates:

1. **API Credentials**: `api_url` and `api_token` must be set
2. **Report ID**: `report_id` must be configured
3. **Timeout**: Must be positive integer (default: 300 seconds)
4. **Output Path**: Must be valid directory path if specified

### Dynamic Behavior

Configuration affects fetching behavior:

1. **PTID Filter**: If `ptid_list` is set, data is filtered to those PTIDs
2. **Output Path**: If provided, fetched data is saved to CSV
3. **Timeout**: Controls how long to wait for REDCap response
4. **Mode**: Used in output directory naming for organization

## Logging and Monitoring

### Logging Strategy

The system implements focused logging at key points:

#### Log Levels

1. **DEBUG**: Detailed information (saved file paths, timing details)
2. **INFO**: Operational progress (fetch start, record counts, completion)
3. **WARNING**: Non-critical issues (empty results, missing optional fields)
4. **ERROR**: Critical failures (API errors, validation failures)

#### Key Log Messages

**Fetch Start:**
```
INFO: Fetching data from REDCap report 12345
```

**Fetch Complete:**
```
INFO: Fetched 247 records from report 12345 in 8.3s
```

**PTID Filtering:**
```
INFO: PTID filter: 247 → 15 records
```

**Empty Results:**
```
WARNING: No data returned from REDCap report 12345
```

**Validation Errors:**
```
ERROR: Missing required fields: ptid, redcap_event_name
```

**API Errors:**
```
ERROR: REDCap API request failed: Invalid report ID
```

### Performance Metrics

The system tracks:

1. **Execution Time**: Total time for `fetch_report_data()` call
2. **Record Counts**: Number of records fetched and after filtering
3. **Report ID**: Which report was accessed
4. **File Saved**: Path to saved CSV (if applicable)

## Error Handling and Recovery

### Error Categories

#### Configuration Errors

1. **Missing Report ID**: `ValueError` if `report_id` not configured
2. **Missing API URL**: `ValueError` if `api_url` not configured
3. **Invalid Configuration**: Type errors for invalid config values

#### Network Errors

1. **Timeout**: `RuntimeError` after timeout expires (e.g., "API request timed out after 300s")
2. **Connection Failure**: `RuntimeError` for network connectivity issues
3. **HTTP Errors**: `RuntimeError` for non-200 HTTP status codes
4. **Authentication**: API token invalid or missing (REDCap returns error)

#### Data Errors

1. **Empty Results**: Returns empty DataFrame (logged as WARNING, not error)
2. **Invalid JSON**: `RuntimeError` for malformed REDCap responses
3. **Missing Required Fields**: `ValueError` listing missing fields (ptid, redcap_event_name)
4. **PTID Column Missing**: Gracefully skips PTID filtering if column absent

#### System Errors

1. **File System**: Errors creating output directories or saving CSV
2. **Memory**: pandas errors for extremely large datasets
3. **Permissions**: File write permission errors

### Error Messages

All errors include clear, actionable messages:

```python
# Configuration error
ValueError("REDCAP_REPORT_ID is not configured")

# Network error
RuntimeError("API request timed out after 300s")
RuntimeError("REDCap API request failed: Invalid report ID")

# Data validation error
ValueError("Missing required fields: ptid, redcap_event_name")

# JSON parsing error
RuntimeError("Failed to parse JSON response: Expecting value: line 1 column 1")
```

### Recovery Strategies

#### No Automatic Fallback

Unlike the old ETL system, report-based fetching does NOT implement automatic fallback mechanisms. If the report fetch fails, the system raises an error immediately.

**Rationale:**
- Report failures indicate configuration issues that need manual attention
- No ambiguity about which data is being processed
- Clearer error reporting for troubleshooting

#### Manual Recovery Steps

1. **Verify Configuration**: Check `report_id`, `api_url`, `api_token`
2. **Test Report**: Access report in REDCap web interface
3. **Check Network**: Verify connectivity to REDCap server
4. **Review REDCap Logs**: Check REDCap for API errors
5. **Adjust Timeout**: Increase timeout for large reports

## Testing and Validation

### Unit Testing

Each function is designed for independent testing:

1. **Mock API Responses**: Use `unittest.mock` to simulate REDCap responses
2. **Payload Validation**: Test `_build_report_payload()` output structure
3. **Data Validation**: Test `_validate_and_map()` with various data scenarios
4. **PTID Filtering**: Test `_apply_ptid_filter()` with different configurations
5. **Error Scenarios**: Test error handling paths with invalid inputs

### Integration Testing

1. **End-to-End Testing**: Complete fetch with test report
2. **Configuration Testing**: Test with various configuration scenarios
3. **Network Testing**: Test timeout and error handling
4. **Empty Data Testing**: Test behavior with reports returning no data

### Test Data Setup

Create test reports in REDCap with:

1. **Small Dataset**: Quick testing with 5-10 records
2. **Known Data**: Predictable values for validation
3. **Edge Cases**: Empty fields, special characters, boundary values
4. **PTID Coverage**: Records covering PTID filter test cases

### Example Test Structure

```python
from unittest.mock import patch, MagicMock
from src.pipeline.core.fetcher import fetch_report_data

def test_fetch_report_data():
    config = MagicMock()
    config.report_id = "12345"
    config.api_url = "https://redcap.example.org/api/"
    config.api_token = "test_token"
    config.timeout = 30
    config.ptid_list = None
    
    with patch('src.pipeline.core.fetcher._post_api') as mock_post:
        mock_post.return_value = [
            {"record_id": "001", "redcap_event_name": "baseline_arm_1"},
            {"record_id": "002", "redcap_event_name": "baseline_arm_1"},
        ]
        
        df, count = fetch_report_data(config)
        assert count == 2
        assert "ptid" in df.columns
```

## Best Practices

### REDCap Report Configuration

1. **Filter at Source**: Configure comprehensive filters in REDCap report
2. **Include All Fields**: Ensure report includes all variables needed for validation
3. **Test Reports**: Test reports in REDCap web interface before using in code
4. **Document Reports**: Document report purpose and filtering logic
5. **Version Control**: Track report configurations with documentation

### Development Guidelines

1. **Error Handling**: Always wrap fetch calls in try-except blocks
2. **Logging**: Use appropriate log levels for different scenarios
3. **Configuration**: Validate configuration before calling fetch functions
4. **Testing**: Test with mock data before using live REDCap API

### Operational Guidelines

1. **Monitor Performance**: Track fetch times and record counts
2. **Secure Credentials**: Protect API tokens (use environment variables)
3. **Backup Configuration**: Maintain backup of report configurations
4. **Documentation**: Document report IDs and their purposes
5. **Audit Trail**: Keep saved CSV files for troubleshooting

### Performance Guidelines

1. **Report Filters**: Use REDCap filters to minimize data transfer
2. **Timeout Settings**: Set appropriate timeout for report size
3. **PTID Lists**: Use PTID filtering for targeted processing
4. **Network**: Ensure stable network connection for large reports

## Troubleshooting Guide

### Common Issues

#### No Data Retrieved

**Error:** `WARNING: No data returned from REDCap report 12345`

**Possible Causes:**
1. Report filters too restrictive (no records match)
2. Report ID incorrect
3. Report deleted or disabled in REDCap
4. Insufficient API permissions

**Solutions:**
1. Check report in REDCap web interface
2. Verify report ID in configuration
3. Confirm report returns data in REDCap
4. Check API token permissions

#### Missing Report ID

**Error:** `ValueError: REDCAP_REPORT_ID is not configured`

**Solution:**
1. Set `REDCAP_REPORT_ID` in configuration file or environment variable
2. Verify configuration is loaded correctly

#### Validation Errors

**Error:** `ValueError: Missing required fields: ptid`

**Possible Causes:**
1. Report doesn't include required fields
2. REDCap uses `record_id` but mapping failed
3. Data structure unexpected

**Solutions:**
1. Add required fields to REDCap report
2. Check report includes `record_id` or `ptid` column
3. Verify report includes `redcap_event_name` field

#### API Timeout

**Error:** `RuntimeError: API request timed out after 300s`

**Possible Causes:**
1. Large report with many records
2. Slow network connection
3. REDCap server performance issues

**Solutions:**
1. Increase timeout in configuration: `TIMEOUT = 600`
2. Optimize report filters to reduce data size
3. Check REDCap server status
4. Test during off-peak hours

#### Authentication Errors

**Error:** `RuntimeError: REDCap API request failed: ERROR: You do not have permissions`

**Possible Causes:**
1. Invalid API token
2. Token expired or revoked
3. Insufficient API permissions
4. Report access restrictions

**Solutions:**
1. Verify API token is correct and active
2. Regenerate API token in REDCap
3. Check API export permissions in REDCap user settings
4. Verify report is accessible with that token

### Diagnostic Procedures

#### Test Configuration

```python
from src.pipeline.config.config_manager import get_config

config = get_config()
print(f"API URL: {config.api_url}")
print(f"Report ID: {config.report_id}")
print(f"Timeout: {config.timeout}")
print(f"PTID List: {config.ptid_list}")
```

#### Test API Connectivity

```python
from src.pipeline.core.fetcher import _post_api
from src.pipeline.config.config_manager import get_config

config = get_config()

# Test basic API access
test_payload = {
    'token': config.api_token,
    'content': 'project',
    'format': 'json'
}
try:
    result = _post_api(config, test_payload)
    print("API connection successful")
    print(f"Project: {result}")
except Exception as e:
    print(f"API connection failed: {e}")
```

#### Test Report Fetch

```python
from src.pipeline.core.fetcher import fetch_report_data
from src.pipeline.config.config_manager import get_config

config = get_config()

try:
    df, count = fetch_report_data(config)
    print(f"Successfully fetched {count} records")
    print(f"Columns: {df.columns.tolist()}")
    print(f"First row:\n{df.head(1)}")
except Exception as e:
    print(f"Fetch failed: {e}")
```

#### Verify Report in REDCap

1. Log into REDCap web interface
2. Navigate to **Data Exports, Reports, and Stats**
3. Find your report by ID
4. Click **View Report**
5. Verify data appears as expected
6. Check export functionality in REDCap UI

## Future Enhancements

### Potential Improvements

1. **Multiple Reports**: Support fetching from multiple reports in one run
2. **Report Caching**: Cache report results for faster re-runs during development
3. **Incremental Fetch**: Fetch only new/changed records since last run
4. **Retry Logic**: Implement automatic retry for transient network failures
5. **Progress Reporting**: Live progress updates for large report fetches
6. **Batch Processing**: Process large reports in batches to reduce memory usage

### Extensibility Points

1. **Custom Validation**: Plugin architecture for additional field validations
2. **Output Formats**: Support for Parquet, JSON, or other output formats
3. **Data Transformations**: Optional post-fetch transformation plugins
4. **Alternative Sources**: Support for fetching from other REDCap endpoints
5. **Audit Logging**: Enhanced audit trail with detailed operation logs

### Architecture Considerations

The current report-based architecture provides a solid foundation for enhancements:

- **Simplicity**: Easy to extend without complex dependencies
- **Modularity**: Functions are independent and testable
- **Configuration**: New features can be configuration-driven
- **Performance**: Minimal processing overhead allows for optimization
