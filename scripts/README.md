# Scripts Directory

This directory contains utility scripts for project maintenance and automation.

## Available Scripts

### Version Management

#### `update_version.py`
**Purpose**: Update project version across all files

**Usage**:
```bash
# Increment patch version (0.1.0 → 0.1.1)
python scripts/update_version.py --patch

# Increment minor version (0.1.0 → 0.2.0)
python scripts/update_version.py --minor

# Increment major version (0.1.0 → 1.0.0)
python scripts/update_version.py --major

# Set specific version
python scripts/update_version.py 1.5.2
```

**What it does**:
- Validates version format (semantic versioning)
- Updates `version.py`
- Updates `pyproject.toml`
- Updates `src/pipeline/__init__.py`
- Provides git commit guidance

**See also**: [docs/version-management.md](../docs/version-management.md)

---

### External Package Protection

#### `check_external_changes.py`
**Purpose**: Prevent unauthorized modifications to external packages

**Usage**:
```bash
# Run manually
python scripts/check_external_changes.py

# In pre-commit hook
python scripts/check_external_changes.py || exit 1
```

**What it does**:
- Checks staged and uncommitted changes
- Validates no modifications to `nacc_form_validator`
- Enforces external package policy
- Exits with error if violations detected

**Protected directories**:
- `nacc_form_validator/` (external validation engine)

**See also**: [docs/external-package-policy.md](../docs/external-package-policy.md)

---

## Integration with Development Workflow

### Pre-commit Checks

Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
echo "Checking for external package modifications..."
python scripts/check_external_changes.py || exit 1
```

### CI/CD Integration

These scripts are integrated in GitHub Actions workflows:
- `check_external_changes.py` → `.github/workflows/check-external-packages.yml`
- Version validation → `.github/workflows/build.yml`

### Development Guidelines

1. **Before committing**:
   ```bash
   # Check for external package changes
   python scripts/check_external_changes.py
   ```

2. **Before releasing**:
   ```bash
   # Update version
   python scripts/update_version.py --minor
   
   # Review changes
   git diff
   
   # Build and test
   poetry build
   poetry run twine check dist/*
   ```

3. **After version update**:
   ```bash
   # Commit version change
   git add .
   git commit -m "chore: bump version to X.Y.Z"
   
   # Tag release
   git tag vX.Y.Z
   git push origin --tags
   ```

## Adding New Scripts

When adding new scripts to this directory:

1. **Use proper shebang**: `#!/usr/bin/env python3`
2. **Add docstrings**: Explain purpose and usage
3. **Include CLI help**: Use `argparse` with helpful messages
4. **Handle errors gracefully**: Provide clear error messages
5. **Document here**: Add section above
6. **Make executable** (on Unix): `chmod +x scripts/your_script.py`

## Requirements

Scripts in this directory should:
- Use only standard library when possible
- Document any external dependencies
- Work from project root directory
- Provide clear feedback to users
- Exit with appropriate status codes

## Troubleshooting

### Permission Errors
```bash
# On Unix-like systems, make scripts executable
chmod +x scripts/*.py
```

### Module Import Errors
```bash
# Run scripts from project root
cd /path/to/project
python scripts/script_name.py
```

### Path Issues
Scripts expect to run from project root and will adjust paths accordingly.

## Questions?

- Check individual script help: `python scripts/script_name.py --help`
- Review related documentation in `docs/`
- Contact the development team
