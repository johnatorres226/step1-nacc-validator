#!/usr/bin/env python3
"""
Test script to verify test mode functionality.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipeline.config_manager import QCConfig
from pipeline.reports import ReportFactory
from pipeline.context import ProcessingContext, ExportConfiguration, ReportConfiguration
from nacc_form_validator.datastore import Datastore

def create_test_databases():
    """Create test databases for testing."""
    print("Creating test databases...")
    
    # Create data directory if it doesn't exist
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Create regular test database
    test_db_path = data_dir / "validation_history.db"
    if not test_db_path.exists():
        print(f"Creating test database: {test_db_path}")
        datastore = EnhancedDatastore(str(test_db_path))
        print("✅ Regular test database created")
    
    # Create test mode database
    test_mode_db_path = data_dir / "test_validation_history.db"
    if not test_mode_db_path.exists():
        print(f"Creating test mode database: {test_mode_db_path}")
        datastore = EnhancedDatastore(str(test_mode_db_path))
        print("✅ Test mode database created")

def test_test_mode_summary():
    """Test the test mode summary generation."""
    print("="*80)
    print("TESTING TEST MODE SUMMARY GENERATION")
    print("="*80)
    
    # Create test databases first
    create_test_databases()
    
    # Create test output directory
    test_output_dir = Path("output") / "test_verification"
    test_output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Test output directory: {test_output_dir}")
    
    # Test instruments
    instruments = ["a1_participant_demographics", "b1_vital_signs_and_anthropometrics"]
    
    # Test regular mode
    print("\n1. Testing REGULAR mode:")
    regular_filename = "ENHANCED_SUMMARY_TEST.txt"
    try:
        # Set the datastore path for regular mode
        regular_datastore_path = str(Path("data") / "validation_history.db")
        print(f"Regular datastore path: {regular_datastore_path}")
        print(f"Path exists: {Path(regular_datastore_path).exists()}")
        # Test regular mode using ReportFactory
        processing_context = ProcessingContext(
            data_df=pd.DataFrame(),
            instrument_list=instruments,
            rules_cache={},
            primary_key_field='ptid',
            config=None
        )
        
        export_config = ExportConfiguration(
            output_dir=test_output_dir,
            date_tag='26AUG2025',
            time_tag='140000'
        )
        
        report_config = ReportConfiguration(
            qc_run_by='test_user',
            primary_key_field='ptid',
            instruments=instruments
        )
        
        factory = ReportFactory(processing_context)
        regular_report = factory.generate_status_report(
            all_records_df=pd.DataFrame(),
            complete_visits_df=pd.DataFrame(),
            detailed_validation_logs_df=pd.DataFrame(),
            export_config=export_config,
            report_config=report_config
        )
        print(f"✅ Regular mode report generated: {regular_report}")
        
        # Check file content
        if regular_report.exists():
            with open(regular_report, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"✅ Report size: {len(content)} characters")
                if "metric" in content:
                    print("✅ Contains correct header for regular mode")
                else:
                    print("❌ Missing expected header for regular mode")
    except Exception as e:
        print(f"❌ Error in regular mode: {e}")
    
    # Test test mode using ReportFactory
    print("\n2. Testing TEST mode:")
    try:
        # Test mode uses same ReportFactory interface
        test_export_config = ExportConfiguration(
            output_dir=test_output_dir,
            date_tag='26AUG2025',
            time_tag='140000'
        )
        
        test_report_config = ReportConfiguration(
            qc_run_by='test_user',
            primary_key_field='ptid',
            instruments=instruments
        )
        
        test_factory = ReportFactory(processing_context)
        test_report = test_factory.generate_status_report(
            all_records_df=pd.DataFrame(),
            complete_visits_df=pd.DataFrame(),
            detailed_validation_logs_df=pd.DataFrame(),
            export_config=test_export_config,
            report_config=test_report_config
        )
        print(f"✅ Test mode report generated: {test_report}")
        
        # Check file content
        if test_report.exists():
            with open(test_report, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"✅ Report size: {len(content)} characters")
                
                # Check for test mode indicators
                checks = [
                    ("TEST RUN SUMMARY REPORT", "correct header"),
                    ("Test Mode: ENABLED", "test mode indicator"),
                    ("Test Database: data/test_validation_history.db", "test database path"),
                    ("test_validation_history.db", "test database reference"),
                    ("clear_test_validation_db.py", "cleanup script reference")
                ]
                
                for check_text, description in checks:
                    if check_text in content:
                        print(f"✅ Contains {description}")
                    else:
                        print(f"❌ Missing {description}")
                
                # Check filename pattern separately
                if "TEST_RUN_SUMMARY_" in str(test_report):
                    print("✅ Contains correct filename pattern")
                else:
                    print("❌ Missing correct filename pattern")
                
                # Show first 20 lines
                lines = content.split('\n')[:20]
                print("\nFirst 20 lines of test mode report:")
                for i, line in enumerate(lines, 1):
                    print(f"{i:2d}: {line}")
        else:
            print("❌ Test mode report file not found")
    except Exception as e:
        print(f"❌ Error in test mode: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("TEST MODE VERIFICATION COMPLETED")
    print("="*80)

if __name__ == "__main__":
    test_test_mode_summary()
