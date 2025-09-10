# Poetry Guide for UDSv4 REDCap QC Validator

## Overview

This document provides a comprehensive guide to using Poetry in the UDSv4 REDCap QC Validator project. Poetry is already configured and actively used for dependency management, virtual environment handling, and development workflow automation. This guide explains how Poetry enhances the project's cross-platform compatibility, dependency resolution, and development experience.

## Table of Contents

1. [What is Poetry?](#what-is-poetry)
2. [Project Poetry Configuration](#project-poetry-configuration)
3. [Installation and Setup](#installation-and-setup)
4. [Daily Development Workflow](#daily-development-workflow)
5. [Dependency Management](#dependency-management)
6. [Environment Management](#environment-management)
7. [CLI Integration](#cli-integration)
8. [Cross-Platform Usage](#cross-platform-usage)
9. [Build and Distribution](#build-and-distribution)
10. [Troubleshooting](#troubleshooting)

---

## What is Poetry?

Poetry is a modern dependency management and packaging tool for Python that provides deterministic dependency resolution, virtual environment management, and streamlined development workflows. In this project, Poetry is used to:

- **Manage Dependencies**: All project dependencies are defined in `pyproject.toml` with automatic lock file generation
- **Virtual Environment Management**: Automatic creation and management of isolated Python environments
- **Build System**: Modern Python packaging using PEP 517/518 standards
- **Development Workflow**: Streamlined commands for installation, testing, and package building
- **Cross-Platform Support**: Native support for Windows, Linux, and Unix systems

### Key Poetry Features Used in This Project

1. **Dual Configuration**: The project uses both traditional `[project]` sections and Poetry-specific `[tool.poetry]` sections for maximum compatibility
2. **Dependency Groups**: Separate development dependencies for testing, linting, and formatting tools
3. **CLI Integration**: The `udsv4-qc` command-line tool is configured through Poetry scripts
4. **Lock File**: `poetry.lock` ensures reproducible installations across all environments
5. **Modern Build System**: Uses Poetry Core as the build backend

### Essential Poetry Commands

```bash
# Install all dependencies (including dev)
poetry install

# Run the CLI tool
poetry run udsv4-qc --help

# Activate virtual environment
poetry shell

# Add a new dependency
poetry add package-name

# Add a development dependency
poetry add --group dev package-name

# Update dependencies
poetry update

# Build the package
poetry build
```

## Project Poetry Configuration

This project uses a hybrid Poetry configuration that maintains compatibility with both Poetry and standard Python packaging tools. The configuration is split between traditional project metadata and Poetry-specific settings.

### Current Dependencies Structure

**Core Dependencies** (defined in `[project.dependencies]`):

- **Data Processing**: `pandas`, `jsonschema`, `cerberus>=1.3.5`
- **Date/Time Handling**: `python-dateutil>=2.9.0`, `types-python-dateutil>=2.9.0.20240316`
- **Logic Operations**: `json-logic`
- **Configuration**: `python-dotenv`, `python-decouple`
- **HTTP Requests**: `requests`
- **CLI Framework**: `click>=8.0.0`, `rich>=13.0.0`, `typer>=0.9.0`
- **Development Tools**: `ipython`, `setuptools`

**Development Dependencies** (defined in `[tool.poetry.group.dev.dependencies]`):

- **Testing**: `pytest>=7.2.0`, `pytest-cov>=4.0.0`, `requests-mock>=1.12.1`
- **Code Quality**: `ruff>=0.12.0`, `black>=23.0.0`, `mypy>=1.0.0`
- **Development Tools**: `pre-commit>=3.0.0`, `wheel>=0.40.0`
- **Build/Distribution**: `build>=0.10.0`, `twine>=5.0.0`

### Package Structure Configuration

The project is configured to include multiple packages from different locations:

```toml
[tool.poetry]
packages = [
    { include = "pipeline", from = "src" },
    { include = "cli", from = "src" },
    { include = "nacc_form_validator" },
]
```

This configuration allows Poetry to:

- Include the `pipeline` module from the `src/` directory
- Include the `cli` module from the `src/` directory  
- Include the `nacc_form_validator` module from the project root
- Automatically handle package discovery and installation

## Installation and Setup

### Prerequisites

- Python 3.11 or higher (as specified in `requires-python = ">=3.11"`)
- Git (for cloning the repository)

### Installing Poetry

**Windows (PowerShell):**

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

**Linux/Unix (Bash):**

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**Alternative (using pip):**

```bash
pip install poetry
```

**Verify Installation:**

```bash
poetry --version
```

### Project Setup

1. **Clone the Repository:**

```bash
git clone https://github.com/johnatorres226/step1-nacc-validator.git
cd step1-nacc-validator
```

2. **Install Dependencies:**

```bash
# Install all dependencies (production + development)
poetry install

# Or install only production dependencies
poetry install --only main
```

3. **Verify Installation:**

```bash
# Test CLI functionality
poetry run udsv4-qc --help

# Check installed packages
poetry show
```

### Development Environment Setup

For active development, you may want to configure Poetry to create virtual environments within the project directory:

```bash
# Configure Poetry to use in-project virtual environments
poetry config virtualenvs.in-project true

# Reinstall to create .venv in project directory
poetry install
```

## Daily Development Workflow
### Common Development Tasks

**Starting Development:**

```bash
# Activate Poetry environment
poetry shell

# Or run commands directly
poetry run udsv4-qc --help
```

**Running the CLI Tool:**

```bash
# Run QC validation with Poetry
poetry run udsv4-qc config --detailed

# Run validation with parameters
poetry run udsv4-qc run --initials ABC --log

# Get help for any command
poetry run udsv4-qc --help
poetry run udsv4-qc run --help
```

**Development Tools:**

```bash
# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov

# Format code with Black
poetry run black .

# Lint code with Ruff
poetry run ruff check .

# Type checking with mypy
poetry run mypy src/

# Run pre-commit hooks
poetry run pre-commit run --all-files
```

**Working with Dependencies:**

```bash
# Add a new production dependency
poetry add pandas

# Add a development dependency
poetry add --group dev pytest-mock

# Update all dependencies
poetry update

# Update a specific dependency
poetry update pandas

# Remove a dependency
poetry remove package-name
```

## Dependency Management

### Understanding Dependency Configuration

This project uses a dual approach to dependency management for maximum compatibility:

1. **Standard Dependencies** (`[project.dependencies]`): Core runtime dependencies
2. **Poetry Development Dependencies** (`[tool.poetry.group.dev.dependencies]`): Development tools

### Adding New Dependencies

**Production Dependencies:**

For packages needed at runtime (like data processing libraries):

```bash
# Add to production dependencies
poetry add requests
poetry add "pandas>=1.5.0"
```

**Development Dependencies:**

For tools used only during development (testing, linting, etc.):

```bash
# Add to development dependencies
poetry add --group dev pytest-mock
poetry add --group dev "black>=23.0.0"
```

### Managing Dependency Versions

**Version Constraints:**

```bash
# Exact version
poetry add "package==1.2.3"

# Minimum version
poetry add "package>=1.2.0"

# Compatible version (will install latest 1.x.x)
poetry add "package~=1.2.0"

# Pessimistic version (will install latest 1.2.x)
poetry add "package~=1.2.1"
```

**Updating Dependencies:**

```bash
# Update all dependencies to latest compatible versions
poetry update

# Update specific dependency
poetry update pandas

# Update only development dependencies
poetry update --only dev
```

### Dependency Resolution and Lock File

The `poetry.lock` file ensures that everyone working on the project gets exactly the same dependency versions:

```bash
# Install exact versions from lock file
poetry install

# Update lock file after adding dependencies
poetry lock

# Check if lock file is up to date
poetry check
```

## Environment Management

### Virtual Environment Operations

**Creating and Managing Environments:**

```bash
# Show current environment information
poetry env info

# List all environments for this project
poetry env list

# Use a specific Python version
poetry env use python3.11
poetry env use python3.12

# Remove current environment
poetry env remove python
```

**Environment Configuration:**

```bash
# Configure Poetry to create .venv in project directory
poetry config virtualenvs.in-project true

# Configure Poetry to use system site packages
poetry config virtualenvs.system-site-packages true

# Check current configuration
poetry config --list
```

**Activating the Environment:**

```bash
# Method 1: Use poetry shell (recommended)
poetry shell

# Method 2: Run commands directly
poetry run python --version
poetry run udsv4-qc --help

# Method 3: Manual activation (if .venv exists in project)
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Linux/Unix
source .venv/bin/activate
```

## CLI Integration

The project's command-line interface is integrated with Poetry through the script configuration in `pyproject.toml`. The CLI tool (`udsv4-qc`) is available both as a Poetry-managed command and as an installed script.

### CLI Configuration

The CLI is configured in the project metadata:

```toml
[project.scripts]
udsv4-qc = "cli.cli:cli"
```

This means:

- **Entry Point**: The `cli` function in `cli.cli` module
- **Command Name**: `udsv4-qc`
- **Location**: `src/cli/cli.py`

### Using the CLI with Poetry

**Development Usage:**

```bash
# Run CLI through Poetry (recommended for development)
poetry run udsv4-qc --help

# Run configuration command
poetry run udsv4-qc config --detailed

# Run QC validation
poetry run udsv4-qc run --initials ABC --log --detailed-run
```

**Installed Usage:**

After running `poetry install`, the CLI is also available directly:

```bash
# If Poetry environment is activated
poetry shell
udsv4-qc --help

# Or in an activated virtual environment
udsv4-qc config --detailed
```

### CLI Development and Testing

**Testing CLI Changes:**

```bash
# Install in development mode
poetry install

# Test CLI functionality
poetry run udsv4-qc --help

# Test with different options
poetry run udsv4-qc config --json-output
poetry run udsv4-qc run --initials TST --dry-run
```

## Cross-Platform Usage

Poetry provides excellent cross-platform support, and this project is configured to work seamlessly on Windows, Linux, and Unix systems.

### Windows-Specific Features

**PowerShell Integration:**

```powershell
# Install Poetry on Windows
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# Setup project
poetry install

# Run CLI tool
poetry run udsv4-qc config --detailed
```

**Windows Environment Handling:**

- Poetry automatically handles Windows path separators
- Virtual environments are created in `%APPDATA%\pypoetry\virtualenvs\` by default
- PowerShell scripts are generated for environment activation

### Linux/Unix-Specific Features

**Shell Integration:**

```bash
# Install Poetry on Linux/Unix
curl -sSL https://install.python-poetry.org | python3 -

# Setup project
poetry install

# Run CLI tool
poetry run udsv4-qc config --detailed
```

**Unix Environment Handling:**

- Virtual environments are created in `~/.cache/pypoetry/virtualenvs/` by default
- Shell scripts are generated for environment activation
- Native compilation support for packages with C extensions

### Cross-Platform Development Tips

1. **Use Poetry Commands**: Always use `poetry run` for cross-platform compatibility
2. **Path Handling**: Poetry handles path differences automatically
3. **Environment Variables**: Use `python-dotenv` for environment-specific configuration
4. **File Permissions**: Poetry respects platform-specific file permissions

## Build and Distribution

### Building the Package

Poetry provides modern Python packaging capabilities:

```bash
# Build source distribution and wheel
poetry build

# Build only wheel
poetry build -f wheel

# Build only source distribution  
poetry build -f sdist
```

**Build Output:**

```
dist/
├── udsv4_redcap_qc_validator-0.1.0-py3-none-any.whl
└── udsv4_redcap_qc_validator-0.1.0.tar.gz
```

### Version Management

```bash
# Show current version
poetry version

# Bump patch version (0.1.0 -> 0.1.1)
poetry version patch

# Bump minor version (0.1.0 -> 0.2.0)
poetry version minor

# Bump major version (0.1.0 -> 1.0.0)
poetry version major

# Set specific version
poetry version 1.2.3
```

### Distribution Preparation

**Checking Build Configuration:**

```bash
# Verify project configuration
poetry check

# Show what would be included in build
poetry show --tree

# Dry run of build process
poetry build --dry-run
```

**Installing Built Package:**

```bash
# Install wheel locally for testing
pip install dist/udsv4_redcap_qc_validator-0.1.0-py3-none-any.whl

# Test installed package
udsv4-qc --help
```

## Troubleshooting

### Common Issues and Solutions

#### "poetry: The term 'poetry' is not recognized" Error

**Symptoms:**

- Running `poetry` in the terminal results in an error stating that the command is not recognized
- Commands like `poetry run udsv4-qc --help` fail with a similar error

**Cause:**

- Poetry is installed, but its executable (`poetry.exe` on Windows) is not on the system PATH
- This often happens when Poetry is installed via `pip` or in a user-local Python environment

**Resolution:**

The best solution is to uninstall Poetry and reinstall it using the official installer:

**Uninstall Poetry (PowerShell, Windows):**

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python - --uninstall
```

**Reinstall Poetry (PowerShell, Windows):**

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

After reinstalling, restart your terminal and verify the installation:

```powershell
poetry --version
```

#### Virtual Environment Issues

**Problem:** Poetry creates virtual environment in unexpected location

**Solution:**

```bash
# Configure Poetry to create .venv in project directory
poetry config virtualenvs.in-project true

# Recreate environment
poetry env remove python
poetry install
```

**Problem:** Multiple Python versions causing conflicts

**Solution:**

```bash
# Use specific Python version
poetry env use python3.11
poetry install

# Verify Python version in environment
poetry run python --version
```

#### Dependency Resolution Issues

**Problem:** Dependency conflicts during installation

**Solution:**

```bash
# Clear Poetry cache
poetry cache clear pypi --all

# Update lock file
poetry lock --no-update

# Try installing with more verbose output
poetry install -vvv
```

**Problem:** Package not found or version conflicts

**Solution:**

```bash
# Check current dependency tree
poetry show --tree

# Update specific package
poetry update package-name

# Remove and re-add problematic package
poetry remove package-name
poetry add package-name
```

#### CLI Issues

**Problem:** CLI command not working after Poetry installation

**Solution:**

```bash
# Verify CLI installation
poetry run udsv4-qc --help

# Check if package is properly installed
poetry show udsv4-redcap-qc-validator

# Reinstall in development mode
poetry install
```

**Problem:** CLI imports failing

**Solution:**

```bash
# Check Python path in Poetry environment
poetry run python -c "import sys; print(sys.path)"

# Verify package installation
poetry run python -c "import cli.cli; print('Success')"
```

### Getting Help

**Poetry Documentation:**

- Official Documentation: <https://python-poetry.org/docs/>
- CLI Reference: <https://python-poetry.org/docs/cli/>
- Configuration: <https://python-poetry.org/docs/configuration/>

**Project-Specific Help:**

```bash
# Check Poetry configuration
poetry config --list

# Verify project setup
poetry check

# Show dependency information
poetry show --tree

# Get environment information
poetry env info
```

**Debug Mode:**

```bash
# Run Poetry commands with verbose output
poetry install -vvv
poetry run -v udsv4-qc --help
```

---

## Summary

This guide provides comprehensive information about using Poetry in the UDSv4 REDCap QC Validator project. Poetry is already configured and provides:

- **Streamlined dependency management** with `poetry.lock` for reproducible environments
- **Cross-platform virtual environment handling** for Windows, Linux, and Unix
- **Integrated CLI tool management** with the `udsv4-qc` command
- **Modern Python packaging** using PEP 517/518 standards
- **Development workflow automation** with testing, linting, and formatting tools

**Key takeaways for daily use:**

1. **Use `poetry install`** to set up the development environment
2. **Use `poetry run udsv4-qc`** to run the CLI tool
3. **Use `poetry add`** to add new dependencies
4. **Use `poetry shell`** for interactive development
5. **Use `poetry build`** when preparing for distribution

Poetry enhances the development experience while maintaining compatibility with standard Python packaging tools, making this project accessible to developers regardless of their Poetry experience level.
