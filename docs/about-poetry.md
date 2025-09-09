# Poetry Setup Plan for UDSv4 REDCap QC Validator

## Executive Summary

This document outlines the comprehensive migration strategy for transitioning the UDSv4 REDCap QC Validator project from traditional setuptools-based dependency management to Poetry. Poetry will enhance the project's cross-platform compatibility, dependency resolution, and development workflow while maintaining backward compatibility and improving reproducibility across Windows, Linux, and Unix systems.

## Table of Contents

1. [Poetry Overview](#poetry-overview)
2. [Current Project Analysis](#current-project-analysis)
3. [Migration Strategy](#migration-strategy)
4. [Poetry Configuration](#poetry-configuration)
5. [CLI Adjustments](#cli-adjustments)
6. [Cross-Platform Considerations](#cross-platform-considerations)
7. [Development Workflow](#development-workflow)
8. [Implementation Steps](#implementation-steps)
9. [Testing and Validation](#testing-and-validation)
10. [Benefits and Advantages](#benefits-and-advantages)
11. [Troubleshooting](#troubleshooting)

---

## Poetry Overview

### What is Poetry?

Poetry is a modern dependency management and packaging tool for Python that provides:

- **Dependency Resolution**: Deterministic dependency resolution with lock files
- **Virtual Environment Management**: Automatic virtual environment creation and management
- **Build System**: Modern Python packaging using PEP 517/518 standards
- **Cross-Platform Support**: Native support for Windows, Linux, and Unix systems
- **Development Workflow**: Streamlined development, testing, and publishing workflows

### Key Poetry Features

1. **pyproject.toml-based configuration**: Single configuration file for all project metadata
2. **poetry.lock file**: Ensures reproducible installations across environments
3. **Dependency groups**: Separate development, testing, and production dependencies
4. **Version management**: Semantic versioning with automatic version bumping
5. **Publishing**: Direct publishing to PyPI and private repositories
6. **Plugin system**: Extensible through plugins for enhanced functionality

### Poetry Commands Overview

- `poetry init`: Initialize a new Poetry project
- `poetry install`: Install dependencies from lock file
- `poetry add`: Add new dependencies
- `poetry remove`: Remove dependencies
- `poetry update`: Update dependencies
- `poetry build`: Build distributable packages
- `poetry publish`: Publish to repositories
- `poetry run`: Run commands in the virtual environment
- `poetry shell`: Activate virtual environment
- `poetry env`: Manage virtual environments

---

## Current Project Analysis

### Project Structure Analysis

The current project uses a hybrid approach with both `pyproject.toml` and `requirements.txt`:

```
Current Dependencies Management:
├── pyproject.toml (setuptools-based build system)
├── requirements.txt (pip-based dependency listing)
└── src/
    ├── cli/cli.py (Click-based CLI with entry point)
    └── pipeline/ (Core pipeline modules)
```

### Existing Dependencies

**Core Dependencies:**
- cerberus>=1.3.5 (Data validation)
- python-dateutil>=2.9.0 (Date/time utilities)
- json-logic (Logic operations)
- python-dotenv (Environment variables)
- jsonschema (JSON validation)
- pandas (Data manipulation)
- requests (HTTP requests)
- click>=8.0.0 (CLI framework)
- rich>=13.0.0 (Rich text output)
- typer>=0.9.0 (Modern CLI framework)

**Development Dependencies:**
- pytest>=7.2.0 (Testing framework)
- pytest-cov>=4.0.0 (Coverage reporting)
- black>=23.0.0 (Code formatting)
- flake8>=6.0.0 (Code linting)
- mypy>=1.0.0 (Type checking)

### CLI Configuration Analysis

**Current CLI Entry Point:**
```toml
[project.scripts]
udsv4-qc = "cli.cli:cli"
```

**CLI Structure:**
- Main command group: `cli()`
- Sub-commands: `config`, `run`
- Click-based framework with Rich console output
- Comprehensive option handling for QC operations

### Current Issues with Setup

1. **Dual dependency management**: Both pyproject.toml and requirements.txt
2. **Manual virtual environment management**: No automatic environment handling
3. **Build system complexity**: Manual setuptools configuration
4. **Dependency conflicts**: No deterministic dependency resolution
5. **Cross-platform issues**: Manual handling of platform-specific dependencies

---

## Migration Strategy

### Migration Approach

**Phase 1: Poetry Integration**
- Install Poetry
- Convert existing dependencies to Poetry format
- Generate poetry.lock file
- Test dependency resolution

**Phase 2: Configuration Migration**
- Update pyproject.toml for Poetry compatibility
- Remove requirements.txt dependencies
- Configure dependency groups
- Update build system configuration

**Phase 3: CLI and Entry Point Adjustment**
- Verify CLI entry points work with Poetry
- Test CLI functionality in Poetry environment
- Update development workflow documentation

**Phase 4: Testing and Validation**
- Cross-platform testing (Windows, Linux, Unix)
- Virtual environment testing
- Build and packaging testing
- CLI functionality validation

### Compatibility Considerations

1. **Python Version**: Current requirement `>=3.12` will be maintained
2. **Entry Points**: Existing CLI entry points will be preserved
3. **Package Structure**: Source layout in `src/` will be maintained
4. **Configuration Tools**: All existing tool configurations (black, mypy, pytest) will be preserved

---

## Poetry Configuration

### Updated pyproject.toml Structure

```toml
[tool.poetry]
name = "udsv4-redcap-qc-validator"
version = "0.1.0"
description = "QC validator for UDSv4 REDCap data"
license = "Mozilla Public License 2.0"
authors = ["John Torres <sdccunm.john@gmail.com>"]
maintainers = ["John Torres <sdccunm.john@gmail.com>"]
readme = "README.md"
homepage = "https://github.com/johnatorres226/step1-nacc-validator"
repository = "https://github.com/johnatorres226/step1-nacc-validator"
keywords = ["redcap", "qc", "validation", "udsv4", "nacc"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Science/Research",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Topic :: Scientific/Engineering :: Information Analysis",
]
packages = [
    { include = "pipeline", from = "src" },
    { include = "cli", from = "src" },
    { include = "nacc_form_validator" },
]

[tool.poetry.dependencies]
python = ">=3.12"
cerberus = ">=1.3.5"
python-dateutil = ">=2.9.0"
types-python-dateutil = ">=2.9.0.20240316"
json-logic = "*"
python-dotenv = "*"
python-decouple = "*"
jsonschema = "*"
pandas = "*"
requests = "*"
setuptools = "*"
ipython = "*"
click = ">=8.0.0"
rich = ">=13.0.0"
typer = ">=0.9.0"

[tool.poetry.group.dev.dependencies]
pytest = ">=7.2.0"
pytest-cov = ">=4.0.0"
black = ">=23.0.0"
flake8 = ">=6.0.0"
mypy = ">=1.0.0"
pre-commit = ">=3.0.0"
wheel = ">=0.40.0"
build = ">=0.10.0"
twine = ">=4.0.0"

[tool.poetry.scripts]
udsv4-qc = "cli.cli:cli"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

### Dependency Groups Strategy

**Production Dependencies (`[tool.poetry.dependencies]`)**:
- Core runtime dependencies required for the application to function

**Development Dependencies (`[tool.poetry.group.dev.dependencies]`)**:
- Testing, linting, formatting, and development tools
- Optional installation with `poetry install --with dev`

**Optional Dependency Groups** (Future Consideration):
```toml
[tool.poetry.group.docs.dependencies]
sphinx = "*"
sphinx-rtd-theme = "*"

[tool.poetry.group.performance.dependencies]
cython = "*"
numba = "*"
```

---

## CLI Adjustments

### Entry Point Configuration

**Current Entry Point:**
```toml
[project.scripts]
udsv4-qc = "cli.cli:cli"
```

**Poetry Entry Point:**
```toml
[tool.poetry.scripts]
udsv4-qc = "cli.cli:cli"
```

### CLI Functionality Verification

The existing Click-based CLI will work seamlessly with Poetry:

1. **Command Structure**: No changes required to existing commands
2. **Import Paths**: Relative imports will continue to work
3. **Entry Point**: Poetry scripts section maintains the same format
4. **Virtual Environment**: Poetry automatically handles environment activation

### Enhanced CLI Development

Poetry enables enhanced CLI development workflows:

```bash
# Run CLI in development environment
poetry run udsv4-qc --help

# Activate shell for development
poetry shell
udsv4-qc config --detailed

# Install in editable mode automatically
poetry install
```

---

## Cross-Platform Considerations

### Windows Support

**Poetry Installation on Windows:**
```powershell
# Using PowerShell (Recommended)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -

# Using pip (Alternative)
pip install poetry
```

**Windows-Specific Benefits:**
- Automatic virtual environment creation in user directory
- PowerShell script generation for environment activation
- Windows path handling in pyproject.toml
- Native dependency resolution for Windows packages

### Linux/Unix Support

**Poetry Installation on Linux/Unix:**
```bash
# Using curl (Recommended)
curl -sSL https://install.python-poetry.org | python3 -

# Using pip (Alternative)
pip install poetry
```

**Linux/Unix-Specific Benefits:**
- Automatic virtual environment creation in ~/.cache/pypoetry/
- Shell script generation for environment activation
- Native package compilation support
- System package integration

### Cross-Platform Dependency Management

Poetry automatically handles platform-specific dependencies:

```toml
[tool.poetry.dependencies]
# Platform-specific dependencies (if needed)
pywin32 = {version = "*", markers = "sys_platform == 'win32'"}
python-magic = {version = "*", markers = "sys_platform != 'win32'"}
```

### Environment Variables and Configuration

Poetry respects platform-specific environment variables:

```bash
# Configure Poetry behavior
poetry config virtualenvs.in-project true  # Create .venv in project directory
poetry config virtualenvs.prefer-active-python true  # Use active Python
```

---

## Development Workflow

### Daily Development Workflow

**Setup (One-time):**
```bash
# Clone repository
git clone <repository-url>
cd udsv4-redcap-qc-validator

# Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install
```

**Development Tasks:**
```bash
# Activate environment
poetry shell

# Run CLI commands
udsv4-qc config --detailed
udsv4-qc run --initials ABC --log

# Run tests
poetry run pytest

# Code formatting
poetry run black .

# Type checking
poetry run mypy src/

# Add new dependency
poetry add requests

# Add development dependency
poetry add --group dev pytest-mock

# Update dependencies
poetry update

# Build package
poetry build
```

### Environment Management

**Virtual Environment Commands:**
```bash
# Show environment info
poetry env info

# List environments
poetry env list

# Remove environment
poetry env remove python

# Use specific Python version
poetry env use python3.12
```

### Dependency Management

**Adding Dependencies:**
```bash
# Add production dependency
poetry add pandas

# Add development dependency
poetry add --group dev black

# Add with version constraints
poetry add "click>=8.0.0,<9.0.0"

# Add from git
poetry add git+https://github.com/user/repo.git

# Add local package
poetry add ./local-package
```

**Updating Dependencies:**
```bash
# Update all dependencies
poetry update

# Update specific dependency
poetry update pandas

# Update development dependencies only
poetry update --only dev
```

---

## Implementation Steps

### Step 1: Install Poetry

**Windows (PowerShell):**
```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

**Linux/Unix (Bash):**
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**Verify Installation:**
```bash
poetry --version
```

### Step 2: Initialize Poetry in Project

```bash
# Navigate to project directory
cd "c:\Users\johtorres\Documents\Github_Repos\final-projects\(Step 1) udsv4-redcap-qc-validator"

# Initialize Poetry (using existing pyproject.toml)
poetry install --dry-run  # Test dependency resolution
```

### Step 3: Update pyproject.toml

1. **Backup current pyproject.toml**
2. **Update build system section**:
   ```toml
   [build-system]
   requires = ["poetry-core"]
   build-backend = "poetry.core.masonry.api"
   ```
3. **Convert project section to tool.poetry**
4. **Organize dependencies into groups**

### Step 4: Generate Lock File

```bash
# Generate poetry.lock file
poetry lock

# Verify lock file generation
poetry check
```

### Step 5: Install Dependencies with Poetry

```bash
# Install all dependencies
poetry install

# Install only production dependencies
poetry install --only main

# Install with development dependencies
poetry install --with dev
```

### Step 6: Test CLI Functionality

```bash
# Test CLI entry point
poetry run udsv4-qc --help

# Test CLI commands
poetry run udsv4-qc config --detailed

# Activate shell and test
poetry shell
udsv4-qc --version
```

### Step 7: Update Development Workflow

1. **Update documentation** for Poetry usage
2. **Create development setup scripts**
3. **Update CI/CD configuration** (if applicable)
4. **Train team members** on Poetry workflow

### Step 8: Remove Legacy Files

1. **Remove requirements.txt** (after verifying Poetry setup)
2. **Clean up old virtual environments**
3. **Update .gitignore** for Poetry-specific files

---

## Testing and Validation

### Pre-Migration Testing

**Current System Validation:**
```bash
# Test current setup
python -m pip list
python -c "import cli.cli; print('CLI imports successfully')"
python src/cli/cli.py --help
```

### Post-Migration Testing

**Poetry Setup Validation:**
```bash
# Verify Poetry configuration
poetry check

# Test dependency installation
poetry install --dry-run

# Validate lock file
poetry lock --check

# Test CLI functionality
poetry run udsv4-qc --help
poetry run udsv4-qc config --detailed
```

### Cross-Platform Testing

**Windows Testing:**
```powershell
# Test Poetry installation
poetry --version

# Test project setup
poetry install
poetry run udsv4-qc --help

# Test virtual environment
poetry shell
where python
python --version
```

**Linux/Unix Testing:**
```bash
# Test Poetry installation
poetry --version

# Test project setup
poetry install
poetry run udsv4-qc --help

# Test virtual environment
poetry shell
which python
python --version
```

### Functional Testing

**CLI Command Testing:**
```bash
# Test configuration command
poetry run udsv4-qc config --detailed --json-output

# Test run command (with appropriate parameters)
poetry run udsv4-qc run --initials TST --log --detailed-run

# Test help documentation
poetry run udsv4-qc --help
poetry run udsv4-qc run --help
```

### Performance Testing

**Dependency Resolution:**
```bash
# Time dependency installation
time poetry install

# Compare with pip installation
time pip install -r requirements.txt
```

**Build Testing:**
```bash
# Test package building
poetry build

# Verify build artifacts
ls dist/
```

---

## Benefits and Advantages

### Immediate Benefits

1. **Deterministic Dependencies**: poetry.lock ensures identical dependency versions across environments
2. **Simplified Environment Management**: Automatic virtual environment creation and activation
3. **Enhanced Cross-Platform Support**: Native support for Windows, Linux, and Unix systems
4. **Streamlined Development Workflow**: Single command installation and dependency management
5. **Better Dependency Resolution**: Automatic conflict resolution and compatibility checking

### Long-term Advantages

1. **Improved Reproducibility**: Guaranteed identical environments across development, testing, and production
2. **Enhanced Collaboration**: Team members get identical development environments
3. **Simplified CI/CD**: Consistent dependency installation in automated pipelines
4. **Better Package Management**: Version constraints and dependency groups for different use cases
5. **Modern Python Packaging**: Compliance with latest Python packaging standards (PEP 517/518)

### Development Experience Improvements

1. **Faster Setup**: Single `poetry install` command sets up complete development environment
2. **Dependency Insights**: Clear dependency tree visualization with `poetry show --tree`
3. **Version Management**: Automatic semantic versioning with `poetry version`
4. **Publishing Workflow**: Direct publishing to PyPI with `poetry publish`
5. **Plugin Ecosystem**: Extensible functionality through Poetry plugins

### Cross-Platform Benefits

**Windows:**
- Native PowerShell integration
- Automatic Windows-specific dependency handling
- Proper handling of Windows paths and file systems

**Linux/Unix:**
- Native shell integration
- System package integration
- Proper handling of Unix permissions and paths

**macOS:**
- Homebrew integration
- Native macOS development support
- Apple Silicon compatibility

---

## Conclusion

The migration to Poetry will significantly enhance the UDSv4 REDCap QC Validator project by providing:

1. **Modern dependency management** with deterministic resolution
2. **Cross-platform compatibility** for Windows, Linux, and Unix systems
3. **Streamlined development workflow** for better team collaboration
4. **Improved reproducibility** across different environments
5. **Future-proof packaging** using modern Python standards

The migration process is designed to be **non-disruptive** with **backward compatibility** maintained throughout the transition. The existing CLI functionality will remain unchanged while benefiting from Poetry's enhanced environment management.

This setup plan provides a comprehensive roadmap for successful Poetry adoption, ensuring the project becomes more maintainable, reproducible, and accessible to developers across different platforms and environments.

---

## Troubleshooting

### "poetry: The term 'poetry' is not recognized" Error

#### Symptoms
- Running `poetry` in the terminal results in an error stating that the command is not recognized.
- Commands like `poetry run udsv4-qc --help` fail with a similar error.

#### Cause
- Poetry is installed, but its executable (`poetry.exe` on Windows) is not on the system PATH.
- This often happens when Poetry is installed via `pip` or in a user-local Python environment, and the Scripts directory is not added to PATH.

#### Resolution
The best solution is to uninstall Poetry and reinstall it using the official installer, which ensures the executable is placed in a standard location and added to your PATH automatically.

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

#### Note on Initial Poetry Installation and PATH

When installing Poetry for the first time, ensure that the Poetry executable is available in your terminal by adding it to your system PATH. If the installer does not do this automatically, you can add it manually in PowerShell:

```powershell
$poetryPath = Join-Path $env:APPDATA 'pypoetry\venv\Scripts'
[Environment]::SetEnvironmentVariable(
   'Path',
   [Environment]::GetEnvironmentVariable('Path','User') + ';' + $poetryPath,
   'User'
)
```

After running this command, restart your terminal to use the `poetry` command globally.

#### Prevention
- Use the official Poetry installer (https://install.python-poetry.org) to ensure the executable is placed in a standard location.
- Configure Poetry to create virtual environments inside the project directory:
  ```bash
  poetry config virtualenvs.in-project true
  ```
- Verify that the Python Scripts directory is added to your PATH after installation.
