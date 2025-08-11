#!/usr/bin/env python3
"""
Clear Test Validation Database

This script clears the test validation database to prepare for clean testing.
Use this before running test validations to ensure a fresh state.

Usage:
    python clear_test_validation_db.py
    
The script will:
1. Delete the test validation database file if it exists
2. Display confirmation of the operation
3. Provide instructions for creating a new test database
"""

import os
import sys
from pathlib import Path

def clear_test_validation_db():
    """Clear the test validation database."""
    # Get the project root directory (where this script is located)
    project_root = Path(__file__).parent
    test_db_path = project_root / "data" / "test_validation_history.db"
    
    print("🧪 Test Validation Database Cleaner")
    print("=" * 50)
    print(f"Test Database Path: {test_db_path}")
    
    if test_db_path.exists():
        try:
            # Remove the test database file
            test_db_path.unlink()
            print("✅ Test validation database cleared successfully!")
            print(f"📁 Deleted: {test_db_path}")
        except Exception as e:
            print(f"❌ Error clearing test database: {e}")
            sys.exit(1)
    else:
        print("ℹ️  Test validation database doesn't exist (already clean)")
    
    print("\n📋 Next Steps:")
    print("1. Run test validation commands to create a fresh test database")
    print("2. Use --test-mode flag with enhanced validation commands")
    print("3. Check the data/README.md for test database setup instructions")
    
    print("\n🚀 Example Test Command:")
    print("   python -m src.cli.cli run-enhanced --test-mode --mode complete_events --user-initials TEST")

if __name__ == "__main__":
    clear_test_validation_db()
