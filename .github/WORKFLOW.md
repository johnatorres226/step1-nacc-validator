# CI/CD Workflow Guide

This document describes the CI/CD workflow for the UDSv4 REDCap QC Validator project.

## Branch Strategy

### `main` Branch
- **Production-ready code only**
- Protected branch with strict requirements
- All changes must go through Pull Requests from `dev`
- Requires:
  - Updated CHANGELOG.md
  - Version bump in pyproject.toml
  - All CI checks passing

### `dev` Branch
- **Active development branch**
- All feature branches should be merged here first
- Less restrictive CI checks (linting continues on error)
- Testing ground before merging to main

### Feature Branches
- Create from `dev` branch
- Name format: `feature/description`, `fix/description`, etc.
- Merge back to `dev` via Pull Request

## Workflow

```
feature branch → dev → main → release/tag
```

1. **Development**: Create feature branch from `dev`, make changes
2. **Testing**: Open PR to `dev`, CI runs with lenient checks
3. **Merge to dev**: After review and CI passes
4. **Prepare for release**: Open PR from `dev` to `main`
5. **Release**: After merging to `main`, create a git tag to trigger release

## GitHub Actions Workflows

### 1. CI (`ci.yml`)
**Triggers**: Push to `dev`, PRs to `dev` or `main`

**Jobs**:
- **Test**: Runs pytest on Python 3.11, 3.12, 3.13
  - Only tests code in `src/` (excludes `nacc_form_validator`)
  - Uploads coverage to Codecov
- **Lint**: Runs Ruff linter and formatter
  - Only lints `src/` and `tests/` (excludes `nacc_form_validator`)
  - Continues on error (non-blocking)
- **Type Check**: Runs mypy type checking
  - Only checks `src/` (excludes `nacc_form_validator`)

### 2. Main Branch Checks (`main-checks.yml`)
**Triggers**: PRs to `main`, pushes to `main`

**Jobs**:
- **Changelog/Version Check** (PR only):
  - Verifies CHANGELOG.md was updated
  - Verifies version was bumped in pyproject.toml
  - Validates version format (semantic versioning)
- **Run All Checks**: Full test suite with strict requirements
  - All linting must pass (no continue-on-error)
  - All tests must pass
  - Type checking must pass

### 3. Build (`build.yml`)
**Triggers**: Push to `dev`, PRs to `main` or `dev`

**Jobs**:
- **Build Package**: 
  - Installs dependencies with Poetry
  - Builds wheel and source distribution
  - Validates package with twine
  - Tests package installation
  - Uploads artifacts (7-day retention)

### 4. Release (`release.yml`)
**Triggers**: Tags starting with `v*` (e.g., `v0.2.0`)

**Jobs**:
- **Build and Release**:
  - Builds distribution packages
  - Extracts version-specific changelog
  - Creates GitHub Release with artifacts
  - Marks pre-releases if version contains `-` (e.g., `v0.2.0-beta`)
  - Uploads artifacts with 90-day retention
  - Generates build summary

## Code Organization

### Linting and Testing Scope

The following are **EXCLUDED** from linting and testing:
- `nacc_form_validator/` - Third-party validation engine (kept intact)

The following are **INCLUDED** in linting and testing:
- `src/` - All project source code
- `tests/` - All test files

Configuration:
- **ruff.toml**: Excludes `nacc_form_validator/**` from linting
- **mypy.ini**: Excludes `nacc_form_validator/.*` from type checking
- **pytest**: Test coverage only includes `src/`

## Making a Release

### Step 1: Prepare Changes on Dev
```bash
git checkout dev
git pull origin dev
# Make your changes
git add .
git commit -m "feat: description of changes"
git push origin dev
```

### Step 2: Update Changelog and Version
Before merging to main:
1. Edit `CHANGELOG.md`:
   ```markdown
   ## [0.2.0] - 2026-02-13
   ### Added
   - New feature X
   - New validation rule Y
   
   ### Fixed
   - Bug in module Z
   ```

2. Edit `pyproject.toml`:
   ```toml
   version = "0.2.0"  # Update from 0.1.0
   ```

### Step 3: Create PR to Main
```bash
git checkout -b release/v0.2.0
git add CHANGELOG.md pyproject.toml
git commit -m "chore: prepare release v0.2.0"
git push origin release/v0.2.0
```
Create PR from `release/v0.2.0` to `main`

### Step 4: Create Release Tag
After PR is merged to main:
```bash
git checkout main
git pull origin main
git tag -a v0.2.0 -m "Release version 0.2.0"
git push origin v0.2.0
```

This triggers the Release workflow which:
- Builds the package
- Creates a GitHub Release
- Attaches distribution files
- Publishes release notes from CHANGELOG.md

## Semantic Versioning

Follow [Semantic Versioning](https://semver.org/):
- **MAJOR** (X.0.0): Breaking changes
- **MINOR** (0.X.0): New features (backwards compatible)
- **PATCH** (0.0.X): Bug fixes (backwards compatible)
- **Pre-release** (0.0.0-alpha.1): Development versions

## CI Configuration Notes

### Less Restrictive on Dev
- Linting errors don't fail the build (`continue-on-error: true`)
- Allows for experimentation and rapid development
- Encourages frequent commits

### Strict on Main
- All checks must pass
- Changelog and version must be updated
- Ensures production-ready code quality

### No Testing of `nacc_form_validator`
- This module is a third-party validation engine
- Maintained separately and kept intact
- Only project code in `src/` is tested and linted
