# UDSv4 REDCap QC Validator

A comprehensive Quality Control (QC) validation system for NACC UDSv4 (Uniform Data Set version 4) REDCap data. This system provides automated data extraction, validation, and quality assurance for REDCap-based research data, ensuring compliance with NACC data quality standards and protocols.

> **✨ New: Poetry Integration** - This project now uses Poetry for modern dependency management, cross-platform compatibility, and reproducible builds. Existing users can migrate by following the [Poetry installation instructions](#-installation-with-poetry-recommended) below.

## 📑 Table of Contents

- [What This Project Does](#-what-this-project-does)
- [Technologies and Dependencies](#-technologies-and-dependencies)
  - [Core Technologies](#core-technologies)
  - [Development Tools](#development-tools)
  - [Validation Engine](#validation-engine)
  - [Architecture Components](#architecture-components)
- [Documentation](#-documentation)
- [License](#-license)
- [Quick Start](#-quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation with Poetry (Recommended)](#-installation-with-poetry-recommended)
  - [Alternative Installation (Legacy)](#-alternative-installation-legacy)
  - [Main Commands](#-main-commands)
- [Building and Development](#-building-and-development)
- [System Requirements](#-system-requirements)
- [Cross-Platform Compatibility](#-cross-platform-compatibility)
  - [Windows](#windows)
  - [Linux/Unix](#linuxunix)
  - [macOS](#macos)
- [Security Considerations](#-security-considerations)
- [Contributing](#-contributing)
  - [Development Setup](#development-setup)
  - [Development Workflow](#development-workflow)
  - [Testing Guidelines](#testing-guidelines)
  - [Code Quality Standards](#code-quality-standards)
  - [Adding Dependencies](#adding-dependencies)
- [Third-Party Code Disclosure](#-third-party-code-disclosure)


## �📖 What This Project Does

The UDSv4 REDCap QC Validator is designed to:

- **Extract REDCap Data**: Securely connects to REDCap via API to retrieve UDSv4 form data
- **Apply Quality Control Rules**: Validates data using comprehensive NACC-specific validation rules stored in JSON format
- **Generate Detailed Reports**: Creates CSV reports, validation logs, and quality dashboards for data review
- **Support Multiple Processing Modes**: Handles complete visits, individual instruments, and custom filtering scenarios
- **Ensure Data Integrity**: Performs schema validation, custom field validation, and cross-field logic checks
- **Provide Audit Trails**: Comprehensive logging and monitoring for regulatory compliance and troubleshooting

## 🛠 Technologies and Dependencies

### Core Technologies

- **Python 3.11+**: Primary programming language (Poetry managed)
- **Poetry**: Modern dependency management and packaging tool
- **REDCap API**: For secure data extraction from REDCap databases
- **Cerberus**: Advanced data validation and schema enforcement
- **pandas**: Data manipulation and analysis
- **Click**: Modern command-line interface framework
- **Rich**: Enhanced console output and formatting

### Development Tools

- **Poetry**: Dependency management, virtual environments, and packaging
- **pytest**: Testing framework with coverage reporting
- **Black**: Code formatting
- **Ruff**: Code linting
- **mypy**: Static type checking
- **pre-commit**: Git hooks for code quality

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

### Prerequisites

- **Python 3.11+** installed on your system
- **Git** for cloning the repository
- **REDCap API credentials** and access
- **Poetry** for dependency management (installation instructions below)

## 📦 Installation with Poetry (Recommended)

Poetry provides modern dependency management with deterministic builds and cross-platform compatibility.

---

### Step 1: Install Poetry  
**Windows (PowerShell)** — run the official installer script:

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

---

### Step 2: Where Poetry is Installed  

- Core installation (virtual environment):  
  `%AppData%\pypoetry\venv`

- Shim executable (used on PATH):  
  `%AppData%\Python\Scripts\poetry.exe`

The shim is what allows you to type `poetry` anywhere in the terminal.

---

### Step 3: Verify Installation  

```powershell
poetry --version
where.exe poetry
```

Or browse to the folder:

```powershell
cd $env:APPDATA\Python\Scripts
dir poetry.exe
```

---

### Step 4: Add Poetry to PATH (if not already available)

**Option A — PowerShell**

```powershell
$poetryPath = Join-Path $env:APPDATA 'Python\Scripts'
[Environment]::SetEnvironmentVariable(
  'Path',
  [Environment]::GetEnvironmentVariable('Path','User') + ';' + $poetryPath,
  'User'
)
```

- Close and reopen your terminal (or VS Code).  
- Restart your computer if necessary.

**Option B — Manual (Windows UI)**

1. Press **Start** → type *Environment Variables* → open **Edit the system environment variables**  
2. Click **Environment Variables…**  
3. Under **User variables**, select `Path` → **Edit…**  
4. Click **New**, then paste:  

   ```
   %AppData%\Python\Scripts
   ```

5. OK → OK to save  
6. Close and reopen your terminal (or VS Code)
7. May require a system restart if not udpated immediately

---

### Step 5: Reinstall or Uninstall if Needed  

To uninstall Poetry:

```powershell
python -m poetry self uninstall
```

*(or manually delete `%AppData%\pypoetry` and `%AppData%\Python\Scripts\poetry.exe` if broken)*

Reinstall with the installer script again if necessary.

---

### Linux / macOS  

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### Step 2: Clone and Setup Project

```bash
# Clone the repository
git clone https://github.com/johnatorres226/step1-nacc-validator.git
cd step1-nacc-validator

# Install dependencies (creates virtual environment automatically)
poetry install

# Verify installation
poetry run udsv4-qc --help
```

### Step 3: Environment Configuration

Create a `.env` file in the project root:

```env
REDCAP_API_URL=https://your-redcap-instance/api/
REDCAP_API_TOKEN=your_api_token_here
PROJECT_ID=your_project_id
JSON_RULES_PATH_I=config/I/
JSON_RULES_PATH_I4=config/I4/
JSON_RULES_PATH_F=config/F/
```

### Step 4: Create Output Directory

```bash
mkdir output
```

### Step 5: Verify Setup

```bash
# Check configuration
poetry run udsv4-qc config

# Test CLI functionality
poetry run udsv4-qc --version
```

## 🔨 Building and Development

### Development Setup

```bash
# Install with development dependencies
poetry install --with dev

# Activate virtual environment shell
poetry shell

# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=qc_pipeline --cov-report=html

# Code formatting
poetry run black .

# Type checking
poetry run mypy src/

# Linting
poetry run ruff
```

### Building the Package

```bash
# Build wheel and source distribution
poetry build

# Check build artifacts
ls dist/

# Install from built package (for testing)
pip install dist/udsv4_redcap_qc_validator-*.whl
```

### Poetry Commands Reference

```bash
# Dependency management
poetry add package-name              # Add runtime dependency
poetry add --group dev package-name  # Add development dependency
poetry remove package-name           # Remove dependency
poetry update                        # Update all dependencies
poetry show --tree                   # Show dependency tree

# Environment management
poetry env info                      # Show environment info
poetry env list                      # List environments
poetry shell                         # Activate environment shell
poetry run command                   # Run command in environment

# Package management
poetry build                         # Build package
poetry publish                       # Publish to PyPI (if configured)
poetry version patch                 # Bump version (patch/minor/major)
```

## 🎯 Alternative Installation (Legacy)

If you prefer traditional pip/venv setup:

### Windows Prerequisites

- Python 3.11 or higher installed
- REDCap API credentials
- Access to validation rule files (JSON format)

### Legacy Installation Steps

1. **Clone and setup the environment:**

   ```bash
   git clone https://github.com/johnatorres226/step1-nacc-validator.git
   cd step1-nacc-validator
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e .
   ```

2. **Configure your environment:**

   Create a `.env` file in the project root with the same content as shown above.

3. **Create required directories:**

   ```powershell
   mkdir output
   ```

4. **Verify installation:**

   ```powershell
   udsv4-qc --help
   udsv4-qc config
   ```

## 💻 Main Commands

The system provides two primary validation modes. Use Poetry commands for the best experience:

# Core Commands

```bash
# Display configuration status and validation
poetry run udsv4-qc config

# Execute QC validation pipeline
poetry run udsv4-qc --initials "YOUR_INITIALS"
```

### Main Validation Modes

```bash
# Validate complete visits (all instruments completed)
poetry run udsv4-qc --mode complete_visits --initials "ABC"

# Validate individual completed instruments
poetry run udsv4-qc --mode complete_instruments --initials "ABC"

# Custom validation with specific filters
poetry run udsv4-qc --mode custom --initials "ABC" --event "baseline_visit" --ptid "NACC123"
```

### Advanced Command Options

```bash
# Generate detailed outputs with coverage reports
poetry run udsv4-qc --mode complete_visits --initials "ABC" --detailed-run --passed-rules

# Specify custom output directory
poetry run udsv4-qc --mode complete_visits --initials "ABC" --output-dir "/custom/path"

# Enable verbose logging during execution
poetry run udsv4-qc --mode complete_visits --initials "ABC" --log

# Process specific events and participants
poetry run udsv4-qc --mode custom --initials "ABC" --event "baseline_visit" --event "followup_visit" --ptid "NACC123" --ptid "NACC456"
```

### Testing Commands

```bash
# Run all tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=qc_pipeline --cov-report=html

# Run specific test categories
poetry run pytest -m unit           # Unit tests only
poetry run pytest -m integration    # Integration tests only
poetry run pytest -m config         # Configuration tests only

# Run tests for specific components
poetry run pytest tests/test_configuration.py
poetry run pytest -k "validation"
```

### Command Parameters

- `--mode` - Validation mode (complete_visits, complete_instruments, custom)
- `--initials` - User initials for tracking and reporting (required)
- `--output-dir` - Custom output directory path
- `--event` - Specify specific REDCap events to process (can be used multiple times)
- `--ptid` - Target specific participant IDs (can be used multiple times)
- `--detailed-run` - Generate comprehensive output files including logs and reports
- `--passed-rules` - Include detailed validation logs (requires --detailed-run)
- `--log` - Enable verbose terminal logging during execution
- `--include-qced` - Include records that have already been QCed (custom mode only)

**For complete command reference and advanced usage, see [QUICK_START.md](QUICK_START.md)**

## 🔧 System Requirements

- **Operating System**: Windows 10/11, macOS, Linux (cross-platform support via Poetry)
- **Python Version**: 3.11 or higher
- **Package Manager**: Poetry (recommended) or pip
- **Memory**: 512MB minimum, 2GB recommended for large datasets
- **Storage**: 100MB for installation, additional space for output files and Poetry cache
- **Network**: Access to REDCap API endpoint and Poetry package repositories

### Poetry-Specific Requirements

- **Poetry**: Version 1.0+ for dependency management and virtual environment handling
- **Build Tools**: Automatically managed by Poetry for cross-platform compatibility
- **Virtual Environment**: Automatically created and managed by Poetry

## 🚀 Cross-Platform Compatibility

This project is designed to work seamlessly across different operating systems:

### Windows
- Native PowerShell and Command Prompt support
- Automatic virtual environment creation via Poetry
- Windows-specific dependency handling

### Linux/Unix
- Bash and shell script compatibility
- Native package compilation support
- System package integration

### macOS
- Homebrew integration potential
- Native macOS development support
- Apple Silicon compatibility

**Note**: Poetry ensures identical dependency resolution and virtual environments across all platforms.

## 🔐 Security Considerations

- Store API tokens securely in `.env` file (never commit to version control)
- Follow your organization's data handling policies for PHI/PII
- Review output files before sharing (may contain sensitive information)
- Ensure proper file permissions on validation rule directories

## 🤝 Contributing

We welcome contributions! Follow these guidelines for the best development experience:

### Development Setup

1. **Fork and clone the repository**
2. **Set up development environment with Poetry:**

   ```bash
   poetry install --with dev
   poetry shell
   ```

3. **Verify setup:**

   ```bash
   poetry run pytest
   poetry run black --check .
   poetry run flake8
   poetry run mypy src/
   ```

### Development Workflow

1. **Create a feature branch:**

   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes following these guidelines:**
   - Follow the existing code structure and architectural patterns
   - Add comprehensive tests for new features using pytest
   - Update documentation when making changes
   - Use type hints and docstrings consistently
   - Format code with Black: `poetry run black .`
   - Ensure linting passes: `poetry run flake8`
   - Verify type checking: `poetry run mypy src/`

3. **Test your changes:**

   ```powershell
   # Run all tests
   poetry run pytest
   
   # Run tests with coverage
   poetry run pytest --cov=qc_pipeline --cov-report=html
   
   # Run specific test categories
   poetry run pytest -m unit
   poetry run pytest -m integration
   ```

4. **Quality checks:**

   ```powershell
   # Code formatting
   poetry run black .
   
   # Linting
   poetry run ruff
   
   # Type checking
   poetry run mypy src/
   
   # Dependency security check
   poetry audit
   ```

5. **Commit and push:**

   ```bash
   git add .
   git commit -m "feat: description of your changes"
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request with:**
   - Clear description of changes
   - Test results and coverage information
   - Any breaking changes or migration notes

### Testing Guidelines

- **Unit Tests**: Test individual functions and methods
- **Integration Tests**: Test component interactions
- **Configuration Tests**: Test environment and setup scenarios
- **Cross-Platform Testing**: Verify functionality on Windows, Linux, macOS

### Code Quality Standards

- **Type Safety**: Use mypy for static type checking
- **Code Style**: Black formatting with 88-character line length
- **Linting**: Ruff for code quality checks
- **Documentation**: Comprehensive docstrings and comments
- **Testing**: Minimum 80% test coverage for new code

### Adding Dependencies

```bash
# Add runtime dependency
poetry add package-name

# Add development dependency
poetry add --group dev package-name

# Update lock file
poetry lock --no-update
```

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
