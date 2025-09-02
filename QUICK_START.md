# UDSv4 REDCap QC Validator - Quick Start Guide

## CLI Commands

### Basic Command Structure

The UDSv4 REDCap QC Validator provides a command-line interface with two main commands:

```bash
# Check system configuration
udsv4-qc config

# Run QC validation
udsv4-qc run --mode [MODE] --initials "YOUR_INITIALS"
```

### Available Modes

**1. `complete_visits`** - Validates only complete visits where all instruments are marked as complete
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

#### Complete Visits Validation

```bash
# Basic complete visits validation
udsv4-qc run --mode complete_visits --initials "JDT"

# With custom output directory
udsv4-qc run --mode complete_visits --initials "JDT" --output-dir "C:\Custom\Output"
```

#### Incomplete Visits Validation

```bash
# All incomplete visits validation
udsv4-qc run --mode all_incomplete_visits --initials "JDT"
```

### Common Options

- `--initials TEXT` - User initials for reporting (required)
- `--output-dir PATH` - Custom output directory
- `--log-level [DEBUG|INFO|WARNING|ERROR]` - Set logging level
- `--help` - Show help information

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

**Quick Start Version**: 2.2  
**Last Updated**: September 2, 2025  
**Compatible with**: Windows Environment with Simplified CLI Interface
