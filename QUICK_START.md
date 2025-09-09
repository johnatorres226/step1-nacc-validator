# Quick Start — UDSv4 REDCap QC Validator

This quick reference shows the primary commands for using this project. Two workflows are provided:

- Poetry (recommended)
- venv + pip (non-Poetry alternative)

Use the Poetry commands when possible for reproducible environments. The venv section provides equivalent commands if you prefer a standard virtual environment.

## Poetry (recommended)

### Install & environment

```bash
poetry install
poetry shell    # optional: open an interactive shell inside the poetry venv
```

### Common commands

```bash
# Show CLI help
poetry run udsv4-qc --help

# Check configuration
poetry run udsv4-qc config

# Run QC validation (main command)
poetry run udsv4-qc --initials "YOUR_INITIALS"

# Run QC with logging
poetry run udsv4-qc --initials "YOUR_INITIALS" --log

# Run QC with detailed outputs (slower, more files)
poetry run udsv4-qc --initials "YOUR_INITIALS" --detailed-run

# Diagnostics (use with --detailed-run)
poetry run udsv4-qc --initials "YOUR_INITIALS" --detailed-run --passed-rules

# Build the package
poetry build
```

## venv + pip (non-Poetry alternative)

### Create & activate (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Install & common commands

```powershell
# Install package in editable mode
pip install -e .

# Show CLI help
udsv4-qc --help

# Check configuration
udsv4-qc config

# Run QC validation (main command)
udsv4-qc --initials "YOUR_INITIALS"

# Run QC with logging
udsv4-qc --initials "YOUR_INITIALS" --log

# Run QC with detailed outputs
udsv4-qc --initials "YOUR_INITIALS" --detailed-run
```

## Notes

- The `--initials` (or `-i`) flag is required for runs and is used in output filenames.
- `--detailed-run` produces additional folders/files (Validation_Logs, Reports, Completed_Visits) and will take longer.
- `--passed-rules` must be used with `--detailed-run` and generates large diagnostic files; use only during debugging.

Last updated: September 9, 2025
