# External Package Protection Policy

## Overview

This document outlines the policy for handling external packages in this repository, specifically the `nacc_form_validator` package.

## Protected Packages

### nacc_form_validator

**Status**: External Engine — tracked local patches permitted under approval process (see below)
**Location**: `/nacc_form_validator`
**Purpose**: Core validation engine for NACC forms

#### Policy Rules

1. **MODIFICATIONS REQUIRE APPROVAL**: The `nacc_form_validator` package is an external engine. Direct modifications are strongly discouraged and require explicit justification, team-lead approval, and registration in the approved patch list (see *Approved Local Patches* section).

2. **Prefer upstream**: Before patching locally, report the bug upstream. If the upstream fix is available and verified, update the entire directory rather than patching individual files.

3. **Bug fixes — local patch process**: When an upstream bug directly blocks production correctness and no upstream fix is available in a reasonable timeframe, a local patch is permitted provided:
   - The bug, root cause, and fix are documented here and in `ci.yml`
   - The file is added to `ALLOWED_PATCHES` in `ci.yml` before committing
   - The change is committed with a `fix(vendored):` prefix describing the patch
   - The upstream issue is tracked for future replacement when upstream ships the fix

4. **Testing**: Tests should not modify `nacc_form_validator` internals. Use mocking for external dependencies.

5. **Integration**: Any logic that can be implemented in `/src/pipeline/` must be placed there, not in this package.

## Protection Mechanisms

### 1. Git Attributes
The `.gitattributes` file marks `nacc_form_validator` as `linguist-vendored` (excluded from GitHub language statistics). The `-diff` attribute is **not** set so patches remain readable in PR reviews.

### 2. CI/CD Checks
`ci.yml` (`check-external-packages` job) enforces an **allowlist** model:
- Any file under `nacc_form_validator/` that is not explicitly listed in `ALLOWED_PATCHES` (in `ci.yml`) will **fail CI**.
- To permit a new patch, add the file path and justification comment to `ALLOWED_PATCHES` in `ci.yml` in the same commit.

### 3. Test Configuration
`pytest` is configured to skip `nacc_form_validator` during test discovery:
```toml
norecursedirs = ["nacc_form_validator", ...]
```

### 4. Linting Configuration
Linters ignore the external package directory:
- Ruff: Configured to skip `nacc_form_validator`
- Mypy: Configured to skip `nacc_form_validator`

## Approved Local Patches

### `nacc_form_validator/nacc_validator.py`

| Field | Detail |
|---|---|
| **Date** | 2026-04-01 |
| **Branch** | `debug-shortcoming` |
| **Upstream bug** | `_validate_compatibility` silently swallows THEN-field failures when the THEN field is absent/null in the record |
| **Root cause** | `_check_subschema_valid` returns `(valid=False, errors={})` when the THEN field is missing. The caller's `if errors:` guard evaluates to `False` → no `_error()` call. Cross-form completeness rules (e.g. B5 `depd=1` but B9 `bedep` not filled in) fire zero errors. |
| **Impact** | B5→B9, D1A, D1B, B9 cross-form compatibility rules produced zero errors for absent THEN fields, causing NACC downstream QC to catch errors our local QC missed. |
| **Fix (10 lines)** | After `_check_subschema_valid` returns `valid=False, errors={}` in the THEN branch, synthesise explicit `"null value not allowed"` errors for each absent non-nullable THEN field. |
| **Validation** | 179/179 tests pass. Production run `QC_CompleteVisits_01APR2026_222003`: 521 errors (+118 vs pre-fix), zero false positives introduced. All NACC-flagged cross-form errors for PTIDs present in our dataset are now caught. |
| **Upstream status** | Bug present in upstream as of 2026-04-01. Sync when upstream ships a fix. |

## Violation Response

If an **unapproved** modification to `nacc_form_validator` is detected:
1. CI will fail the `External Package Protection` job
2. The PR will be blocked
3. Developer must either revert the change or register it in `ALLOWED_PATCHES` with full justification and team-lead approval

## Questions?

If you need to modify validation logic:
1. Check if it can be done in `/src/pipeline/`
2. If a vendored bug must be patched, follow the *Approved Local Patches* process above
3. Contact the team lead for guidance

## Future Updates

When upstream updates are available:
1. Download the new version from the official source
2. **Verify the approved patches above are addressed by the new version** — if so, remove them from `ALLOWED_PATCHES` in `ci.yml`
3. Replace the entire `nacc_form_validator` directory
4. Run the full test suite and a production QC run to confirm parity

