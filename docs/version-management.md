# Version Management

Follows [Semantic Versioning 2.0.0](https://semver.org/): `MAJOR.MINOR.PATCH`

| Increment | When |
|-----------|------|
| `MAJOR` | Breaking / incompatible API change |
| `MINOR` | New backwards-compatible feature |
| `PATCH` | Bug fix or minor improvement |

## Single source of truth

`pyproject.toml` → `[tool.poetry] version = "X.Y.Z"`

The version also appears in `src/pipeline/__init__.py`. The update script keeps them in sync.

## Update Commands

```bash
python scripts/update_version.py --patch   # 0.1.0 → 0.1.1
python scripts/update_version.py --minor   # 0.1.0 → 0.2.0
python scripts/update_version.py --major   # 0.1.0 → 1.0.0
python scripts/update_version.py 1.5.2     # set specific version
```

After running the script, update `CHANGELOG.md` and open a PR to `main` per the release workflow in [github-workflows.md](github-workflows.md).
