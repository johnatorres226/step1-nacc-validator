# GitHub Workflows

Two workflows: `ci.yml` (validate) and `release.yml` (publish).

## CI (`ci.yml`)

Triggers: push to `dev` / `codebase-curation`; PRs targeting `main` or `dev`.

| Job | When | What |
|-----|------|------|
| `check-external-packages` | Always | Blocks unapproved changes to `nacc_form_validator/` |
| `pr-to-main-checks` | PRs → `main` only | Verifies `CHANGELOG.md` updated and version bumped |
| `test` | Always | pytest on Python 3.11 / 3.12 / 3.13; coverage uploaded (3.12) |
| `lint` | Always | `ruff check` + `ruff format --check` |
| `type-check` | Always | `mypy` |
| `build-verify` | Always | `poetry build` + `poetry check` |

## Release (`release.yml`)

Triggers: tag push matching `v*.*.*`.

Validates tag == `pyproject.toml` version → builds wheel + sdist → creates GitHub Release with artifacts.
Marked prerelease if version contains `-`, `alpha`, `beta`, or `rc`.

## Release Workflow (manual steps)

```bash
# 1. On dev: bump version + update CHANGELOG.md
# 2. PR: dev → main (triggers full CI including pr-to-main-checks)
# 3. After merge:
git checkout main && git pull
git tag v1.2.0
git push origin v1.2.0   # triggers release.yml
```

## Troubleshooting

```bash
# Run checks locally before pushing
poetry run pytest tests/ -v
poetry run ruff check src tests
poetry run ruff format --check src tests
poetry run mypy --config-file mypy.ini src
poetry build && poetry check

# CI failed — view logs
gh run list --workflow=ci.yml --limit 5
gh run view <run-id> --log-failed

# External package check failed → revert nacc_form_validator/ changes
#   or add file to ALLOWED_PATCHES in ci.yml with justification

# PR-to-main check failed → update CHANGELOG.md and bump version in pyproject.toml

# Release version mismatch → tag vX.Y.Z must match pyproject.toml version = "X.Y.Z"
```
