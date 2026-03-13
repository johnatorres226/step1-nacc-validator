# GitHub Actions Workflow Documentation

## Overview

This project uses a streamlined **two-workflow approach** for Continuous Integration (CI) and Continuous Deployment (CD), optimized to minimize redundancy and provide fast feedback.

## Workflows

### 1. CI Workflow (`ci.yml`)

**Purpose:** Validate code quality, run tests, and verify package builds on every push and pull request.

**Triggers:**
- Push to `dev` and `codebase-curation` branches
- Pull requests targeting `main` or `dev` branches

**Jobs:**

#### `check-external-packages`
- **Duration:** ~10 seconds
- **Purpose:** Enforce external package policy
- Validates that no unauthorized changes are made to the `nacc_form_validator/` directory
- See [external-package-policy.md](external-package-policy.md) for details

#### `pr-to-main-checks`
- **Duration:** ~15 seconds
- **Condition:** Only runs on PRs targeting `main`
- **Purpose:** Enforce release standards
- Verifies `CHANGELOG.md` was updated
- Verifies version was bumped in `pyproject.toml`
- Validates version format (MAJOR.MINOR.PATCH)

#### `test`
- **Duration:** ~40-60 seconds
- **Strategy:** Matrix across Python 3.11, 3.12, 3.13
- **Purpose:** Run comprehensive test suite
- Executes pytest with coverage reporting
- Uploads coverage to Codecov (Python 3.12 only)
- Uses Poetry dependency caching for speed

#### `lint`
- **Duration:** ~15-20 seconds
- **Purpose:** Code style and quality checks
- Runs Ruff linter
- Runs Ruff formatter check
- Uses configuration from `ruff.toml`

#### `type-check`
- **Duration:** ~20-25 seconds
- **Purpose:** Static type analysis
- Runs mypy type checker
- Uses configuration from `mypy.ini`

#### `build-verify`
- **Duration:** ~30-40 seconds
- **Purpose:** Verify package builds correctly
- Builds wheel and source distribution with Poetry
- Validates package metadata with `poetry check`
- Tests package installation
- Uploads build artifacts (retained 7 days)

**Total CI Duration:** ~2-3 minutes (parallel execution)

---

### 2. Release Workflow (`release.yml`)

**Purpose:** Build, validate, and publish releases to GitHub.

**Triggers:**
- Push of tags matching `v*.*.*` (e.g., `v1.0.0`, `v1.2.3`)

**Jobs:**

#### `release`
- **Duration:** ~35-45 seconds
- **Purpose:** Create official releases
- Validates tag version matches `pyproject.toml` version
- Builds wheel and source distribution
- Validates package metadata
- Extracts relevant section from `CHANGELOG.md`
- Creates GitHub Release with artifacts
- Uploads release artifacts (retained 90 days)
- Marks as prerelease if version contains: `-`, `alpha`, `beta`, or `rc`

**Total Release Duration:** ~40-50 seconds

---

## Workflow Optimization

### What Changed (Option A Implementation)

**Previous State:** 5 separate workflows
- `ci.yml` - Tests and linting on dev/feature branches
- `build.yml` - Package building on dev/feature branches
- `main-checks.yml` - Duplicate tests + changelog checks on main
- `check-external-packages.yml` - External package validation
- `release.yml` - Release creation on every main push + tags

**Issues with Previous Approach:**
- ❌ Every `main` push triggered 3 workflows simultaneously
- ❌ Tests ran twice (CI on PR + Main Checks on merge)
- ❌ Package building duplicated (Build + Release)
- ❌ Release workflow ran on every main push, not just tags
- ❌ ~60-70% wasted CI time

**New State:** 2 consolidated workflows
- `ci.yml` - All validation (tests, lint, type-check, build, external checks, PR checks)
- `release.yml` - Release only (triggers on tags only)

**Benefits:**
- ✅ 60-70% reduction in workflow runs
- ✅ Clear separation: CI validates, Release deploys
- ✅ No duplication of jobs
- ✅ Faster feedback (1 workflow per event vs 3)
- ✅ Easier to maintain and understand
- ✅ Industry-standard CI/CD pattern

---

## Usage Examples

### Development Workflow

1. **Create feature branch:**
   ```bash
   git checkout -b feature/my-feature dev
   ```

2. **Make changes and push:**
   ```bash
   git push origin feature/my-feature
   ```
   - ✓ CI workflow runs (no PR checks since not targeting main)

3. **Create PR to dev:**
   - ✓ CI workflow runs again with latest changes
   - Tests, lint, type-check, build verification

4. **Merge to dev:**
   - ✓ CI workflow runs on dev branch
   - Validates everything still works

### Release Workflow

1. **Prepare release on dev:**
   ```bash
   # Update version in pyproject.toml
   version = "1.2.0"
   
   # Update CHANGELOG.md with new version section
   ## [1.2.0] - 2026-03-13
   ### Added
   - New feature X
   ```

2. **Create PR to main:**
   ```bash
   git checkout -b release/v1.2.0 dev
   git push origin release/v1.2.0
   # Create PR: release/v1.2.0 → main
   ```
   - ✓ CI workflow runs with ALL jobs
   - ✓ `pr-to-main-checks` validates changelog and version
   - ✓ All tests, lint, type-check, build verification

3. **Merge PR to main:**
   ```bash
   git checkout main
   git pull origin main
   ```
   - ✓ CI workflow runs (no PR checks this time)

