# UDSv4 REDCap QC Validator

A comprehensive Quality Control (QC) pipeline for validating NACC UDSv4 REDCap data with enhanced database tracking, trend analysis, and team collaboration features. This Windows-compatible system provides both standard validation and enhanced modes with historical error tracking on network drives.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Important**: This project incorporates code from [`naccdata/nacc-form-validator`](https://github.com/naccdata/nacc-form-validator) which is licensed under the Mozilla Public License 2.0. See the [Third-Party Code Disclosure](#-third-party-code-disclosure) section below for complete licensing information.

## ✨ Key Features

- **Modern CLI Interface**: Professional command-line tool (`udsv4-qc`) with rich output formatting
- **Multiple Validation Modes**: 
  - Complete visits validation with database tracking
  - Incomplete visits processing
  - Custom validation with flexible filters
- **Enhanced Database Integration**: SQLite-based error tracking with network drive support
- **Historical Analysis**: Trend analysis, pattern detection, and error comparison between runs
- **Team Collaboration**: Centralized database storage for multi-user environments
- **Comprehensive Reporting**: Detailed CSV reports, validation logs, and quality dashboards
- **Windows Network Drive Support**: Optimized for Windows environments with UNC path support

## � Quick Start

### Windows Prerequisites
- Python 3.9 or higher installed
- Network drive access for team database features
- REDCap API credentials

### Installation Steps

1. **Clone and setup the environment:**
   ```bash
   git clone <repository-url>
   cd udsv4-redcap-qc-validator
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e .
   ```

2. **Configure your environment:**
   Create a `.env` file in the project root:
   ```env
   REDCAP_API_URL=https://your-redcap-instance/api/
   REDCAP_API_TOKEN=your_api_token_here
   VALIDATION_HISTORY_DB_PATH=\\network-drive\shared\validation_history.db
   ```
2.1 **Ensure all subdirectories have been created**
- Create output directory:
   ```bash
   mkdir output
   ```
- Update the path in the ENV file to point to the output directory:
   ```env
   OUTPUT_DIR=output
   ```

3. **Verify installation:**
   ```bash
   udsv4-qc --help
   udsv4-qc config
   ```

### Basic Usage

```bash
# Check system configuration
udsv4-qc config

# Run standard validation
udsv4-qc run --mode complete_visits --initials "JDT"

# Run enhanced validation with database tracking (recommended)
udsv4-qc run-enhanced --mode complete_events --center_id 123

# Check database status
udsv4-qc datastore-status

# Generate analysis reports
udsv4-qc datastore-analysis --instrument a1 --output-dir ./analysis
```

## 💻 Command Reference

### Core Commands
- `udsv4-qc config` - Display configuration status and validation
- `udsv4-qc run` - Execute standard validation pipeline
- `udsv4-qc run-enhanced` - Execute enhanced validation with database tracking
- `udsv4-qc datastore-status` - Show database status and instrument summary
- `udsv4-qc datastore-analysis` - Generate trend analysis and pattern detection reports

### Common Options
- `--mode [complete_visits|all_incomplete_visits|custom]` - Validation mode
- `--initials TEXT` - User initials for tracking (required for run commands)
- `--output-dir PATH` - Custom output directory
- `--disable-database` - Disable database tracking for testing

**For complete command reference, see [QUICK_START.md](QUICK_START.md)**

## 🌐 Network Drive Configuration

### Windows Environment Setup
```cmd
# Set database path (Command Prompt)
set VALIDATION_HISTORY_DB_PATH=\\network-drive\shared\validation_history.db

# Set database path (PowerShell)
$env:VALIDATION_HISTORY_DB_PATH = "\\network-drive\shared\validation_history.db"

# Verify network access
dir "\\network-drive\shared\"
```

### Benefits of Network Database
- **Centralized Error Tracking**: All team validation runs stored in shared database
- **Historical Analysis**: Long-term trend analysis across multiple runs
- **Quality Monitoring**: Dashboard and reporting functionality for quality assurance
- **Team Collaboration**: Shared access to validation history and patterns

## 🧪 Test Mode Features

The enhanced validator includes a comprehensive test mode for safe validation testing:

- **Isolated Testing**: Uses separate `test_validation_history.db` database
- **Error Detection**: Creates `TEST_RUN_SUMMARY_{date}.txt` showing if errors were found
- **Safe Experimentation**: No impact on production validation history
- **Easy Cleanup**: Use `clear_test_validation_db.py` to reset test database
- **Test Workflow**: Test first with `--test-mode`, then run `--production-mode`

```bash
# Test validation before production run
udsv4-qc run-enhanced --test-mode --mode complete_events --user-initials "TEST"

# Clean test database for fresh testing  
python clear_test_validation_db.py

# Run production validation after successful test
udsv4-qc run-enhanced --production-mode --mode complete_events --user-initials "JDT"
```

## 📚 Documentation

### Quick Reference
- **[QUICK_START.md](QUICK_START.md)** - Complete CLI command reference and usage examples
- **[docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)** - Comprehensive project documentation, architecture, and technical details

### Database Documentation
- **[data/README.md](data/README.md)** - Database setup, network drive configuration, and troubleshooting

### Additional Resources
- **Configuration Examples**: See `.env.template` for environment setup
- **Validation Rules**: Located in `config/json_rules/` directory
- **Test Suite**: Run `pytest tests/` for comprehensive testing
- **API Documentation**: Inline documentation in source code

## 🔧 Development and Testing

### Running Tests
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_cli.py -v
```

### Development Setup
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run code formatting
black src/ tests/

# Run linting
flake8 src/ tests/
```

## 🤝 Contributing

1. Follow the existing code structure and patterns
2. Add comprehensive tests for new features
3. Update documentation when making changes
4. Use type hints and docstrings consistently
5. Test on Windows environment with network drives

## 📋 System Requirements

- **Operating System**: Windows 10/11 (primary target)
- **Python Version**: 3.9 or higher
- **Memory**: 512MB minimum, 2GB recommended for large datasets
- **Network**: Access to REDCap API and network drive (for database features)
- **Storage**: 100MB for installation, additional space for output files

## 🔐 Security Considerations

- Store API tokens securely in `.env` file (never commit to version control)
- Ensure proper network drive permissions for team database access
- Follow your organization's data handling policies
- Review output files before sharing (may contain sensitive information)

## ⚡ Performance Notes

- **Local Operations**: ~100-1000ms response time
- **Network Database**: ~1-10 seconds for database operations
- **Large Datasets**: Memory usage scales with dataset size
- **Optimization**: Use specific modes and filters to reduce processing time

## 🆘 Support and Troubleshooting

### Common Issues
1. **Configuration errors**: Run `udsv4-qc config` to identify problems
2. **Network access**: Verify UNC paths and permissions
3. **Database conflicts**: Check for concurrent access issues
4. **Memory issues**: Process datasets in smaller chunks

### Getting Help
1. Check the documentation files listed above
2. Review the test suite for usage examples
3. Examine log files in the `logs/` directory
4. Contact system administrator for network drive issues

---

## 📢 Third-Party Code Disclosure

### NACC Form Validator Components

This project incorporates substantial code from the [`naccdata/nacc-form-validator`](https://github.com/naccdata/nacc-form-validator) repository, which is licensed under the **Mozilla Public License Version 2.0 (MPL v2.0)**.

#### Files Subject to MPL v2.0

The following files in the `nacc_form_validator/` directory are derived from or substantially incorporate code from the original NACC form validator:

- `datastore.py` - Data storage and persistence functionality
- `errors.py` - Error handling and validation error definitions  
- `json_logic.py` - JSON logic evaluation engine
- `keys.py` - Key management and validation utilities
- `nacc_validator.py` - Core validation logic and rules engine
- `quality_check.py` - Quality control checks and validation routines
- `utils.py` - Shared utility functions and helpers

#### Mozilla Public License v2.0 Compliance

**Source Code Availability**: The original source code for these components is available at:
- **Original Repository**: https://github.com/naccdata/nacc-form-validator
- **License Text**: https://www.mozilla.org/en-US/MPL/2.0/
- **License File**: [MPL-2.0-LICENSE](MPL-2.0-LICENSE) (included in this repository)

**Notice Requirements**: As required by MPL v2.0, Section 3.3:
- The above files retain their original copyright notices where applicable
- This notice serves as the required disclosure of MPL v2.0 covered source code
- Any modifications to the original MPL v2.0 files are documented in version control history

**License Compatibility**: The MPL v2.0 license is compatible with this project's MIT license for the combined work. The MPL v2.0 components remain under MPL v2.0, while the rest of the project is under MIT license.

#### Attribution

Original work by the NACC (National Alzheimer's Coordinating Center) team.  
Repository: https://github.com/naccdata/nacc-form-validator  
License: Mozilla Public License Version 2.0

For the complete license text and terms, see: https://www.mozilla.org/en-US/MPL/2.0/

**Project Status**: Production Ready  
**Version**: 1.0.0  
**Target Environment**: Windows with Network Drive Support  
**Last Updated**: August 28, 2025
