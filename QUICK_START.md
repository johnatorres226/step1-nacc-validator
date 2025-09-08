# UDSv4 REDCap QC Validator - Quick Start Guide

## CLI Commands

### Basic Command Structure

The UDSv4 REDCap QC Validator provides a command-line interface with two main commands:

```bash
# Check system configuration
udsv4-qc config

# Run QC validation (minimal - default mode with silent execution)
udsv4-qc run -i "YOUR_INITIALS"

# Run QC validation with logging enabled
udsv4-qc run -i "YOUR_INITIALS" --log

# Run QC validation with detailed outputs
udsv4-qc run -i "YOUR_INITIALS" --detailed-run
```

### Available Modes

**1. `complete_visits`** - ✅ **DEFAULT** - Validates only complete visits where all instruments are marked as complete
**2. `all_incomplete_visits`** - Validates visits with at least one incomplete instrument  
**3. `custom`** - ⚠️ **Under Development** - Flexible validation with custom filters

### Common Commands

#### Configuration Check

```bash
# Basic configuration check
udsv4-qc config

# Detailed configuration view
udsv4-qc config --detailed
```

#### Complete Visits Validation (Default Mode)

```bash
# Minimal command (silent execution, core outputs only)
udsv4-qc run -i "JDT"

# With terminal logging
udsv4-qc run -i "JDT" --log

# With detailed outputs (includes all validation logs and reports)
udsv4-qc run -i "JDT" --detailed-run

# With both logging and detailed outputs
udsv4-qc run -i "JDT" --log --detailed-run

# With comprehensive rules validation (for debugging/diagnostics)
udsv4-qc run -i "JDT" --detailed-run --passed-rules

# With full logging and comprehensive analysis
udsv4-qc run -i "JDT" --log --detailed-run --passed-rules

# With custom output directory
udsv4-qc run -i "JDT" --output-dir "C:\Custom\Output"
```

#### Other Modes

```bash
# All incomplete visits validation
udsv4-qc run -i "JDT" -m all_incomplete_visits

# Custom mode (under development)
udsv4-qc run -i "JDT" -m custom
```

### CLI Options Reference

#### Core Options

- `-i, --initials TEXT` - User initials for reporting (required)
- `-m, --mode [complete_visits|all_incomplete_visits|custom]` - Validation mode [default: complete_visits]
- `--output-dir PATH` - Custom output directory

#### Output Control

- `-l, --log` - Show terminal logging during execution (silent by default)
- `-dr, --detailed-run` - Generate detailed outputs including Validation_Logs, Completed_Visits, Reports, and Generation_Summary files
- `-ps, --passed-rules` - Generate comprehensive Rules Validation log for diagnostic purposes (requires --detailed-run/-dr, large file, slow generation)

#### Additional Options

- `--event TEXT` - Specify one or more events to run
- `--ptid TEXT` - Specify one or more PTIDs to check
- `--include-qced` - Include records that have already been QCed
- `--help` - Show help information

### Output Files

#### Default Run (Standard Mode)

- `Errors/` - Validation error reports
- `Data_Fetched/` - Raw data retrieved from REDCap
- `QC_Status_Report.json` - Basic status summary

#### Detailed Run Mode (`--detailed-run`)

- All standard outputs plus:
- `Validation_Logs/` - Comprehensive validation logs
- `Completed_Visits/` - Completed visits analysis
- `Reports/` - Detailed analysis reports  
- `Generation_Summary_*` - File generation summary

#### Comprehensive Rules Validation (`--passed-rules`)

When used with `--detailed-run`, additional diagnostic files are generated:

- `Rules_Validation_*` - Comprehensive log of all validation rules (passed and failed) for diagnostic purposes
- **Note**: This option generates large files and slower execution, intended for debugging and development

## Common Usage Patterns

### Daily Validation Workflow

```bash
# 1. Check configuration
udsv4-qc config

# 2. Run quick validation (silent, core outputs only)
udsv4-qc run -i "JDT"

# 3. Review core results
type output\QC_CompleteVisits_*\Errors\*.csv

# 4. Run detailed analysis if needed
udsv4-qc run -i "JDT" --detailed-run

# 5. Run incomplete visits monitoring if needed
udsv4-qc run -i "JDT" -m all_incomplete_visits
```

### Development/Debugging Workflow

```bash
# Run with logging to see detailed progress
udsv4-qc run -i "JDT" --log

# Run with full outputs and logging for comprehensive analysis
udsv4-qc run -i "JDT" --log --detailed-run

# Run with comprehensive rules validation for deep debugging
# (Warning: generates large files and slower execution)
udsv4-qc run -i "JDT" --log --detailed-run --passed-rules
```

## Troubleshooting

### Common Issues

1. **Configuration errors**: Run `udsv4-qc config` to identify issues
2. **API connection**: Verify REDCap URL and token in `.env` file
3. **File permissions**: Ensure write access to output directories
4. **Python environment**: Verify package installation and environment setup
5. **Unicode display errors**: Expected on Windows - functionality still works

### Performance Tips

- Use custom output directories to organize results effectively
- Monitor system resources during large validations
- Run validations during off-peak hours for large datasets

---

**Quick Start Version**: 2.3  
**Last Updated**: September 3, 2025  
**Compatible with**: Windows Environment with Enhanced CLI Interface (includes --passed-rules option)
