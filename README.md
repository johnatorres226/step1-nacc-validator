# UDSv4 REDCap QC Validator

A comprehensive Quality Control (QC) validation system for NACC UDSv4 (Uniform Data Set version 4) REDCap data. This system provides automated data extraction, validation, and quality assurance for REDCap-based research data, ensuring compliance with NACC data quality standards and protocols.

## 📖 What This Project Does

The UDSv4 REDCap QC Validator is designed to:

- **Extract REDCap Data**: Securely connects to REDCap via API to retrieve UDSv4 form data
- **Apply Quality Control Rules**: Validates data using comprehensive NACC-specific validation rules stored in JSON format
- **Generate Detailed Reports**: Creates CSV reports, validation logs, and quality dashboards for data review
- **Support Multiple Processing Modes**: Handles complete visits, individual instruments, and custom filtering scenarios
- **Ensure Data Integrity**: Performs schema validation, custom field validation, and cross-field logic checks
- **Provide Audit Trails**: Comprehensive logging and monitoring for regulatory compliance and troubleshooting

## 🛠 Technologies and Dependencies

### Core Technologies
- **Python 3.9+**: Primary programming language
- **REDCap API**: For secure data extraction from REDCap databases
- **Cerberus**: Advanced data validation and schema enforcement
- **pandas**: Data manipulation and analysis
- **Click**: Modern command-line interface framework
- **Rich**: Enhanced console output and formatting

### Validation Engine
- **JSON Logic**: Flexible rule-based validation system
- **Custom NACC Validators**: Specialized validation methods for neurological assessment forms
- **Schema Validation**: Multi-stage validation pipeline with error detection and reporting

### Architecture Components
- **Configuration Management**: Environment-aware settings with type safety
- **ETL Pipeline**: Extract, Transform, Load pipeline for data processing
- **Quality Control Engine**: Core validation engine with packet-specific rules
- **Output Management**: Multi-format report generation (CSV, JSON, HTML)
- **Logging System**: Comprehensive audit trails and performance monitoring

## 📚 Documentation

For comprehensive understanding of the system, refer to the detailed documentation:

- **[System Architecture](docs/README.md)**: Complete technical overview and component relationships
- **[Configuration Management](docs/configuration-management.md)**: Environment setup and rule mapping
- **[Data Fetching System](docs/data-fetching-system.md)**: ETL pipeline and REDCap integration
- **[QC Validation Engine](docs/qc-validation-engine.md)**: Core validation logic and custom methods
- **[Output Management](docs/output-reporting.md)**: Report generation and file organization
- **[Logging & Monitoring](docs/logging-monitoring.md)**: Audit trails and performance tracking

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Important**: This project incorporates code from [`naccdata/nacc-form-validator`](https://github.com/naccdata/nacc-form-validator) which is licensed under the Mozilla Public License 2.0. See the [Third-Party Code Disclosure](#-third-party-code-disclosure) section below for complete licensing information.

## 🚀 Quick Start

### Windows Prerequisites

- Python 3.9 or higher installed
- REDCap API credentials
- Access to validation rule files (JSON format)

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
   PROJECT_ID=your_project_id
   JSON_RULES_PATH_I=config/I/
   JSON_RULES_PATH_I4=config/I4/
   JSON_RULES_PATH_F=config/F/
   ```

3. **Create required directories:**

   ```bash
   mkdir output
   ```

4. **Verify installation:**

   ```bash
   udsv4-qc --help
   udsv4-qc config
   ```

## 💻 Main Commands

The system provides two primary validation modes:

### Core Commands

- `udsv4-qc config` - Display configuration status and validation
- `udsv4-qc run` - Execute QC validation pipeline

### Main Validation Modes

```bash
# Validate complete visits (all instruments completed)
udsv4-qc run --mode complete_visits --initials "ABC"

# Validate individual completed instruments
udsv4-qc run --mode complete_instruments --initials "ABC"
```

### Command Parameters

- `--mode` - Validation mode (complete_visits, complete_instruments, custom)
- `--initials` - User initials for tracking and reporting (required)
- `--output-dir` - Custom output directory path
- `--event` - Specify specific REDCap events to process
- `--ptid` - Target specific participant IDs

**For complete command reference and advanced usage, see [QUICK_START.md](QUICK_START.md)**

## 🔧 System Requirements

- **Operating System**: Windows 10/11 (primary target), macOS, Linux
- **Python Version**: 3.9 or higher
- **Memory**: 512MB minimum, 2GB recommended for large datasets
- **Storage**: 100MB for installation, additional space for output files
- **Network**: Access to REDCap API endpoint

## 🔐 Security Considerations

- Store API tokens securely in `.env` file (never commit to version control)
- Follow your organization's data handling policies for PHI/PII
- Review output files before sharing (may contain sensitive information)
- Ensure proper file permissions on validation rule directories

## 🤝 Contributing

1. Follow the existing code structure and architectural patterns
2. Add comprehensive tests for new features
3. Update documentation when making changes
4. Use type hints and docstrings consistently
5. Test on Windows environment as primary target platform

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

- **Original Repository**: <https://github.com/naccdata/nacc-form-validator>
- **License Text**: <https://www.mozilla.org/en-US/MPL/2.0/>
- **License File**: [MPL-2.0-LICENSE](MPL-2.0-LICENSE) (included in this repository)

**Notice Requirements**: As required by MPL v2.0, Section 3.3:

- The above files retain their original copyright notices where applicable
- This notice serves as the required disclosure of MPL v2.0 covered source code
- Any modifications to the original MPL v2.0 files are documented in version control history

**License Compatibility**: The MPL v2.0 license is compatible with this project's MIT license for the combined work. The MPL v2.0 components remain under MPL v2.0, while the rest of the project is under MIT license.

#### Attribution

Original work by the NACC (National Alzheimer's Coordinating Center) team.  
Repository: <https://github.com/naccdata/nacc-form-validator>  
License: Mozilla Public License Version 2.0

For the complete license text and terms, see: <https://www.mozilla.org/en-US/MPL/2.0/>

**Project Status**: Production Ready  
**Version**: 1.0.0  
**Target Environment**: Windows with cross-platform support  
**Last Updated**: September 2, 2025
