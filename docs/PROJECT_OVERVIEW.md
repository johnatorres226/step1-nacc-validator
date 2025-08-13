# UDSv4 REDCap QC Validator - Project Overview

## Table of Contents
- [Overview](#overview)
- [Core Scripts and Functions](#core-scripts-and-functions)
- [Configuration System](#configuration-system)
- [Validation Pipeline](#validation-pipeline)
- [CLI Interface](#cli-interface)
- [Windows Environment Setup](#windows-environment-setup)
- [Output Structure](#output-structure)
- [Testing Framework](#testing-framework)
- [Usage Examples](#usage-examples)

## Overview

The UDSv4 REDCap QC Validator is a comprehensive quality control pipeline designed for validating NACC UDSv4 REDCap data. The system provides both basic validation capabilities and enhanced features with historical tracking, trend analysis, and pattern detection.

### Key Features
- **Multi-mode Validation**: Supports complete visits, incomplete visits, and custom validation modes
- **Schema-driven Validation**: Uses Cerberus and JSON Logic for flexible rule definitions
- **Network Drive Support**: Centralized database storage for team collaboration
- **Modern CLI**: Rich command-line interface with progress indicators and tables

## Core Scripts and Functions

### 1. Main Pipeline (`src/pipeline/report_pipeline.py`)

**Primary Functions:**
- `run_report_pipeline(config, enable_datastore)` - Main entry point for standard validation
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

### 5. Helper Functions (`src/pipeline/helpers.py`)

**Primary Functions:**
- `build_complete_visits_df(data)` - Complete visits dataset construction
- `build_detailed_validation_logs(errors)` - Detailed logging
- `load_rules_for_instruments(instruments)` - Rule loading and caching
- `prepare_instrument_data_cache(data)` - Data preparation optimization

### 6. CLI Interface (`src/cli/cli.py`)

**Available Commands:**
- `udsv4-qc config` - Configuration validation and display
- `udsv4-qc run` - Standard validation pipeline

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
- **Historical Tracking**: Long-term error trend analysis
- **Run Comparison**: Identify new, resolved, and persistent errors
- **Pattern Detection**: Systematic error identification

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


### Configuration Management
```bash
# Display current configuration
udsv4-qc config

# Detailed configuration with JSON output
udsv4-qc config --detailed --json-output
```

---

**Document Version**: 1.1  
**Last Updated**: August 12, 2025  
**Target Environment**: Windows with Network Drive Support
