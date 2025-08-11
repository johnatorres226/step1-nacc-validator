# UDSv4 REDCap QC Validator - Quick Start Guide

## Prerequisites

- Python 3.9+ installed
- Virtual environment activated
- REDCap API credentials available
- Network drive access configured (for database features)

## Installation

```bash
# Clone and install
git clone <repository-url>
cd udsv4-redcap-qc-validator
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Configuration

Create a `.env` file in the project root:

```env
REDCAP_API_URL=https://your-redcap-instance/api/
REDCAP_API_TOKEN=your_api_token_here
VALIDATION_HISTORY_DB_PATH=\\network-drive\shared\validation_history.db
```

## CLI Commands

### Core Commands

The UDSv4 REDCap QC Validator supports multiple validation modes, each designed for specific use cases and data filtering requirements:

#### Validation Modes Explained

**1. `complete_visits` Mode**

- **Purpose**: Validates only complete visits where ALL specified instruments are marked as complete (status = '2')
- **Logic**: Filters data to include only participant visits where every instrument has a completion status of '2'
- **Use Case**: Production validation for finalized data entry, quality assurance for complete records
- **Database Support**: ✅ Enabled by default for historical tracking

**2. `all_incomplete_visits` Mode**

- **Purpose**: Validates visits that have at least one incomplete instrument
- **Logic**: Includes any visit where one or more instruments are not marked as complete (status ≠ '2')
- **Use Case**: Data entry monitoring, identifying visits needing completion, workflow management
- **Database Support**: ❌ Not supported (focus on complete data for trending)

**3. `custom` Mode**

- **Purpose**: Flexible validation with user-defined filters for events, participants, or instruments
- **Logic**: Applies custom filters (--event, --ptid, --include-qced) as specified by user
- **Use Case**: Targeted validation, debugging specific records, ad-hoc quality checks
- **Database Support**: ❌ Not supported (custom filters may not be comparable across runs)

**4. `complete_events` Mode (Enhanced Only)**

- **Purpose**: Advanced validation for complete events with comprehensive database tracking
- **Logic**: Validates complete events with error comparison, trend analysis, and pattern detection
- **Use Case**: Production environments, team collaboration, long-term quality monitoring
- **Database Support**: ✅ Required - provides error tracking, comparisons, and analytics

#### Key Differences

- **Data Scope**: `complete_visits` focuses on finalized data, `all_incomplete_visits` on work-in-progress
- **Filtering**: `custom` allows precise targeting, `complete_events` provides comprehensive analysis
- **Database Integration**: Only `complete_visits` and `complete_events` support historical tracking
- **Team Use**: `complete_events` is optimized for collaborative environments with shared databases

#### 1. Check Configuration

```bash
# Verify system configuration
udsv4-qc config

# Detailed configuration view
udsv4-qc config --detailed

# JSON output format
udsv4-qc config --json-output
```

#### 2. Test Mode (Enhanced - Safe Testing) 🧪

**⚠️ RECOMMENDED: Always test first before running production validation!**

Test Mode provides a completely isolated testing environment that allows you to validate your data quality and configuration without affecting production validation history.

```bash
# 🧪 TEST MODE - Run validation in isolated test environment
udsv4-qc run-enhanced --test-mode --mode complete_events --user-initials "TEST"

# Test mode with custom instruments (recommended for testing)
udsv4-qc run-enhanced --test-mode --mode complete_events --user-initials "TEST" --instruments a1 a2

# Test mode with specific events
udsv4-qc run-enhanced --test-mode --mode complete_events --user-initials "TEST" --events "udsv4_ivp_1_arm_1"

# Clean test database for fresh testing
python clear_test_validation_db.py

# 🏭 PRODUCTION MODE - Switch to production after successful testing
udsv4-qc run-enhanced --production-mode --mode complete_events --user-initials "JDT"
```

**🧪 Test Mode Features:**

- **Isolated Database**: Uses `test_validation_history.db` (separate from production)
- **Safe Testing**: No impact on production validation history
- **Test Output**: Creates `TEST_RUN_SUMMARY_{date}.txt` with error detection
- **Test Directories**: Adds `_TEST` suffix to output directory names
- **Easy Cleanup**: Use `clear_test_validation_db.py` to reset test database

**🎯 Recommended Workflow:**

1. **Test First**: Run with `--test-mode` to validate data quality
2. **Review Results**: Check `TEST_RUN_SUMMARY_{date}.txt` for any errors
3. **Fix Issues**: Address any errors found and re-test
4. **Production Run**: Once test passes cleanly, run with `--production-mode`

**💡 Test Mode vs Production Mode:**

| Aspect | Test Mode | Production Mode |
|--------|-----------|-----------------|
| Database | `test_validation_history.db` | `validation_history.db` |
| CLI Flag | `--test-mode` | `--production-mode` (default) |
| Output Files | `TEST_RUN_SUMMARY_{date}.txt` | `ENHANCED_SUMMARY_{date}.txt` |
| Directory Suffix | `_TEST` | None |
| Data Safety | Isolated testing only | Affects production history |

#### 3. Complete Events Mode (Enhanced - Production)

```bash
# Enhanced validation with database tracking
udsv4-qc run-enhanced --mode complete_events --initials "JDT"

