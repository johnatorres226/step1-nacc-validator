# UDSv4 REDCap QC Validator - Project Overview

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Core Scripts and Functions](#core-scripts-and-functions)
- [Configuration System](#configuration-system)
- [Validation Pipeline](#validation-pipeline)
- [Database Integration](#database-integration)
- [CLI Interface](#cli-interface)
- [Windows Environment Setup](#windows-environment-setup)
- [Network Drive Configuration](#network-drive-configuration)
- [Output Structure](#output-structure)
- [Testing Framework](#testing-framework)
- [Usage Examples](#usage-examples)

## Overview

The UDSv4 REDCap QC Validator is a comprehensive quality control pipeline designed for validating NACC UDSv4 REDCap data. The system provides both basic validation capabilities and enhanced features with historical tracking, trend analysis, and pattern detection.

### Key Features
- **Multi-mode Validation**: Supports complete visits, incomplete visits, and custom validation modes
- **Schema-driven Validation**: Uses Cerberus and JSON Logic for flexible rule definitions
- **Historical Tracking**: SQLite database for error tracking and trend analysis
- **Network Drive Support**: Centralized database storage for team collaboration
- **Enhanced Reporting**: Comprehensive reports with error status and comparisons
- **Modern CLI**: Rich command-line interface with progress indicators and tables

## Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│     CLI Layer       │    │   Configuration     │    │    Validation       │
│   (src/cli/cli.py)  │◄──►│  (config_manager)   │◄──►│   (report_pipeline) │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
           │                           │                           │
           ▼                           ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│    Data Fetching    │    │   Rule Processing   │    │   Output Generation │
│     (fetcher.py)    │    │  (quality_check.py) │    │   (helpers.py)      │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
           │                           │                           │
           └─────────────────┬─────────────────────────────────────┘
                             ▼
                ┌─────────────────────┐
                │   Database Layer    │
                │   (datastore.py)    │
                └─────────────────────┘
```

## Core Scripts and Functions

### 1. Main Pipeline (`src/pipeline/report_pipeline.py`)

**Primary Functions:**
- `run_report_pipeline(config, enable_datastore)` - Main entry point for standard validation
- `run_enhanced_report_pipeline(config, enable_datastore)` - Enhanced validation with datastore integration
- `validate_data(data, instrument, rules, config)` - Core validation logic
- `process_instruments_etl(data, config)` - ETL processing for multiple instruments
- `export_results_to_csv(errors_df, output_path)` - Results export functionality

**Key Features:**
- Orchestrates the entire QC process
- Handles both basic and enhanced validation modes
- Manages database integration and error tracking
- Generates comprehensive output reports

### 2. Configuration Manager (`src/pipeline/config_manager.py`)

**Primary Functions:**
- `get_config(force_reload=False)` - Singleton configuration access
- `QCConfig.validate()` - Configuration validation
- `QCConfig.load_from_file()` - File-based configuration loading
- `QCConfig.save_to_file()` - Configuration persistence

**Configuration Parameters:**
- API credentials (REDCap URL and token)
- Validation modes and filters
- Output paths and logging levels
- Database and rule configurations

### 3. Data Fetcher (`src/pipeline/fetcher.py`)

**Primary Functions:**
- `fetch_etl_data(config)` - Main data fetching function
- `fetch_redcap_data(api_url, token)` - REDCap API integration
- `filter_data_by_mode(data, mode)` - Mode-specific data filtering
- `prepare_instrument_datasets(data)` - Dataset preparation for validation

### 4. Quality Check (`src/pipeline/quality_check.py`)

**Primary Functions:**
- `QualityCheck.validate_record(record, rules)` - Individual record validation
- `QualityCheck.apply_schema_validation(data, schema)` - Schema-based validation
- `QualityCheck.apply_json_logic_rules(data, rules)` - Rule-based validation
- `QualityCheck.generate_error_report(errors)` - Error reporting

### 5. Enhanced Datastore (`src/pipeline/datastore.py`)

**Primary Functions:**
- `EnhancedDatastore.store_validation_run(run_data)` - Store validation results
- `EnhancedDatastore.compare_with_previous_run(current_errors)` - Error comparison
- `EnhancedDatastore.generate_quality_dashboard(instrument)` - Dashboard generation
- `EnhancedDatastore.analyze_error_trends(instrument, days_back)` - Trend analysis

**Database Schema:**
```sql
-- Validation runs metadata
CREATE TABLE validation_runs (
    id TEXT PRIMARY KEY,
    instrument TEXT,
    timestamp DATETIME,
    total_records INTEGER,
    error_count INTEGER,
    mode TEXT,
    user_initials TEXT
);

-- Detailed error records
CREATE TABLE error_records (
    id INTEGER PRIMARY KEY,
    run_id TEXT,
    ptid TEXT,
    event_name TEXT,
    field_name TEXT,
    error_type TEXT,
    error_message TEXT,
    field_value TEXT,
    FOREIGN KEY (run_id) REFERENCES validation_runs(id)
);
```

### 6. Helper Functions (`src/pipeline/helpers.py`)

**Primary Functions:**
- `build_complete_visits_df(data)` - Complete visits dataset construction
- `build_detailed_validation_logs(errors)` - Detailed logging
- `load_rules_for_instruments(instruments)` - Rule loading and caching
- `prepare_instrument_data_cache(data)` - Data preparation optimization

### 7. CLI Interface (`src/cli/cli.py`)

**Available Commands:**
- `udsv4-qc config` - Configuration validation and display
- `udsv4-qc run` - Standard validation pipeline
- `udsv4-qc run-enhanced` - Enhanced validation with datastore
- `udsv4-qc datastore-status` - Database status information
- `udsv4-qc datastore-analysis` - Generate analysis reports

## Configuration System

### Environment Variables (.env file)
```env
# REDCap API Configuration
REDCAP_API_URL=https://your-redcap-instance/api/
REDCAP_API_TOKEN=your_api_token_here

# Database Configuration (for network drive)
VALIDATION_HISTORY_DB_PATH=\\network-drive\shared\validation_history.db

# Optional Configuration
OUTPUT_PATH=./output
JSON_RULES_PATH=./config/json_rules
LOG_LEVEL=INFO
```

### Configuration Validation
The system validates:
- API credentials and connectivity
- File system paths and permissions
- Database accessibility
- Rule file availability
- Output directory writability

## Validation Pipeline

### 1. Data Fetching Phase
- Connects to REDCap API
- Fetches raw data based on configuration
- Applies mode-specific filtering
- Prepares instrument-specific datasets

### 2. Rule Processing Phase
- Loads JSON validation rules
- Applies schema validation (Cerberus)
- Executes complex logic rules (JSON Logic)
- Handles dynamic validation scenarios

### 3. Validation Execution Phase
- Processes records individually
- Collects validation errors
- Generates detailed error context
- Tracks validation metrics

### 4. Output Generation Phase
- Creates CSV error reports
- Generates summary statistics
- Builds status reports
- Produces validation logs

### 5. Database Integration Phase (Enhanced Mode)
- Stores validation results
- Compares with previous runs
- Generates trend analyses
- Creates quality dashboards

## Database Integration

### Network Drive Setup for Windows
```powershell
# Set environment variable for network database
$env:VALIDATION_HISTORY_DB_PATH = "\\network-drive\shared\validation_history.db"

# Verify network connectivity
Test-Path "\\network-drive\shared\"

# Check database access
dir "\\network-drive\shared\validation_history.db"
```

### Database Features
- **Centralized Storage**: Shared database for team collaboration
- **Historical Tracking**: Long-term error trend analysis
- **Run Comparison**: Identify new, resolved, and persistent errors
- **Pattern Detection**: Systematic error identification
- **Performance Monitoring**: Database size and query optimization

## CLI Interface

### Command Structure
```
udsv4-qc [OPTIONS] COMMAND [ARGS]

Options:
  --log-level [DEBUG|INFO|WARNING|ERROR]  Set logging level
  --version                               Show version
  --help                                  Show help message

Commands:
  config              Display configuration status
  run                 Run standard validation pipeline
  run-enhanced        Run enhanced validation with datastore
  datastore-status    Show database status
  datastore-analysis  Generate analysis reports
```

### Common Usage Patterns
```bash
# Check system configuration
udsv4-qc config

# Run standard validation
udsv4-qc run --mode complete_visits --initials "JDT"

# Run enhanced validation with database
udsv4-qc run-enhanced --mode complete_events --center_id 123

# Generate analysis report
udsv4-qc datastore-analysis --instrument a1 --output-dir ./analysis
```

## Windows Environment Setup

### Prerequisites
- Python 3.9+ installed
- Network drive access configured
- REDCap API credentials available

### Installation Steps
```cmd
# Clone the repository
git clone <repository-url>
cd udsv4-redcap-qc-validator

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install in editable mode
pip install -e .

# Verify installation
udsv4-qc --help
```

### Network Drive Configuration
```cmd
# Map network drive (if needed)
net use Z: \\network-drive\shared

# Set database path
set VALIDATION_HISTORY_DB_PATH=Z:\validation_history.db

# Verify access
dir Z:\validation_history.db
```

### Running Tests
```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_cli.py -v

# Run with coverage
pytest --cov=src tests/
```

## Usage Examples

### Basic Validation
```bash
# Complete visits validation
udsv4-qc run --mode complete_visits --initials "JDT"

# Custom validation with specific instruments
udsv4-qc run --mode custom --initials "JDT" --event "udsv4_ivp_1_arm_1"
```

### Enhanced Validation
```bash
# Enhanced mode with database tracking
udsv4-qc run-enhanced --mode complete_events --center_id 123

# Generate comprehensive analysis
udsv4-qc datastore-analysis --instrument a1 --output-dir ./analysis
```

### Database Management
```bash
# Check database status
udsv4-qc datastore-status

# Generate trend analysis
udsv4-qc datastore-analysis --instrument a1 --days-back 90
```

### Configuration Management
```bash
# Display current configuration
udsv4-qc config

# Detailed configuration with JSON output
udsv4-qc config --detailed --json-output
```

## Performance Considerations

### Network Drive Operations
- **Local Database**: ~100-1000ms operations
- **Network Database**: ~1-10 seconds operations
- **Optimization**: Use datastore analysis commands for batch operations

### Database Size Management
- **Excellent**: < 100MB
- **Good**: 100MB - 1GB
- **Cleanup Needed**: > 1GB

### Memory Usage
- **Typical**: 200-500MB for standard runs
- **Large datasets**: 1-2GB for complete institution validation
- **Optimization**: Instrument-specific processing to reduce memory footprint

## Best Practices

### For Regular Users
1. Always check configuration before running (`udsv4-qc config`)
2. Use meaningful initials for tracking
3. Monitor database size regularly
4. Use enhanced mode for production validation

### For Administrators
1. Configure network drive permissions properly
2. Set up automated database backups
3. Monitor database performance
4. Implement data retention policies

### For Developers
1. Follow the existing code structure
2. Add comprehensive tests for new features
3. Update documentation when making changes
4. Use type hints and docstrings consistently

---

**Document Version**: 1.0  
**Last Updated**: July 16, 2025  
**Target Environment**: Windows with Network Drive Support
