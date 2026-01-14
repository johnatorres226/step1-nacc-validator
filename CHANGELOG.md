# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-01-13

### Project Refactoring Initiative
- **Rescaling Project Scope** - Initiating major refactoring to simplify project architecture and focus on core QC extraction from nacc_form_validator. The goal is to reduce complexity in CLI, logging, and ETL processes while maintaining fundamental validation philosophy and line-by-line validation integrity.

### Planned Changes
- Simplify CLI interface and reduce logging verbosity
- Streamline output generation and validation log creation
- Refactor ETL pipeline while preserving core validation logic
- Minimize non-essential reporting features
- Maintain nacc_form_validator as core immutable component

## [0.2.0] - 2025-12-06

### Fixed
- **Cross-Form Compatibility Rule False Positives** - Fixed critical issue in `nacc_form_validator/nacc_validator.py` where compatibility rules referencing fields from other forms were generating false positive errors when those fields were missing or empty. Changed condition in `_check_subschema_valid()` from `if field in record_copy and _is_missing_value(...)` to `if field not in record_copy or _is_missing_value(...)` to properly handle both absent fields and fields with missing values. This eliminates false positives for cross-form validation rules (e.g., apnea/apneadx, bipolar/bipoldx, etc.).

### Changed
- **Removed Caching from Report Pipeline** - Eliminated all caching mechanisms in `src/pipeline/reports/report_pipeline.py` to ensure fresh rule loading on each validation run. Removed `_SchemaAndRulesCache` and `_SchemaAndRulesOptimizedCache` classes, replacing with direct rule loading.
- **Updated I4 Rules Configuration** - Fixed field name in `config/I4/rules/a5d2_rules.json` line 4617 from "anxiet" to "anxiety" to match current form specifications.

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