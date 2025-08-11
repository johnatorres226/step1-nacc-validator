# Test Suite Documentation

This directory contains automated tests for the `udsv4-redcap-qc-validator` project. All tests use the `pytest` framework. Below is a summary of each test script and instructions for running them.

## Test Scripts Overview

- **test_cli.py**: Tests the command-line interface, including the `config` and `run` commands, option overrides, error handling, and user input.
- **test_config.py**: Validates the `QCConfig` dataclass, environment variable loading, and configuration validation logic.
- **test_config_manager.py**: Tests configuration loading, validation, singleton pattern, and helper functions for dynamic rules and paths.
- **test_core_functionality.py**: Covers configuration system, datastore path resolution, enhanced datastore, report generation, pipeline integration, helper functions, error handling, and data validation.
- **test_datastore.py**: Verifies datastore initialization, previous record retrieval, and placeholder validation methods.
- **test_enhanced_datastore.py**: Tests enhanced datastore features, database schema, error comparison, dashboard generation, and integration with the report pipeline.
- **test_enhanced_run.py**: Checks enhanced output directory structure and naming conventions.
- **test_helpers.py**: Validates helper functions for loading JSON rules and running vectorized checks.
- **test_integration.py**: Provides end-to-end integration tests for the pipeline, configuration, data validation, error handling, and dashboard/report generation.
- **test_quality_check.py**: Tests the quality check logic, including initialization, schema validation, strict mode, and error handling.
- **test_report_pipeline.py**: Validates report generation functions, including tool status reports, aggregate error counts, and complete visits filtering.
- **test_signature.py**: Tests signature-related functionality (details depend on implementation).
- **test_compatibility_null_fields.py**: Ensures compatibility rule handling for null fields.

## How to Run the Tests

To run all tests in this directory:

```sh
pytest .
```

To run a specific test file:

```sh
pytest test_cli.py
```

Add the `-v` flag for verbose output:

```sh
pytest -v .
```

## Notes
- Make sure all dependencies in `requirements.txt` are installed before running tests.
- Some tests use fixtures and mocks for isolated testing.
- Test output will indicate pass/fail status and any errors encountered.
