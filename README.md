# UDSv4 REDCap QC Validator

A comprehensive Quality Control (QC) pipeline for validating NACC UDSv4 REDCap data with enhanced database tracking, trend analysis, and team collaboration features. This Windows-compatible system provides both standard validation and enhanced modes with historical error tracking on network drives.

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

## 📂 Project Structure

```text
udsv4-redcap-qc-validator/
├── src/
│   ├── cli/                    # Command-line interface
│   └── pipeline/               # Core validation pipeline
├── config/
│   └── json_rules/             # Validation rules (JSON format)
├── data/                       # Database storage directory
├── docs/                       # Comprehensive documentation
├── tests/                      # Test suite
├── output/                     # Default output directory
├── QUICK_START.md              # Quick reference guide
├── README.md                   # This file
└── requirements.txt            # Python dependencies
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

## 📊 Output Examples

### Standard Validation Output
```
output/QC_CompleteVisits_16JUL2025/
├── complete_visits_dataset_16JUL2025.csv    # Clean validated data
├── final_error_dataset_16JUL2025.csv        # All validation errors
├── QC_Report_ErrorCount_16JUL2025.csv       # Error summary by participant
├── QC_Status_Report_16JUL2025.csv           # Instrument-level status
└── Validation_Logs/                         # Detailed logs
```

### Enhanced Validation Output
```
output/ENHANCED_QC_CompleteEvents_16JUL2025/
├── ENHANCED_SUMMARY_16JUL2025.txt           # Enhanced summary report
├── QC_CompleteEvents_16JUL2025/             # Standard validation output
├── DATABASE_SUMMARY_16JUL2025.json          # Database storage summary
├── DATABASE_SUMMARY_16JUL2025.txt           # Human-readable summary
└── Analysis_Reports/                        # Trend analysis files
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

**Project Status**: Production Ready  
**Version**: 1.0.0  
**Target Environment**: Windows with Network Drive Support  
**Last Updated**: July 16, 2025
