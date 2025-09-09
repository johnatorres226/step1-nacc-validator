# Simplified Repository Configuration

## Required Secrets
Configure these secrets in your GitHub repository settings:

- `PYPI_TOKEN` - For automated PyPI publishing (optional, only needed for releases)

## Branch Protection
For the main branch, consider enabling:
- Require pull request reviews before merging
- Require status checks to pass before merging (CI workflow)
- Require branches to be up to date before merging

## GitHub Actions
This repository uses two simple workflows:
1. **CI** (`ci.yml`) - Runs code quality checks on every push/PR
2. **Release** (`release.yml`) - Publishes to PyPI when a version tag is created

That's it! Simple and effective CI/CD for this Python CLI tool.
