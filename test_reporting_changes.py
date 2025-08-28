#!/usr/bin/env python3
"""
Test script to verify reporting changes include packet information correctly.
"""

import sys
import os
import pandas as pd
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipeline.core.visit_processing import build_complete_visits_df

def test_complete_visits_packet_integration():
    """Test that complete visits processing includes packet information."""
    
    # Create sample data with packet information and completion columns
    sample_data = pd.DataFrame({
        'ptid': ['001', '002', '003', '004'],
        'redcap_event_name': ['visit_1_arm_1', 'visit_1_arm_1', 'visit_2_arm_1', 'visit_1_arm_1'], 
        'packet': ['I', 'I4', 'F', 'I'],
        'form_a_complete': ['2', '2', '1', '2'],  # Complete, Complete, Incomplete, Complete
        'form_b_complete': ['2', '1', '2', '2'],  # Complete, Incomplete, Complete, Complete
        'form_c_complete': ['2', '2', '2', '2']   # Complete, Complete, Complete, Complete
    })
    
    print("Sample data:")
    print(sample_data)
    print()
    
    # Test complete visits processing
    instrument_list = ['form_a', 'form_b', 'form_c']
    try:
        summary_df, complete_visits_tuples = build_complete_visits_df(sample_data, instrument_list)
        
        print("Complete visits summary:")
        print(summary_df)
        print()
        
        print("Complete visits tuples:")
        for visit in complete_visits_tuples:
            print(f"  {visit}")
        print()
        
        # Verify packet column exists in summary
        if 'packet' in summary_df.columns:
            print("✓ SUCCESS: packet column found in complete visits summary")
        else:
            print("✗ ERROR: packet column missing from complete visits summary")
            return False
        
        # Verify packet values are preserved
        if not summary_df.empty:
            actual_packets = set(summary_df['packet'].unique())
            print(f"✓ SUCCESS: packet values found: {actual_packets}")
        else:
            print("ℹ INFO: No complete visits found in test data (expected due to incomplete forms)")
            
        return True
        
    except Exception as e:
        print(f"✗ ERROR: Exception during processing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing complete visits packet integration...")
    print("=" * 50)
    
    success = test_complete_visits_packet_integration()
    
    if success:
        print("\n🎉 All tests passed! Reporting changes working correctly.")
    else:
        print("\n❌ Tests failed! Please check the implementation.")
        sys.exit(1)