# Enhanced validation with custom instruments
udsv4-qc run-enhanced --mode complete_events --initials "JDT" --instruments a1 a2

# Enhanced validation with specific events
udsv4-qc run-enhanced --mode complete_events --initials "JDT" --events "udsv4_ivp_1_arm_1"

# Enhanced validation with custom output directory
udsv4-qc run-enhanced --mode complete_events --initials "JDT" --output-path "C:\Enhanced\Output"
```

#### 4. Complete Visits Mode

```bash
# Basic complete visits validation
udsv4-qc run --mode complete_visits --initials "JDT"

# Complete visits with custom output directory
udsv4-qc run --mode complete_visits --initials "JDT" --output-path "C:\Custom\Output"

# Complete visits without database tracking (test mode)
udsv4-qc run --mode complete_visits --initials "JDT" --disable-database
```

#### 5. Custom Mode

```bash
# Custom validation with specific events
udsv4-qc run --mode custom --initials "JDT" --event "udsv4_ivp_1_arm_1"

# Custom validation with specific participants
udsv4-qc run --mode custom --initials "JDT" --ptid "1001" --ptid "1002"

# Custom validation with both event and participant filters
udsv4-qc run --mode custom --initials "JDT" --event "udsv4_ivp_1_arm_1" --ptid "NM0048"

# Custom validation including already QCed records
udsv4-qc run --mode custom --initials "JDT" --event "udsv4_ivp_1_arm_1" --include-qced
```

#### 6. All Incomplete Visits Mode

```bash
# All incomplete visits validation
udsv4-qc run --mode all_incomplete_visits --initials "JDT"

# Incomplete visits with custom output directory
udsv4-qc run --mode all_incomplete_visits --initials "JDT" --output-path "C:\Incomplete\Output"
```

### Database Commands

#### 7. Database Status

```bash
# Check database status and available instruments
udsv4-qc datastore-status

# Check specific database file
udsv4-qc datastore-status --datastore-path "\\network-drive\shared\validation_history.db"
```

#### 8. Generate Analysis Reports

```bash
# Generate analysis for specific instrument
udsv4-qc datastore-analysis --instrument a1

# Generate analysis with custom output directory
udsv4-qc datastore-analysis --instrument a1 --output-dir "C:\Analysis\Reports"

# Generate analysis for specific time period
udsv4-qc datastore-analysis --instrument a1 --days-back 90

# Generate analysis with custom database path
udsv4-qc datastore-analysis --instrument a1 --datastore-path "\\network-drive\shared\validation_history.db"
```

## Common Usage Patterns

### Daily Validation Workflow

```bash
# 1. Check configuration
udsv4-qc config

# 2. Test mode first (RECOMMENDED)
udsv4-qc run-enhanced --test-mode --mode complete_events --initials "TEST"

# 3. Review test results
type output\*_TEST\TEST_RUN_SUMMARY_*.txt

# 4. Run production validation if test passes
udsv4-qc run-enhanced --production-mode --mode complete_events --initials "JDT"

# 5. Check database status
udsv4-qc datastore-status

# 6. Generate analysis if needed
udsv4-qc datastore-analysis --instrument a1 --output-dir ./analysis
```

### Testing and Development

```bash
# Safe testing with test mode
udsv4-qc run-enhanced --test-mode --mode complete_events --initials "TEST"

# Clean test database for fresh testing
python clear_test_validation_db.py

# Run without database for quick testing
udsv4-qc run --mode complete_visits --initials "TEST" --disable-database

# Run with custom output for testing
udsv4-qc run --mode complete_visits --initials "TEST" --output-path "./test_output"
```

### Batch Processing

```bash
# Process multiple instruments in enhanced mode
udsv4-qc run-enhanced --mode complete_events --initials "JDT" --instruments a1 a2 a3 a4

