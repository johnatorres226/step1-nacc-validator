#!/usr/bin/env python3
"""
Version Update Script for UDSv4 REDCap QC Validator

This script updates the version across all relevant files in the project.
It follows semantic versioning (MAJOR.MINOR.PATCH).

Usage:
    python scripts/update_version.py 0.2.0
    python scripts/update_version.py --major  # Increment major version
    python scripts/update_version.py --minor  # Increment minor version
    python scripts/update_version.py --patch  # Increment patch version
"""

import argparse
import re
import sys
from pathlib import Path


def read_current_version(version_file: Path) -> str:
    """Read the current version from version.py."""
    content = version_file.read_text()
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise ValueError("Could not find __version__ in version.py")
    return match.group(1)


def increment_version(current: str, part: str) -> str:
    """Increment the specified part of the version."""
    major, minor, patch = map(int, current.split("."))
    
    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Invalid version part: {part}")


def validate_version(version: str) -> bool:
    """Validate that the version follows semantic versioning."""
    pattern = r'^\d+\.\d+\.\d+$'
    return bool(re.match(pattern, version))


def update_file(file_path: Path, old_version: str, new_version: str) -> None:
    """Update version in a specific file."""
    if not file_path.exists():
        print(f"⚠️  File not found: {file_path}")
        return
    
    content = file_path.read_text()
    updated_content = content.replace(old_version, new_version)
    
    if content == updated_content:
        print(f"⚠️  No changes in: {file_path.name}")
        return
    
    file_path.write_text(updated_content)
    print(f"✅ Updated: {file_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Update project version")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("version", nargs="?", help="New version (e.g., 0.2.0)")
    group.add_argument("--major", action="store_true", help="Increment major version")
    group.add_argument("--minor", action="store_true", help="Increment minor version")
    group.add_argument("--patch", action="store_true", help="Increment patch version")
    
    args = parser.parse_args()
    
    # Find project root
    root = Path(__file__).parent.parent
    version_file = root / "version.py"
    
    if not version_file.exists():
        print(f"❌ Error: version.py not found at {version_file}")
        sys.exit(1)
    
    # Read current version
    current_version = read_current_version(version_file)
    print(f"📌 Current version: {current_version}")
    
    # Determine new version
    if args.version:
        new_version = args.version
        if not validate_version(new_version):
            print(f"❌ Error: Invalid version format: {new_version}")
            print("   Version must follow semantic versioning (MAJOR.MINOR.PATCH)")
            sys.exit(1)
    else:
        if args.major:
            new_version = increment_version(current_version, "major")
        elif args.minor:
            new_version = increment_version(current_version, "minor")
        else:  # args.patch
            new_version = increment_version(current_version, "patch")
    
    print(f"🎯 New version: {new_version}")
    
    # Update all relevant files
    files_to_update = [
        version_file,
        root / "pyproject.toml",
        root / "src" / "pipeline" / "__init__.py",
    ]
    
    print("\n📝 Updating files...")
    for file_path in files_to_update:
        update_file(file_path, current_version, new_version)
    
    print(f"\n✨ Version updated from {current_version} to {new_version}")
    print("\n💡 Next steps:")
    print(f"   1. Review changes: git diff")
    print(f"   2. Commit: git add . && git commit -m 'chore: bump version to {new_version}'")
    print(f"   3. Tag: git tag v{new_version}")
    print(f"   4. Push: git push origin --tags")


if __name__ == "__main__":
    main()
