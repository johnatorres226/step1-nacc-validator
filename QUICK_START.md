# UDSv4 REDCap QC Validator - Quick Start Guide

## CLI Commands

### Core Commands

The UDSv4 REDCap QC Validator supports multiple validation modes, each designed for specific use cases and data filtering requirements:

#### Validation Modes Explained

**1. `complete_visits` Mode**

- **Purpose**: Validates only complete visits where ALL specified instruments are marked as complete (status = '2')
- **Logic**: Filters data to include only participant visits where every instrument has a completion status of '2'
- **Use Case**: Production validation for finalized data entry, quality assurance for complete records

**2. `all_incomplete_visits` Mode**

- **Purpose**: Validates visits that have at least one incomplete instrument
- **Logic**: Includes any visit where one or more instruments are not marked as complete (status ≠ '2')
- **Use Case**: Data entry monitoring, identifying visits needing completion, workflow management

**3. `custom` Mode**

- **Purpose**: Flexible validation with user-defined filters for events, participants, or instruments
- **Logic**: Applies custom filters (--event, --ptid, --include-qced) as specified by user
- **Use Case**: Targeted validation, debugging specific records, ad-hoc quality checks

#### Key Differences

- **Data Scope**: `complete_visits` focuses on finalized data, `all_incomplete_visits` on work-in-progress
- **Filtering**: `custom` allows precise targeting for specific validation needs
- **Use Cases**: Different modes serve different phases of the data collection workflow

#### 1. Check Configuration

```bash
# Verify system configuration
udsv4-qc config

# Detailed configuration view
udsv4-qc config --detailed

# JSON output format
udsv4-qc config --json-output
```

#### 2. Complete Visits Mode

```bash
# Basic complete visits validation
udsv4-qc run --mode complete_visits --initials "JDT"

# Complete visits with custom output directory
udsv4-qc run --mode complete_visits --initials "JDT" --output-dir "C:\Custom\Output"
```

#### 3. Custom Mode

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

#### 4. All Incomplete Visits Mode

```bash
# All incomplete visits validation
udsv4-qc run --mode all_incomplete_visits --initials "JDT"

# Incomplete visits with custom output directory
udsv4-qc run --mode all_incomplete_visits --initials "JDT" --output-dir "C:\Incomplete\Output"
```

## Common Usage Patterns

### Daily Validation Workflow

```bash
# 1. Check configuration
udsv4-qc config

# 2. Run complete visits validation
udsv4-qc run --mode complete_visits --initials "JDT"

# 3. Review results
type output\QC_CompleteVisits_*\final_error_dataset_*.csv

# 4. Run incomplete visits monitoring if needed
udsv4-qc run --mode all_incomplete_visits --initials "JDT"

# 5. Generate targeted validation for specific events
udsv4-qc run --mode custom --initials "JDT" --event "udsv4_ivp_1_arm_1"
```

### Testing and Development

```bash
# Quick testing with custom output
udsv4-qc run --mode complete_visits --initials "TEST" --output-dir "./test_output"

# Test specific participants
udsv4-qc run --mode custom --initials "TEST" --ptid "1001" --ptid "1002"

# Test specific events and participants
udsv4-qc run --mode custom --initials "TEST" --event "udsv4_ivp_1_arm_1" --ptid "NM0048"

# Include already QCed records for testing
udsv4-qc run --mode custom --initials "TEST" --event "udsv4_ivp_1_arm_1" --include-qced
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
```

#### Common Issues

1. **Configuration errors**: Run `udsv4-qc config` to identify issues
2. **API connection**: Verify REDCap URL and token in `.env` file
3. **File permissions**: Ensure write access to output directories
4. **Python environment**: Verify package installation and environment setup
5. **Unicode display errors**: Expected on Windows - functionality still works

#### Performance Tips

- Use targeted validation with `--event` or `--ptid` filters for faster processing
- Use custom output directories to organize results effectively
- Monitor system resources during large validations
- Run validations during off-peak hours for large datasets

---

**Quick Start Version**: 2.1  
**Last Updated**: July 17, 2025  
**Compatible with**: Windows Environment with Simplified CLI Interface
