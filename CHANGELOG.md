# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-09-10

### Added
- **Initial Release**: Complete UDSv4 REDCap Quality Control validation system
- **CLI Interface**: Comprehensive command-line interface with `udsv4-qc` command
- **Multiple Processing Modes**: 
  - `complete_visits`: Validate complete visits that haven't been QC'd
  - `all_incomplete_visits`: Process incomplete visits for quality control
- **REDCap Integration**: Secure API connection and data extraction from REDCap instances
- **Validation Engine**: Comprehensive NACC-specific validation rules with JSON-based rule definitions
- **Packet-Based Processing**: Automatic routing based on visit types (I, I4, F packets)
- **Hierarchical Rule Resolution**: Dynamic instrument detection and rule application
- **Data Quality Reports**: 
  - CSV error reports with detailed validation results
  - Validation logs with comprehensive rule checking
  - Generation summary reports
  - Passed records tracking
- **Flexible Output Management**: 
  - Configurable output directories
  - Timestamped report generation
  - Multiple report formats (CSV, JSON)
- **Advanced CLI Options**:
  - `--initials`: User identification for tracking and reporting
  - `--event`: Target specific REDCap events
  - `--ptid`: Filter by specific participant IDs
  - `--detailed-run`: Generate comprehensive output files
  - `--passed-rules`: Include detailed validation logs
  - `--log`: Enable verbose terminal logging
  - `--output-dir`: Custom output directory specification
- **Configuration Management**: 
  - Environment variable support
  - JSON-based configuration
  - Validation of configuration settings
- **Error Handling**: Robust error handling with detailed logging and user-friendly messages
- **Performance Features**:
  - Concurrent processing support
  - Efficient data filtering
  - Memory-optimized validation
- **Testing Suite**: Comprehensive test coverage (108 tests) covering all major components
- **Documentation**: Complete documentation including README, quick start guide, and technical docs

### Architecture
- **Modular Design**: Clean separation of concerns with dedicated modules for CLI, configuration, data fetching, validation, and reporting
- **ETL Pipeline**: Professional Extract-Transform-Load pipeline for REDCap data processing
- **Plugin Architecture**: Extensible validation rule system
- **Data Contracts**: Strict data validation and type safety

### Dependencies
- **Python 3.11+**: Modern Python with type hints and performance improvements
- **Poetry**: Dependency management and virtual environment handling
- **Click**: Professional CLI framework
- **Rich**: Enhanced terminal output and formatting
- **Pandas**: Data manipulation and analysis
- **Requests**: HTTP client for REDCap API integration
- **NACC Form Validator**: Integration with official NACC validation components

### Removed
- **Custom Mode**: Removed `--mode custom` functionality and associated `--include-qced` option for simplified operation

### Notes
- This is the initial stable release of the UDSv4 REDCap QC Validator
- Incorporates substantial code from the `naccdata/nacc-form-validator` repository under MPL v2.0 license
- Designed for production use in clinical research environments
- Cross-platform support (Windows, macOS, Linux)