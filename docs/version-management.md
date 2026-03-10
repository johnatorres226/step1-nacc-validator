# Version Management Protocol

## Overview

This project uses a centralized version management system to maintain consistency across all version references and facilitate easy version updates.

## Version Location

**Single Source of Truth**: [`version.py`](../version.py)

All version information is stored in the `version.py` file at the project root. This file contains:
- `__version__`: The full version string (e.g., "0.1.0")
- `__version_info__`: Version as a tuple of integers
- `VERSION_MAJOR`, `VERSION_MINOR`, `VERSION_PATCH`: Individual version components

## Semantic Versioning

We follow [Semantic Versioning 2.0.0](https://semver.org/):

```
MAJOR.MINOR.PATCH

1.0.0 → Breaking changes (incompatible API changes)
0.1.0 → New features (backwards-compatible)
0.0.1 → Bug fixes (backwards-compatible)
```

### When to Increment

- **MAJOR**: Breaking changes, incompatible API modifications
- **MINOR**: New features, backwards-compatible functionality
- **PATCH**: Bug fixes, minor improvements, documentation updates

## Files That Reference Version

The version appears in multiple files:
1. `version.py` - **Primary source**
2. `pyproject.toml` - Poetry configuration
3. `src/pipeline/__init__.py` - Package metadata

## Updating Version

### Automated Method (Recommended)

Use the version update script:

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

The script will:
1. Validate the new version format
2. Update all relevant files
3. Show what was changed
4. Provide next steps for committing

### Manual Method

If you need to update manually:

1. **Update `version.py`**:
   ```python
   __version__ = "0.2.0"
   ```

2. **Update `pyproject.toml`**:
   ```toml
   [tool.poetry]
   version = "0.2.0"
   ```

3. **Update `src/pipeline/__init__.py`**:
   ```python
   __version__ = "0.2.0"
   ```

4. **Verify consistency**:
   ```bash
   grep -r "__version__" --include="*.py" --include="*.toml"
   ```

## Version Release Workflow

### Development Releases

For feature development on `dev` branch:

```bash
# Make changes
git checkout dev
# ... code changes ...

# Update version (if significant)
python scripts/update_version.py --patch

# Commit
git add .
git commit -m "feat: implement new feature"
git push origin dev
```

### Production Releases

For releases to `main`:

```bash
# Ensure all changes are merged to dev
git checkout dev
git pull

# Update version for release
python scripts/update_version.py --minor  # or --major

# Review changes
git diff

# Commit version bump
git add .
git commit -m "chore: bump version to $(grep '__version__' version.py | cut -d'"' -f2)"

# Create and push tag
export VERSION=$(grep '__version__' version.py | cut -d'"' -f2)
git tag -a "v$VERSION" -m "Release version $VERSION"
git push origin dev --tags

# Merge to main
git checkout main
git merge dev
git push origin main
```

## CI/CD Integration

### Build Workflow

The `build.yml` workflow:
- Builds the package using Poetry
- Validates package metadata
- Checks that version is consistent
- Creates distribution artifacts

### Version Validation

CI checks ensure:
- Version format follows semantic versioning
- Version is consistent across all files
- No development versions in production releases

## Version Queries

### Python Code

```python
# Import version
from version import __version__, __version_info__

print(f"Version: {__version__}")
print(f"Version info: {__version_info__}")
```

### Command Line

```bash
# Using the CLI
udsv4-qc --version

# Direct query
python -c "from version import __version__; print(__version__)"

# From pyproject.toml
poetry version
```

### CI/CD

```yaml
# In GitHub Actions
- name: Get version
  run: |
    VERSION=$(python -c "from version import __version__; print(__version__)")
    echo "VERSION=$VERSION" >> $GITHUB_ENV
```

## Version History

See [CHANGELOG.md](../CHANGELOG.md) for detailed version history and release notes.

## Pre-release Versions

For alpha/beta/rc releases, use suffixes:

```
0.1.0a1  - Alpha release 1
0.1.0b2  - Beta release 2
0.1.0rc3 - Release candidate 3
```

Update in `version.py`:
```python
__version__ = "0.1.0a1"
```

## Troubleshooting

### Version Mismatch

If you see version mismatches:

```bash
# Check all version references
grep -r "0\.\|[0-9]\+\.[0-9]\+\.[0-9]\+" \
  version.py pyproject.toml src/pipeline/__init__.py

# Use update script to fix
python scripts/update_version.py <correct-version>
```

### Build Failures

If build fails with version errors:

1. Verify `version.py` exists and is valid
2. Check `pyproject.toml` has the same version
3. Ensure version follows semantic versioning format
4. Run: `poetry build -vv` for detailed output

## Best Practices

1. **Always use the update script** for version changes
2. **Update version before merging to main**
3. **Tag releases** with the version number
4. **Update CHANGELOG.md** with version notes
5. **Test build** before pushing version changes
6. **Never manually edit multiple files** - use the script
7. **Keep versions in sync** across all files

## Questions?

- Review [semantic versioning](https://semver.org/)
- Check [Poetry versioning docs](https://python-poetry.org/docs/cli/#version)
- See the update script: `scripts/update_version.py`
