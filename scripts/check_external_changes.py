#!/usr/bin/env python3
"""
Check for unauthorized modifications to external packages.

This script verifies that protected directories (like nacc_form_validator)
have not been modified in the current commit or working directory.

Exit codes:
    0: No unauthorized changes detected
    1: Unauthorized changes detected or script error
"""

import subprocess
import sys
from pathlib import Path

# Protected directories that should not be modified
PROTECTED_DIRS = [
    "nacc_form_validator",
]

# Files that are allowed to change even in protected directories
ALLOWED_FILES = [
    "nacc_form_validator/__pycache__",
    "nacc_form_validator/.pytest_cache",
]


def is_allowed_change(file_path: str) -> bool:
    """Check if a file change is in the allowed list."""
    for allowed in ALLOWED_FILES:
        if file_path.startswith(allowed):
            return True
    return False


def check_staged_changes() -> list[str]:
    """Check for staged changes in protected directories."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            capture_output=True,
            text=True,
            check=True
        )
        
        changed_files = result.stdout.strip().split("\n")
        violations = []
        
        for file_path in changed_files:
            if not file_path:
                continue
            
            for protected_dir in PROTECTED_DIRS:
                if file_path.startswith(protected_dir) and not is_allowed_change(file_path):
                    violations.append(file_path)
        
        return violations
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running git command: {e}")
        return []


def check_uncommitted_changes() -> list[str]:
    """Check for uncommitted changes in protected directories."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            check=True
        )
        
        changed_files = result.stdout.strip().split("\n")
        violations = []
        
        for file_path in changed_files:
            if not file_path:
                continue
            
            for protected_dir in PROTECTED_DIRS:
                if file_path.startswith(protected_dir) and not is_allowed_change(file_path):
                    violations.append(file_path)
        
        return violations
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running git command: {e}")
        return []


def main():
    """Main execution function."""
    print("🔍 Checking for unauthorized modifications to external packages...")
    print(f"📦 Protected directories: {', '.join(PROTECTED_DIRS)}")
    print()
    
    staged = check_staged_changes()
    uncommitted = check_uncommitted_changes()
    
    all_violations = list(set(staged + uncommitted))
    
    if all_violations:
        print("❌ VIOLATION: Unauthorized changes detected in protected packages!\n")
        print("The following files in protected directories have been modified:\n")
        for file_path in sorted(all_violations):
            print(f"  ⚠️  {file_path}")
        
        print("\n" + "=" * 70)
        print("🚫 POLICY: nacc_form_validator is an EXTERNAL package")
        print("=" * 70)
        print("\nThis package must NOT be modified in this repository.")
        print("It is maintained externally and updates come from upstream.\n")
        print("What to do:")
        print("  1. Revert changes to the protected package")
        print("  2. If you need to modify validation logic, do it in:")
        print("     - src/pipeline/processors/")
        print("     - Extend/wrap the validator instead")
        print("  3. See docs/external-package-policy.md for details\n")
        
        sys.exit(1)
    
    print("✅ No unauthorized changes to external packages detected.")
    print("✨ All checks passed!")
    sys.exit(0)


if __name__ == "__main__":
    main()
