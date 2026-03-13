# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2026-03-13

### Added
- **REDCap Repeat Instance in JSON Output**: QC Status Report JSON payload now includes `redcap_repeat_instance` field for each participant record
  - Enables downstream processes to correctly identify and process repeating events
  - Supports proper record matching and data integration workflows
  - Field extracted from source data and included in JSON tracking export

## [1.1.0] - 2026-03-13

### Fixed
- **Compatibility Rule Variable Logging**: Compatibility rule errors now correctly report the actual failing variable instead of the trigger variable
  - When a compatibility rule fails (e.g., if `othersign=1` then `apraxsp` must be in [1,2,3]), the error is now logged under the failing variable (`apraxsp`) rather than the trigger variable (`othersign`)
  - Implemented regex-based extraction in `report_pipeline.py` to parse error messages and identify the correct variable
  - Added comprehensive test suite (`test_compatibility_variable_logging.py`) to detect this issue in future dependency updates
  - Resolves misidentified error variables in CSV output reports, improving error traceability and diagnosis
  - Note: This is a workaround for an upstream bug in `nacc-form-validator` package (https://github.com/naccdata/nacc-form-validator)

## [1.0.3] - 2026-03-13

### Added
- **Error Interpretation Field**: Added blank `error_interpretation` field to error dataset output for staging error interpretation feature
  - Prepares infrastructure for future error interpretation and guidance system
  - Field currently blank, ready for future enhancement

## [1.0.2] - 2026-03-13

### Fixed
- **visitdate and redcap_repeat_instance Propagation**: These fields are now properly included in error reports for all instruments, not just form_header
  - Added `visitdate` and `redcap_repeat_instance` to core columns list
  - Ensures all instrument error records include visit date and repeat instance information
- **Code Quality Improvements**:
  - Fixed line-too-long linting issues in report_pipeline.py
  - Fixed mypy type checking errors (added type annotations, proper exclusions)
  - Updated CI workflow with `--explicit-package-bases` flag for mypy

## [1.0.1] - 2026-03-13

### Changed
- **Enhanced Error Dataset Output**: Error reports now include additional fields for improved error tracking and resolution:
  - `redcap_repeat_instance`: REDCap event instance identifier
  - `visitdate`: Visit date from the record
  - `qc_date`: Timestamp when QC validation was performed

## [1.0.0] - 2026-03-09

### Added
- **Report-Based Data Fetching**: New `fetch_report_data()` function using REDCap's report API for pre-filtered data extraction, eliminating complex ETL transformations
- **Interactive CLI Commands Display**: Commands now automatically display after user login for improved discoverability
- **Packet Isolation System**: Implemented per-record packet isolation to prevent cross-packet rule collisions during validation
- **Expected Conflict Detection**: Enhanced rule pool with smart detection of expected namespace conflicts (C2/C2T) vs unexpected configuration errors
- **Comprehensive Test Coverage**: Expanded test suite to 140 passing tests covering report fetching, packet isolation, and unified validation
- **Auto-Packet Population**: Automatically adds packet field with default value 'I' when missing from REDCap exports

### Changed
- **Data Fetching Architecture**: Replaced complex ETL pipeline (6 classes, 397 lines) with streamlined report-based fetch (145 lines)
- **Pipeline Orchestration**: Simplified `run_pipeline()` from class-based orchestrator (700 lines) to functional approach (171 lines)
- **Rule Loading System**: Consolidated 4 rule routing files into single `rule_loader.py` with O(1) variable lookup via `NamespacedRulePool`
- **Report Generation**: Replaced `ReportFactory` class (732 lines) with 4 focused export functions (110 lines)
- **Data Processing**: Merged `instrument_processors.py` into `data_processing.py`, deleted `processors/` package
- **Validation Utilities**: Consolidated `validation_logging.py` and `visit_processing.py` into single `validation_utils.py` (99 lines)
- **Configuration Management**: Removed deprecated filter logic and completion column tracking, streamlined instrument mappings
- **CLI Branding**: Redesigned with UNM Lobos wordmark, merged check/config commands into unified `status` command
- **Documentation**: Completely rewrote `docs/data-fetching-system.md` to reflect report-based architecture (reduced from complex ETL documentation)
- **Rule Validation**: Updated validation rules across F, I, and I4 packets for a1a, a5d2, b1-b9, c2/c2t, d1a/d1b forms

### Fixed  
- **Multi-Packet Rule Collision**: Resolved issue where rules from different packets could interfere during validation of mixed-packet datasets
- **C2/C2T Namespace Conflicts**: Properly handle expected conflicts between C2 and C2T namespaces using discriminant-based routing
- **Rule Pool Caching**: Removed caching for safer, immutable behavior preventing stale rule references across runs

### Removed
- **Legacy ETL Classes**: Removed 6 ETL classes (`RedcapETLPipeline`, `RedcapApiClient`, `DataValidator`, `DataTransformer`, `DataSaver`, `FilterLogicManager`)
- **Deprecated Documentation**: Removed `CONFIG_RULE_ROUTING.md`, `ERROR_DEBUGGING.md`, `REFACTORING_PLAN.md` after consolidation
- **Dead Code**: Removed ~850 lines of unused code, 7 empty `__init__.py` files, deprecated validation functions
- **Obsolete Infrastructure**: Removed `processors/` package, `io/context.py`, instrument-specific processors
- **Legacy Fallback Logic**: Eliminated complex data fetch fallback mechanisms in favor of clear error reporting

### Internal
- **Code Reduction**: Overall pipeline source reduced from ~4,854 to ~1,690 lines (65% reduction) while maintaining full functionality
- **Test Suite Growth**: Increased from 116 to 140 passing tests with better coverage of edge cases
- **Project Classification**: Transitioned from "Alpha" to "Production/Stable" status

## [0.3.0] - 2026-01-13

### Fixed
- **A1A SDOH Form Validation with a1anot=93** - Updated `a1a_rules.json` for I, I4, and F packets to properly handle cases where `a1anot=93` (form not completed). All data fields in the A1A SDOH form are now nullable by default with a compatibility rule that makes them non-nullable when `a1anot` is forbidden (i.e., not equal to 93). System fields (`frmdatea1a`, `langa1a`, `modea1a`, `rmreasa1a`, `rmmodea1a`) remain required regardless of `a1anot` value. This resolves false positive errors for participants who declined or were unable to complete the form.


### Project Refactoring Initiative
- **Rescaling Project Scope** - Initiating minor adjustment to simplify project architecture and focus on core QC extraction from nacc_form_validator. The goal is to reduce complexity in CLI, logging, and minor ETL processes while maintaining fundamental validation philosophy and line-by-line validation integrity.

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
- **Processing Mode**: 
  - `complete_visits`: Validate complete visits that haven't been QC'd
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