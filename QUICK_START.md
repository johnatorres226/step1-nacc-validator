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

#### 1. Check Configuration
```bash
# Verify system configuration
udsv4-qc config

# Detailed configuration view
udsv4-qc config --detailed

# JSON output format
udsv4-qc config --json-output
```

#### 2. Run Standard Validation
```bash
# Basic complete visits validation
udsv4-qc run --mode complete_visits --initials "JDT"

# All incomplete visits
udsv4-qc run --mode all_incomplete_visits --initials "JDT"

# Custom validation with specific events
udsv4-qc run --mode custom --initials "JDT" --event "udsv4_ivp_1_arm_1"

# Custom validation with specific participants
udsv4-qc run --mode custom --initials "JDT" --ptid "1001" --ptid "1002"

# Run with custom output directory
udsv4-qc run --mode complete_visits --initials "JDT" --output-dir "C:\Custom\Output"

# Run without database tracking (test mode)
udsv4-qc run --mode complete_visits --initials "JDT" --disable-database
```

#### 3. Run Enhanced Validation (Recommended)
```bash
# Enhanced validation with database tracking
udsv4-qc run-enhanced --mode complete_events --center_id 123

# Enhanced validation with custom instruments
udsv4-qc run-enhanced --mode complete_events --center_id 123 --instruments a1 a2

# Enhanced validation with specific events
udsv4-qc run-enhanced --mode complete_events --center_id 123 --events "udsv4_ivp_1_arm_1"

# Enhanced validation with custom output directory
udsv4-qc run-enhanced --mode complete_events --center_id 123 --output-path "C:\Enhanced\Output"

# Enhanced validation with user initials
udsv4-qc run-enhanced --mode complete_events --center_id 123 --user-initials "JDT"
```

### Database Commands

#### 4. Database Status
```bash
# Check database status and available instruments
udsv4-qc datastore-status

# Check specific database file
udsv4-qc datastore-status --datastore-path "\\network-drive\shared\validation_history.db"
```

#### 5. Generate Analysis Reports
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

### Legacy Command Support

#### 6. Legacy Datastore Commands
```bash
# Generate datastore analysis report
udsv4-qc datastore --instruments a1 a2 --output-path "output" --days-back 30
```

## Common Usage Patterns

### Daily Validation Workflow
```bash
# 1. Check configuration
udsv4-qc config

# 2. Run enhanced validation
udsv4-qc run-enhanced --mode complete_events --center_id 123

# 3. Check database status
udsv4-qc datastore-status

# 4. Generate analysis if needed
udsv4-qc datastore-analysis --instrument a1 --output-dir ./analysis
```

### Testing and Development
```bash
# Run without database for testing
udsv4-qc run --mode complete_visits --initials "TEST" --disable-database

# Run with custom output for testing
udsv4-qc run --mode complete_visits --initials "TEST" --output-dir "./test_output"
```

### Batch Processing
```bash
# Process multiple instruments in enhanced mode
udsv4-qc run-enhanced --mode complete_events --center_id 123 --instruments a1 a2 a3 a4

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
--output-dir PATH                                      # Custom output directory
--event TEXT                                           # Specific event (multiple allowed)
--ptid TEXT                                            # Specific participant ID (multiple allowed)
--include-qced                                         # Include already QCed records
--initials TEXT                                        # User initials (required)
--disable-database                                     # Disable database tracking
```

### Run-Enhanced Command Options
```bash
--mode [complete_events]                               # Enhanced mode (complete_events only)
--enable-datastore/--disable-datastore                # Enable/disable database (default: enabled)
--instruments TEXT                                     # Specific instruments (multiple allowed)
--events TEXT                                          # Specific events (multiple allowed)
--output-path PATH                                     # Custom output directory
--user-initials TEXT                                   # User initials
```

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
1. **Configuration errors**: Run `udsv4-qc config` to identify issues
2. **Network drive access**: Verify UNC path and permissions
3. **Database lock**: Check if database is being used by another process
4. **API connection**: Verify REDCap URL and token in `.env` file

#### Performance Tips
- Use `--disable-database` for testing to improve speed
- Run analysis commands during off-peak hours
- Monitor database size with `udsv4-qc datastore-status`

## Best Practices

### For Regular Use
1. Always use `udsv4-qc run-enhanced` for production validation
2. Check configuration before running: `udsv4-qc config`
3. Use meaningful initials for tracking
4. Monitor database status regularly

### For Team Collaboration
1. Use consistent network database path
2. Coordinate validation runs to avoid conflicts
3. Share analysis reports for trend monitoring
4. Use standard naming conventions for outputs

### For Development/Testing
1. Use `--disable-database` for testing
2. Use custom output directories for experiments
3. Test configuration changes with `udsv4-qc config`
4. Monitor logs for debugging information

---

**Quick Start Version**: 1.0  
**Last Updated**: July 16, 2025  
**Compatible with**: Windows Environment with Network Drive Support
