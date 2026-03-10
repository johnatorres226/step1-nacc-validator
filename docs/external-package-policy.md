# External Package Protection Policy

## Overview

This document outlines the policy for handling external packages in this repository, specifically the `nacc_form_validator` package.

## Protected Packages

### nacc_form_validator

**Status**: External Engine (Read-Only)
**Location**: `/nacc_form_validator`
**Purpose**: Core validation engine for NACC forms

#### Policy Rules

1. **NO MODIFICATIONS ALLOWED**: The `nacc_form_validator` package is an external engine that must not be modified in this repository.

2. **Updates**: Updates to this package will come from its upstream source. Do not make local changes.

3. **Bug Fixes**: If you find bugs in `nacc_form_validator`, report them to the upstream maintainers. Do not fix them locally.

4. **Testing**: Tests should not modify `nacc_form_validator` internals. Use mocking for external dependencies.

5. **Integration**: This package is integrated as-is. Our code should wrap or extend it, not modify it.

## Protection Mechanisms

### 1. Git Attributes
The `.gitattributes` file marks `nacc_form_validator` as vendored code:
- Excluded from diff statistics
- Marked as vendored/external for GitHub

### 2. CI/CD Checks
The CI workflow includes a check to prevent modifications:
- `check-external-packages.yml` workflow validates no changes to protected directories

### 3. Test Configuration
`pytest` is configured to skip `nacc_form_validator` during test discovery:
```toml
norecursedirs = ["nacc_form_validator", ...]
```

### 4. Linting Configuration
Linters ignore the external package directory:
- Ruff: Configured to skip `nacc_form_validator`
- Mypy: Configured to skip `nacc_form_validator`

## Enforcement

### Pre-commit Check
Run before committing:
```bash
python scripts/check_external_changes.py
```

### CI/CD Integration
Automated checks run on every pull request to ensure compliance.

## Violation Response

If modifications to `nacc_form_validator` are detected:
1. The CI build will fail
2. The pull request will be blocked
3. Developer must revert changes and address the issue through proper channels

## Questions?

If you need to modify validation logic:
1. Check if it can be done in `/src/pipeline/processors/`
2. Consider extending the validator rather than modifying it
3. Contact the team lead for guidance

## Future Updates

When upstream updates are available:
1. Download the new version from the official source
2. Replace the entire `nacc_form_validator` directory
3. Test the integration thoroughly
4. Update any compatibility notes in `COMPATIBILITY_RULE_FIX.md`