# Generate multiple analysis reports
udsv4-qc datastore-analysis --instrument a1 --output-dir ./analysis
udsv4-qc datastore-analysis --instrument a2 --output-dir ./analysis
udsv4-qc datastore-analysis --instrument a3 --output-dir ./analysis
```

## Command Options Reference

### Global Options

```bash
--log-level [DEBUG|INFO|WARNING|ERROR]  # Set logging level (default: INFO)
--version                               # Show version information
--help                                  # Show help message
```

### Run Command Options

```bash
--mode [complete_visits|all_incomplete_visits|custom]  # Validation mode (required)
--output-path PATH                                     # Custom output directory
--event TEXT                                           # Specific event (multiple allowed)
--ptid TEXT                                            # Specific participant ID (multiple allowed)
--include-qced                                         # Include already QCed records
--user-initials TEXT                                   # User initials (required)
--disable-database                                     # Disable database tracking
```

### Run-Enhanced Command Options

```bash
--mode [complete_events]                               # Enhanced mode (complete_events only)
--enable-datastore/--disable-datastore                # Enable/disable database (default: enabled)
--test-mode/--production-mode                          # Test mode or production mode (default: production)
--instruments TEXT                                     # Specific instruments (multiple allowed)
--events TEXT                                          # Specific events (multiple allowed)
--output-path PATH                                     # Custom output directory
--user-initials TEXT                                   # User initials
```

**Test Mode vs Production Mode:**

- `--test-mode`: Uses `test_validation_history.db`, creates `TEST_RUN_SUMMARY_{date}.txt`, adds `_TEST` suffix to directories
- `--production-mode`: Uses production database, standard enhanced summary format (default behavior)

### Database Command Options

```bash
--datastore-path PATH                                  # Custom database path
--instrument TEXT                                      # Specific instrument (required for analysis)
--output-dir PATH                                      # Analysis output directory
--days-back INTEGER                                    # Days to analyze (default: 30)
```

## Output Structure

### Standard Run Output

```
output/QC_CompleteVisits_DDMMMYYYY/
├── complete_visits_dataset_DDMMMYYYY.csv      # Clean dataset
├── final_error_dataset_DDMMMYYYY.csv          # All errors found
├── QC_Report_ErrorCount_DDMMMYYYY.csv         # Error count summary
├── QC_Status_Report_DDMMMYYYY.csv             # Instrument status
└── Validation_Logs/                           # Detailed logs
    ├── validation_DDMMMYYYY.log
    └── detailed_validation_log_DDMMMYYYY.txt
```

### Enhanced Run Output

```
output/ENHANCED_QC_CompleteEvents_DDMMMYYYY/
├── ENHANCED_SUMMARY_DDMMMYYYY.txt             # Enhanced summary
├── QC_CompleteEvents_DDMMMYYYY/               # Standard output
├── DATABASE_SUMMARY_DDMMMYYYY.json            # Database summary (JSON)
├── DATABASE_SUMMARY_DDMMMYYYY.txt             # Database summary (text)
└── Analysis_Reports/                          # Trend analysis
    ├── trend_analysis_DDMMMYYYY.csv
    └── pattern_detection_DDMMMYYYY.csv
```

### Test Mode Output

```
output/ENHANCED_QC_CompleteEvents_DDMMMYYYY_TEST/
├── TEST_RUN_SUMMARY_DDMMMYYYY.txt             # Test summary with error detection
├── QC_CompleteEvents_DDMMMYYYY_TEST/          # Standard output with TEST suffix
├── DATABASE_SUMMARY_DDMMMYYYY_TEST.json       # Test database summary (JSON)
├── DATABASE_SUMMARY_DDMMMYYYY_TEST.txt        # Test database summary (text)
└── Analysis_Reports/                          # Test trend analysis
    ├── trend_analysis_DDMMMYYYY_TEST.csv
    └── pattern_detection_DDMMMYYYY_TEST.csv
```

## Windows Environment Setup

### Network Drive Configuration

```cmd
# Set environment variable (Command Prompt)
set VALIDATION_HISTORY_DB_PATH=\\network-drive\shared\validation_history.db

# Set environment variable (PowerShell)
$env:VALIDATION_HISTORY_DB_PATH = "\\network-drive\shared\validation_history.db"

# Verify network access
dir "\\network-drive\shared\"
```

### Troubleshooting

#### Common Issues

1. **Configuration errors**: Run `python -m src.cli.cli config` to identify issues
2. **Network drive access**: Verify UNC path and permissions
3. **Database lock**: Check if database is being used by another process
4. **API connection**: Verify REDCap URL and token in `.env` file
5. **Unicode display errors**: Expected on Windows - functionality still works

#### Performance Tips

- Use `--test-mode` for safe testing before production runs
- Use `--disable-database` for testing to improve speed
- Run analysis commands during off-peak hours
- Monitor database size with `python -m src.cli.cli datastore-status`

## Best Practices

### For Regular Use

1. **Always test first**: Use `--test-mode` before production runs
2. Check configuration: `python -m src.cli.cli config`
3. Use meaningful initials for tracking
4. Monitor database status regularly
5. Clean test database as needed: `python clear_test_validation_db.py`

### For Team Collaboration

1. Use consistent network database path
2. Coordinate validation runs to avoid conflicts
3. Share analysis reports for trend monitoring
4. Use standard naming conventions for outputs
5. Document test procedures and results

### For Development/Testing

1. **Use test mode first**: `--test-mode` for all new configurations
2. Use `--disable-database` for quick testing without database
3. Use custom output directories for experiments
4. Test configuration changes with `python -m src.cli.cli config`
5. Monitor logs for debugging information

---

**Quick Start Version**: 2.0  
**Last Updated**: July 17, 2025  
**Compatible with**: Windows Environment with Network Drive Support  
**Test Mode**: Full Support with Database Isolation
