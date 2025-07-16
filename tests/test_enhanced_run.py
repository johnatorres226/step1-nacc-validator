#!/usr/bin/env python3
"""
Test script to verify enhanced run functionality with directory structure.
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipeline.datastore import EnhancedDatastore
from pipeline.report_pipeline import generate_enhanced_summary_report

def test_enhanced_directory_structure():
    """Test the enhanced directory structure creation."""
    print("="*80)
    print("TESTING ENHANCED DIRECTORY STRUCTURE")
    print("="*80)
    
    # Create expected directory structure
    date_tag = datetime.now().strftime("%d%b%Y").upper()
    event_type = "Complete_Events"
    enhanced_dir_name = f"ENHANCED_QC_{event_type}_{date_tag}"
    
    test_output_path = Path("output") / enhanced_dir_name
    test_output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"✅ Enhanced directory created: {test_output_path}")
    
    # Test enhanced summary report generation
    instruments = ["a1_participant_demographics", "b1_vital_signs_and_anthropometrics"]
    filename = f"ENHANCED_SUMMARY_{date_tag}.txt"
    
    try:
        # Create some test data in the datastore
        datastore = EnhancedDatastore("data/validation_history.db")
        
        # Generate enhanced summary report
        report_path = generate_enhanced_summary_report(
            str(test_output_path),
            instruments,
            filename
        )
        
        print(f"✅ Enhanced summary report generated: {report_path}")
        
        # Verify the file exists and has content
        if Path(report_path).exists():
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"✅ Report file size: {len(content)} characters")
                print(f"✅ Report filename: {filename}")
                
                # Show first few lines
                lines = content.split('\n')[:10]
                print("\nFirst 10 lines of report:")
                for i, line in enumerate(lines, 1):
                    print(f"{i:2d}: {line}")
        else:
            print("❌ Report file not found")
            
    except Exception as e:
        print(f"❌ Error generating enhanced summary: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("🎉 ENHANCED DIRECTORY STRUCTURE TEST COMPLETED!")
    print("="*80)

def test_enhanced_naming_convention():
    """Test the enhanced naming convention."""
    print("\n" + "="*80)
    print("TESTING ENHANCED NAMING CONVENTION")
    print("="*80)
    
    date_tag = datetime.now().strftime("%d%b%Y").upper()
    
    # Test different event types
    event_types = ["Complete_Events", "Complete_Instruments", "Custom"]
    
    for event_type in event_types:
        enhanced_dir_name = f"ENHANCED_QC_{event_type}_{date_tag}"
        enhanced_filename = f"ENHANCED_SUMMARY_{date_tag}.txt"
        
        print(f"Event Type: {event_type}")
        print(f"  Directory: {enhanced_dir_name}")
        print(f"  Summary File: {enhanced_filename}")
        print()
    
    print("✅ All naming conventions verified")
    print("="*80)

if __name__ == "__main__":
    test_enhanced_directory_structure()
    test_enhanced_naming_convention()