4. **Create and push tag:**
   ```bash
   git tag v1.2.0
   git push origin v1.2.0
   ```
   - ✓ Release workflow triggers
   - Builds package
   - Creates GitHub Release
   - Attaches wheel and source distribution

---

## Configuration Files

### Workflow Configurations
- `.github/workflows/ci.yml` - CI workflow definition
- `.github/workflows/release.yml` - Release workflow definition
- `.github/workflows/archived/` - Old workflows (preserved for reference)

### Tool Configurations
- `pyproject.toml` - Poetry dependencies and project metadata
- `ruff.toml` - Ruff linter/formatter configuration
- `mypy.ini` - mypy type checker configuration
- `.github/dependabot.yml` - Dependency update automation (if present)

---

## Troubleshooting

### CI Failing

**External Package Check Failed:**
- Error indicates changes to `nacc_form_validator/`
- This is intentional - see [external-package-policy.md](external-package-policy.md)
- Revert changes to external packages

**PR to Main Check Failed:**
- Ensure `CHANGELOG.md` is updated with new version section
- Ensure version in `pyproject.toml` is bumped
- Version must follow MAJOR.MINOR.PATCH format

**Tests Failing:**
- Run tests locally: `poetry run pytest tests/ -v`
- Check coverage: `poetry run pytest tests/ --cov=src`

**Lint/Format Failing:**
- Run locally: `poetry run ruff check src tests`
- Auto-fix: `poetry run ruff check --fix src tests`
- Format: `poetry run ruff format src tests`

**Type Check Failing:**
- Run locally: `poetry run mypy --config-file mypy.ini src`
- Add type hints or ignore comments as needed

**Build Verification Failed:**
- Clean build: `rm -rf dist/ build/ *.egg-info`
- Rebuild: `poetry build`
- Validate: `poetry check`

### Release Failing

**Version Mismatch:**
- Error: "Tag version (vX.Y.Z) does not match pyproject.toml version"
- Ensure tag version matches exactly (no `v` prefix in pyproject.toml)
- Example: Tag `v1.2.0` → `pyproject.toml` version = `"1.2.0"`

**Changelog Extraction Failed:**
- Warning: "No specific changelog entry found"
- Ensure `CHANGELOG.md` has section: `## [X.Y.Z] - YYYY-MM-DD`
- Format must match exactly for automatic extraction

**Release Not Created:**
- Verify tag was pushed: `git push origin vX.Y.Z`
- Check workflow runs: `gh run list --workflow=release.yml`
- View workflow logs: `gh run view <run-id> --log`

---

## Monitoring

### Check Workflow Status

```bash
# List recent workflow runs
gh run list --limit 10

# Watch live workflow run
gh run watch

# View specific run
gh run view <run-id>

# View failed logs
gh run view <run-id> --log-failed
```

### Check CI Status

```bash
# Status of latest CI run
gh run list --workflow=ci.yml --limit 1

# View CI logs
gh run view $(gh run list --workflow=ci.yml --limit 1 --json databaseId --jq '.[0].databaseId') --log
```

### Check Release Status

```bash
# List releases
gh release list

# View specific release
gh release view v1.2.0

# List release workflow runs
gh run list --workflow=release.yml --limit 5
```

---

## Best Practices

### For Contributors

1. **Always run checks locally before pushing:**
   ```bash
   poetry run pytest tests/ -v
   poetry run ruff check src tests
   poetry run mypy src
   ```

2. **Keep commits focused:**
   - One logical change per commit
   - Clear, descriptive commit messages

3. **Update documentation:**
   - If changing behavior, update relevant docs
   - Keep CHANGELOG.md current on dev branch

### For Maintainers

1. **PR Reviews:**
   - Wait for all CI checks to pass
   - Review PR-to-main checks output (changelog, version)
   - Verify version bump is appropriate (major/minor/patch)

2. **Releases:**
   - Always release from main branch
   - Tag format: `vMAJOR.MINOR.PATCH`
   - Verify CHANGELOG.md has proper version section
   - Test locally before tagging: `poetry build && poetry check`

3. **Workflow Maintenance:**
   - Review workflow runs weekly
   - Monitor for flaky tests
   - Update actions/dependencies quarterly
   - Keep Python version matrix current with supported versions

---

## Archived Workflows

Previous workflow files are preserved in `.github/workflows/archived/` for reference:
- `ci.yml.old` - Original CI workflow
- `build.yml.old` - Separate build workflow
- `main-checks.yml.old` - Main branch protection checks
- `check-external-packages.yml.old` - External package validation
- `release.yml.old` - Original release workflow

These files are kept for historical reference and can be safely deleted after confirming the new workflows are stable.

---

## Related Documentation

- [Version Management](version-management.md) - Versioning strategy and changelog guidelines
- [External Package Policy](external-package-policy.md) - Rules for external dependencies
- [About Poetry](about-poetry.md) - Poetry dependency management
- [Guidelines](guidelines.md) - General development guidelines

---

## Changelog

### 2026-03-13 - Workflow Consolidation (Option A)
- **Consolidated** 5 workflows into 2 (CI + Release)
- **Removed** redundant job execution
- **Optimized** CI workflow with parallel job execution
- **Changed** release trigger from main pushes to tags only
- **Improved** workflow naming for clarity
- **Added** comprehensive workflow documentation

**Impact:** ~60-70% reduction in workflow runs, faster feedback, clearer separation of CI/CD.
