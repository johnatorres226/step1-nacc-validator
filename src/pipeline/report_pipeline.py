"""
Main pipeline for processing and validating REDCap instrument data.

This module orchestrates the entire QC process, from fetching raw data to
generating final summary reports. It is designed to be run from the command
line via `cli/cli.py`.

The pipeline operates in several stages:
1.  **Configuration**: Loads settings from `QCConfig`.
2.  **Data Fetching**: Extracts data from the source using `pipeline.fetcher`.
3.  **Rule Loading**: Caches all JSON validation rules for the requested instruments.
4.  **Data Preparation**: Prepares instrument-specific dataframes for validation.
5.  **Validation**: Runs vectorized simple checks and then row-by-row complex
    validation against the JSON rules.
6.  **Reporting**: Generates several output files, including:
    - A final dataset of all identified errors.
    - Aggregate error counts per participant/event.
    - A tool status report indicating pass/fail for each instrument.
    - Detailed validation logs.
"""
import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import asdict

import numpy as np
import pandas as pd

from pipeline.config_manager import (
    QCConfig,
    get_dynamic_rule_instruments,
    get_discriminant_variable,
    is_dynamic_rule_instrument,
    get_rule_mappings,
    get_instrument_json_mapping,
    upload_ready_path
)
from pipeline.datastore import EnhancedDatastore, ErrorComparison
from pipeline.fetcher import fetch_etl_data
from pipeline.quality_check import QualityCheck
from pipeline.helpers import (
    build_complete_visits_df,
    build_detailed_validation_logs,
    build_variable_maps,
    debug_variable_mapping,
    load_rules_for_instruments,
    load_json_rules_for_instrument,
    prepare_instrument_data_cache,
    process_dynamic_validation,
    _preprocess_cast_types,
    _run_vectorized_simple_checks,
    load_dynamic_rules_for_instrument,
)
from pipeline.schema_builder import build_cerberus_schema_for_instrument
from pipeline.utils import (
    convert_to_date,
    convert_to_datetime,
)

# Set up logging
import logging

logger = logging.getLogger(__name__)

# Enhanced validation functionality
def validate_with_datastore_tracking(data: pd.DataFrame, 
                                   instrument: str, 
                                   config: QCConfig,
                                   datastore_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate data with datastore tracking for error comparison and trend analysis.
    
    Only works with complete_events mode.
    
    Args:
        data: DataFrame to validate
        instrument: Instrument name
        config: QC configuration
        datastore_path: Path to datastore database
        
    Returns:
        Dictionary with validation results, comparison, and trend analysis
    """
    # Only support complete_events mode
    if config.mode != 'complete_events':
        logger.warning(f"Datastore tracking only supports complete_events mode, got: {config.mode}")
        return {}
    
    logger.info(f"Starting validation with datastore tracking for {instrument}")
    
    # Initialize datastore
    datastore = EnhancedDatastore(get_datastore_path(datastore_path))
    
    # Load validation rules
    validation_rules = load_json_rules_for_instrument(instrument)
    
    # Run validation
    errors, validation_logs, passed_validations = validate_data(
        data=data,
        validation_rules=validation_rules,
        instrument_name=instrument,
        primary_key_field='ptid'
    )
    
    # Convert errors to DataFrame
    errors_df = pd.DataFrame(errors)
    
    # Store validation run
    run_config = {
        'mode': config.mode,
        'events': config.events,
        'instruments': config.instruments,
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    run_id = datastore.store_validation_run(
        instrument=instrument,
        errors_df=errors_df,
        total_records=len(data),
        run_config=run_config
    )
    
    # Compare with previous run
    error_comparisons = datastore.compare_with_previous_run(errors_df, instrument)
    
    # Count comparison results
    new_errors = len([c for c in error_comparisons if c.status == 'new'])
    resolved_errors = len([c for c in error_comparisons if c.status == 'resolved'])
    persistent_errors = len([c for c in error_comparisons if c.status == 'persistent'])
    
    # Get trend analysis
    trend_analysis = datastore.get_trend_analysis(instrument)
    
    # Get pattern analysis
    pattern_analysis = datastore.detect_error_patterns(instrument)
    
    # Generate quality dashboard
    dashboard = datastore.generate_quality_dashboard(instrument)
    
    logger.info(f"Validation completed for {instrument}: {len(errors)} errors, {new_errors} new, {resolved_errors} resolved")
    
    return {
        'run_id': run_id,
        'validation_results': {
            'errors': errors,
            'validation_logs': validation_logs,
            'passed_validations': passed_validations,
            'total_records': len(data),
            'error_count': len(errors),
            'passed_count': len(data) - len(errors)
        },
        'comparison_results': {
            'new_errors': new_errors,
            'resolved_errors': resolved_errors,
            'persistent_errors': persistent_errors,
            'total_comparisons': len(error_comparisons),
            'comparisons': error_comparisons
        },
        'trend_analysis': trend_analysis,
        'pattern_analysis': pattern_analysis,
        'dashboard': dashboard
    }


def generate_datastore_analysis_report(instrument: str, 
                                     output_path: str,
                                     datastore_path: Optional[str] = None,
                                     filename: Optional[str] = None) -> str:
    """
    Generate a comprehensive datastore analysis report.
    
    Args:
        instrument: Instrument name
        output_path: Path to save the report
        datastore_path: Path to datastore database
        filename: Optional custom filename for the report
        
    Returns:
        Path to the generated report file
    """
    datastore = EnhancedDatastore(get_datastore_path(datastore_path))
    
    # Get comprehensive analysis
    dashboard = datastore.generate_quality_dashboard(instrument)
    trend_analysis = datastore.get_trend_analysis(instrument, days_back=90)
    pattern_analysis = datastore.detect_error_patterns(instrument, days_back=90)
    
    # Generate report
    if filename:
        report_filename = filename
    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"datastore_analysis_{instrument}_{timestamp}.txt"
        
    report_path = Path(output_path) / report_filename
    
    # Create output directory if it doesn't exist
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("DATASTORE ANALYSIS REPORT\n")
        f.write("="*80 + "\n")
        f.write(f"Instrument: {instrument}\n")
        f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Analysis Period: 90 days\n")
        f.write("="*80 + "\n\n")
        
        # Dashboard Summary
        f.write("QUALITY DASHBOARD SUMMARY\n")
        f.write("-" * 40 + "\n")
        summary = dashboard['summary']
        f.write(f"Error Rate Trend: {summary['error_rate_trend']}\n")
        f.write(f"Current Error Rate: {summary['current_error_rate']:.2f}%\n")
        f.write(f"Average Error Rate: {summary['average_error_rate']:.2f}%\n")
        f.write(f"Total Historical Runs: {summary['total_historical_runs']}\n")
        f.write(f"Recent Runs (30 days): {summary['total_runs']}\n\n")
        
        # Trend Analysis
        f.write("TREND ANALYSIS\n")
        f.write("-" * 40 + "\n")
        f.write(f"Trend Direction: {trend_analysis['trend_direction']}\n")
        f.write(f"Analysis Period: {trend_analysis['period_days']} days\n")
        f.write(f"Total Runs Analyzed: {trend_analysis['total_runs']}\n")
        
        if trend_analysis['error_rates']:
            f.write("\nRecent Error Rates:\n")
            for i, rate_data in enumerate(trend_analysis['error_rates'][-5:]):
                f.write(f"  Run {i+1}: {rate_data['error_rate']:.2f}% ({rate_data['error_count']} errors)\n")
        f.write("\n")
        
        # Pattern Analysis
        f.write("PATTERN ANALYSIS\n")
        f.write("-" * 40 + "\n")
        f.write(f"Repeated Patterns: {pattern_analysis['repeated_patterns']}\n")
        f.write(f"Error Clusters: {pattern_analysis['error_clusters']}\n")
        f.write(f"Systematic Issues: {pattern_analysis['systematic_issues']}\n")
        
        if pattern_analysis['top_patterns']:
            f.write("\nTop Repeated Patterns:\n")
            for pattern in pattern_analysis['top_patterns'][:5]:
                f.write(f"  {pattern['ptid']} - {pattern['variable']}: {pattern['count']} times\n")
        
        if pattern_analysis['systematic_issues_detail']:
            f.write("\nSystematic Issues:\n")
            for issue in pattern_analysis['systematic_issues_detail'][:5]:
                f.write(f"  {issue['variable']} ({issue['error_type']}): {issue['count']} occurrences\n")
        
        f.write("\n")
        
        # Recommendations
        f.write("RECOMMENDATIONS\n")
        f.write("-" * 40 + "\n")
        
        if summary['error_rate_trend'] == 'increasing':
            f.write("WARNING: Error rate is increasing. Consider:\n")
            f.write("   - Reviewing data collection procedures\n")
            f.write("   - Additional staff training\n")
            f.write("   - Implementing preventive measures\n")
        elif summary['error_rate_trend'] == 'decreasing':
            f.write("SUCCESS: Error rate is decreasing. Continue current practices.\n")
        else:
            f.write("INFO: Error rate is stable. Monitor for changes.\n")
        
        if pattern_analysis['systematic_issues'] > 0:
            f.write(f"\nWARNING: {pattern_analysis['systematic_issues']} systematic issues detected.\n")
            f.write("   Consider targeted interventions for recurring problems.\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write("End of Report\n")
        f.write("="*80 + "\n")
    
    logger.info(f"Datastore analysis report generated: {report_path}")
    return str(report_path)


def get_datastore_path(default_path: Optional[str] = None) -> str:
    """
    Get the datastore path from environment variable or use default.
    
    Args:
        default_path: Default path to use if environment variable is not set
        
    Returns:
        str: Path to the validation history database
    """
    # If a specific path is provided, use it directly
    if default_path:
        return default_path
    
    # Otherwise check environment variable
    env_path = os.getenv("VALIDATION_HISTORY_DB_PATH")
    if env_path:
        return env_path
    
    # Final fallback
    return "data/validation_history.db"


def generate_enhanced_summary_report(output_path: str, 
                                   instruments: List[str],
                                   filename: str = "ENHANCED_SUMMARY.txt",
                                   datastore_path: Optional[str] = None,
                                   test_mode: bool = False) -> str:
    """
    Generate an enhanced summary report for multiple instruments.
    
    Args:
        output_path: Path to save the report
        instruments: List of instrument names to analyze
        filename: Custom filename for the report
        datastore_path: Path to datastore database
        test_mode: Whether this is a test run (affects report format)
        
    Returns:
        Path to the generated report file
    """
    datastore = EnhancedDatastore(get_datastore_path(datastore_path))
    
    # For test mode, use TEST_RUN_SUMMARY format
    if test_mode and "ENHANCED_SUMMARY" in filename:
        date_tag = datetime.datetime.now().strftime("%d%b%Y").upper()
        filename = f"TEST_RUN_SUMMARY_{date_tag}.txt"
    
    report_path = Path(output_path) / filename
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        if test_mode:
            f.write("="*80 + "\n")
            f.write("TEST RUN SUMMARY REPORT\n")
            f.write("="*80 + "\n")
            f.write(f"Test Mode: ENABLED\n")
            f.write(f"Test Database: data/test_validation_history.db\n")
            f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Analysis Period: 90 days\n")
            f.write("="*80 + "\n\n")
            
            f.write("TEST MODE INFORMATION\n")
            f.write("-" * 40 + "\n")
            f.write("This is a test run using a separate test database.\n")
            f.write("No production data was affected during this validation.\n")
            f.write("Test results are isolated from production validation history.\n\n")
        else:
            f.write("="*80 + "\n")
            f.write("ENHANCED QC SUMMARY REPORT\n")
            f.write("="*80 + "\n")
            f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Analysis Period: 90 days\n")
            f.write("="*80 + "\n\n")
        
        for instrument in instruments:
            f.write(f"INSTRUMENT: {instrument}\n")
            f.write("-" * 40 + "\n")
            
            try:
                # Get comprehensive analysis
                dashboard = datastore.generate_quality_dashboard(instrument)
                trend_analysis = datastore.get_trend_analysis(instrument, days_back=90)
                pattern_analysis = datastore.detect_error_patterns(instrument, days_back=90)
                
                # Summary
                summary = dashboard.get('summary', {})
                current_error_rate = summary.get('current_error_rate', 0)
                total_errors = summary.get('total_errors', 0)
                
                if test_mode:
                    f.write(f"Test Run Status: {'ERRORS DETECTED' if total_errors > 0 else 'NO ERRORS FOUND'}\n")
                    f.write(f"Total Errors Found: {total_errors}\n")
                    f.write(f"Error Rate: {current_error_rate:.2f}%\n")
                    
                    if total_errors > 0:
                        f.write(f"⚠️  WARNING: {total_errors} validation errors detected in test run\n")
                        f.write("   Review errors before running production validation\n")
                    else:
                        f.write("✅ SUCCESS: No validation errors found in test run\n")
                        f.write("   Data appears ready for production validation\n")
                    f.write("\n")
                
                f.write(f"Error Rate Trend: {summary.get('error_rate_trend', 'N/A')}\n")
                f.write(f"Current Error Rate: {current_error_rate:.2f}%\n")
                f.write(f"Average Error Rate: {summary.get('average_error_rate', 0):.2f}%\n")
                f.write(f"Total Historical Runs: {summary.get('total_historical_runs', 0)}\n")
                f.write(f"Recent Runs (30 days): {summary.get('recent_runs', 0)}\n\n")
                
            except Exception as e:
                f.write(f"ERROR: Could not analyze instrument {instrument}\n")
                f.write(f"Error details: {str(e)}\n")
                if test_mode:
                    f.write("⚠️  WARNING: Analysis failed - check test database setup\n")
                f.write("\n")
                logger.warning(f"Error analyzing instrument {instrument}: {e}")
                continue
            
            # Trend Analysis (skip in test mode if no historical data)
            if not test_mode or trend_analysis.get('total_runs', 0) > 0:
                f.write("TREND ANALYSIS\n")
                f.write("-" * 20 + "\n")
                f.write(f"Trend Direction: {trend_analysis.get('trend_direction', 'N/A')}\n")
                f.write(f"Analysis Period: 90 days\n")
                f.write(f"Total Runs Analyzed: {trend_analysis.get('total_runs', 0)}\n")
                
                recent_rates = trend_analysis.get('recent_error_rates', [])
                if recent_rates:
                    f.write("Recent Error Rates:\n")
                    for i, rate_info in enumerate(recent_rates[:5], 1):
                        f.write(f"  Run {i}: {rate_info.get('error_rate', 0):.2f}% ({rate_info.get('error_count', 0)} errors)\n")
                
                f.write("\n")
            elif test_mode:
                f.write("TREND ANALYSIS\n")
                f.write("-" * 20 + "\n")
                f.write("No historical data available in test database\n")
                f.write("This is expected for test runs\n\n")
            
            # Pattern Analysis
            f.write("PATTERN ANALYSIS\n")
            f.write("-" * 20 + "\n")
            f.write(f"Repeated Patterns: {pattern_analysis.get('repeated_patterns', 0)}\n")
            f.write(f"Error Clusters: {pattern_analysis.get('error_clusters', 0)}\n")
            f.write(f"Systematic Issues: {pattern_analysis.get('systematic_issues', 0)}\n")
            
            # Top patterns
            top_patterns = pattern_analysis.get('top_patterns', [])
            if top_patterns:
                f.write("Top Repeated Patterns:\n")
                for pattern in top_patterns[:5]:
                    f.write(f"  {pattern['ptid']} - {pattern['variable']}: {pattern['count']} times\n")
            
            # Systematic issues
            systematic = pattern_analysis.get('systematic_issues_detail', [])
            if systematic:
                f.write("Systematic Issues:\n")
                for issue in systematic[:5]:
                    f.write(f"  {issue['variable']} ({issue['error_type']}): {issue['count']} occurrences\n")
            
            f.write("\n")
            
            # Recommendations
            f.write("RECOMMENDATIONS\n")
            f.write("-" * 20 + "\n")
            if test_mode:
                if summary.get('total_errors', 0) > 0:
                    f.write("TEST MODE RECOMMENDATIONS:\n")
                    f.write("   1. Review and fix validation errors before production run\n")
                    f.write("   2. Check data entry procedures for systematic issues\n")
                    f.write("   3. Re-run test after corrections to verify fixes\n")
                    f.write("   4. Only proceed to production after clean test run\n")
                else:
                    f.write("TEST MODE RECOMMENDATIONS:\n")
                    f.write("   ✅ Test passed successfully - ready for production run\n")
                    f.write("   📋 Use: qc_validator run_enhanced --production-mode\n")
            else:
                if summary['error_rate_trend'] == 'increasing':
                    f.write("WARNING: Error rate is increasing. Consider:\n")
                    f.write("   - Reviewing data collection procedures\n")
                    f.write("   - Additional staff training\n")
                    f.write("   - Implementing preventive measures\n")
                elif summary['error_rate_trend'] == 'decreasing':
                    f.write("SUCCESS: Error rate is decreasing. Continue current practices.\n")
                else:
                    f.write("INFO: Error rate is stable. Monitor for changes.\n")
            
            if pattern_analysis['systematic_issues'] > 0:
                f.write(f"\nWARNING: {pattern_analysis['systematic_issues']} systematic issues detected.\n")
                f.write("   Consider targeted interventions for recurring problems.\n")
            
            f.write("\n" + "="*80 + "\n\n")
        
        # Test mode summary
        if test_mode:
            f.write("TEST RUN COMPLETION SUMMARY\n")
            f.write("="*40 + "\n")
            f.write("Test run completed successfully.\n")
            f.write("Use clear_test_validation_db.py to clean test database for next test.\n")
            f.write("Switch to --production-mode when ready for production validation.\n\n")
        
        f.write(f"End of {'Test Run' if test_mode else 'Enhanced'} Summary Report\n")
        f.write("="*80 + "\n")
    
    logger.info(f"Enhanced summary report generated: {report_path}")
    return str(report_path)


# Enhanced Pipeline Class
class EnhancedReportPipeline:
    """
    Enhanced report pipeline with datastore integration for error tracking and trend analysis.
    
    This class extends the existing validation pipeline to include:
    - Error comparison between runs
    - Trend analysis over time
    - Pattern detection for recurring issues
    - Data quality monitoring
    """
    
    def __init__(self, datastore_path: Optional[str] = None):
        """
        Initialize the enhanced report pipeline.
        
        Args:
            datastore_path: Path to the datastore database file
        """
        self.datastore = EnhancedDatastore(get_datastore_path(datastore_path))
        
    def validate_with_comparison(self, 
                               data: pd.DataFrame,
                               instrument: str,
                               output_path: Optional[str] = None,
                               ptid_list: Optional[List[str]] = None,
                               primary_key_field: str = "ptid",
                               run_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate data and compare with previous run to identify resolved/new errors.
        
        Args:
            data: DataFrame to validate
            instrument: Instrument name
            output_path: Optional path for output files
            ptid_list: Optional list of specific PTIDs to validate
            primary_key_field: Primary key field name
            run_config: Configuration for this validation run
            
        Returns:
            Dictionary with validation results, comparisons, and analysis
        """
        # Only allow complete_events mode
        if run_config and run_config.get('mode') != 'complete_events':
            logger.warning(f"Enhanced datastore limited to complete_events mode, got: {run_config.get('mode')}")
            return self._fallback_validation(data, instrument, output_path, ptid_list, primary_key_field)
        
        logger.info(f"Starting validation with comparison for {instrument}")
        
        # Load validation rules
        validation_rules = load_json_rules_for_instrument(instrument)
        
        # Filter data if ptid_list is provided
        if ptid_list:
            data = data[data[primary_key_field].isin(ptid_list)]
        
        # Run validation using existing function
        errors, validation_logs, passed_validations = validate_data(
            data=data,
            validation_rules=validation_rules,
            instrument_name=instrument,
            primary_key_field=primary_key_field
        )
        
        # Convert errors to DataFrame for datastore
        errors_df = pd.DataFrame(errors)
        
        # Store validation run
        run_id = self.datastore.store_validation_run(
            instrument=instrument,
            errors_df=errors_df,
            total_records=len(data),
            run_config=run_config or {}
        )
        
        if run_id is None:
            logger.error("Failed to store validation run")
            return self._fallback_validation(data, instrument, output_path, ptid_list, primary_key_field)
        
        # Compare with previous run
        comparisons = self.datastore.compare_with_previous_run(errors_df, instrument)
        
        # Get trend analysis
        trend_analysis = self.datastore.get_trend_analysis(instrument)
        
        # Count comparison results
        new_errors = len([c for c in comparisons if c.status == 'new'])
        resolved_errors = len([c for c in comparisons if c.status == 'resolved'])
        
        logger.info(f"Validation completed successfully for {instrument}")
        logger.info(f"Total errors: {len(errors)}, New: {new_errors}, Resolved: {resolved_errors}")
        
        # Generate enhanced output files if path provided
        output_files = []
        if output_path:
            output_files = self._generate_enhanced_output_files(
                errors_df, comparisons, instrument, output_path, run_id, trend_analysis
            )
        
        return {
            'run_id': run_id,
            'validation_results': {
                'errors': errors,
                'validation_logs': validation_logs,
                'passed_validations': passed_validations,
                'total_records': len(data),
                'error_count': len(errors),
                'passed_count': len(data) - len(errors)
            },
            'comparison_results': {
                'comparisons': comparisons,
                'new_errors': new_errors,
                'resolved_errors': resolved_errors,
                'persistent_errors': len(comparisons) - new_errors - resolved_errors,
                'total_comparisons': len(comparisons)
            },
            'trend_analysis': trend_analysis,
            'output_files': output_files
        }
    
    def _fallback_validation(self, data: pd.DataFrame, instrument: str, 
                           output_path: Optional[str], ptid_list: Optional[List[str]], 
                           primary_key_field: str) -> Dict[str, Any]:
        """Fallback validation for non-complete_events mode."""
        validation_rules = load_json_rules_for_instrument(instrument)
        
        if ptid_list:
            data = data[data[primary_key_field].isin(ptid_list)]
        
        errors, validation_logs, passed_validations = validate_data(
            data=data,
            validation_rules=validation_rules,
            instrument_name=instrument,
            primary_key_field=primary_key_field
        )
        
        return {
            'run_id': None,
            'validation_results': {
                'errors': errors,
                'validation_logs': validation_logs,
                'passed_validations': passed_validations,
                'total_records': len(data),
                'error_count': len(errors),
                'passed_count': len(data) - len(errors)
            },
            'comparison_results': {
                'comparisons': [],
                'new_errors': 0,
                'resolved_errors': 0,
                'persistent_errors': 0,
                'total_comparisons': 0
            },
            'trend_analysis': {},
            'output_files': []
        }
    
    def _generate_enhanced_output_files(self, errors_df: pd.DataFrame, 
                                      comparisons: List[ErrorComparison],
                                      instrument: str, output_path: str,
                                      run_id: str, trend_analysis: Dict[str, Any]) -> List[str]:
        """Generate enhanced output files with comparison and trend information."""
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        run_date = datetime.datetime.now().strftime("%d%b%Y")
        output_files = []
        
        # Enhanced error dataset with status
        if not errors_df.empty:
            enhanced_errors = errors_df.copy()
            enhanced_errors['error_status'] = 'new'  # Default to new
            
            # Add comparison status
            comparison_lookup = {}
            for comp in comparisons:
                key = (comp.ptid, comp.redcap_event_name, comp.variable)
                comparison_lookup[key] = comp.status
            
            for idx, row in enhanced_errors.iterrows():
                key = (row.get('ptid', ''), row.get('redcap_event_name', ''), 
                       row.get('variable', ''))
                enhanced_errors.at[idx, 'error_status'] = comparison_lookup.get(key, 'new')
            
            # Save enhanced error dataset
            enhanced_file = output_dir / f"enhanced_error_dataset_{run_date}.csv"
            enhanced_errors.to_csv(enhanced_file, index=False)
            output_files.append(str(enhanced_file))
        
        # Error comparison report
        comparison_data = []
        for comp in comparisons:
            comparison_data.append(asdict(comp))
        
        if comparison_data:
            comparison_df = pd.DataFrame(comparison_data)
            comparison_file = output_dir / f"error_comparison_{run_date}.csv"
            comparison_df.to_csv(comparison_file, index=False)
            output_files.append(str(comparison_file))
        
        # Error status summary
        summary_data = {
            'run_id': run_id,
            'instrument': instrument,
            'timestamp': datetime.datetime.now().isoformat(),
            'total_errors': len(errors_df),
            'new_errors': len([c for c in comparisons if c.status == 'new']),
            'resolved_errors': len([c for c in comparisons if c.status == 'resolved']),
            'persistent_errors': len([c for c in comparisons if c.status == 'persistent']),
            'trend_analysis': trend_analysis
        }
        
        summary_file = output_dir / f"error_status_summary_{run_date}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2)
        output_files.append(str(summary_file))
        
        return output_files
    
    def generate_dashboard(self, instrument: str) -> Dict[str, Any]:
        """Generate a data quality dashboard for an instrument."""
        return self.datastore.generate_quality_dashboard(instrument)
    
    def get_trend_analysis(self, instrument: str, days_back: int = 30) -> Dict[str, Any]:
        """Get trend analysis for an instrument."""
        return self.datastore.get_trend_analysis(instrument, days_back)
    
    def detect_error_patterns(self, instrument: str, days_back: int = 30) -> Dict[str, Any]:
        """Detect error patterns for an instrument."""
        return self.datastore.detect_error_patterns(instrument, days_back)


# Enhanced version of the main pipeline function
def run_enhanced_report_pipeline(config: QCConfig, enable_datastore: bool = True):
    """
    Enhanced version of the main QC report pipeline with datastore integration.
    
    Args:
        config: The configuration object for the pipeline
        enable_datastore: Whether to enable datastore functionality
    """
    # Only enable datastore for complete_events mode
    if config.mode != 'complete_events':
        logger.info(f"Datastore disabled for mode: {config.mode}")
        enable_datastore = False
    
    # Handle test mode by modifying datastore path
    if hasattr(config, 'test_mode') and config.test_mode:
        logger.info("Running in TEST MODE - using test database")
        # Set environment variable to use test database
        import os
        os.environ['VALIDATION_HISTORY_DB_PATH'] = str(Path("data") / "test_validation_history.db")
    
    # Create enhanced output directory structure
    event_type = config.mode.replace('_', ' ').title().replace(' ', '_')
    date_tag = datetime.datetime.today().strftime("%d%b%Y").upper()
    test_suffix = "_TEST" if (hasattr(config, 'test_mode') and config.test_mode) else ""
    enhanced_dir_name = f"ENHANCED_QC_{event_type}_{date_tag}{test_suffix}"
    
    enhanced_output_path = Path(config.output_path) / enhanced_dir_name
    enhanced_output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Enhanced QC output directory: {enhanced_output_path}")
    
    if enable_datastore:
        logger.info("Running enhanced pipeline with datastore integration")
        
        # Update config to use enhanced output path
        original_output_path = config.output_path
        config.output_path = str(enhanced_output_path)
        
        # Run the standard pipeline first to get all the data
        run_report_pipeline(config)
        
        # Generate enhanced datastore analysis
        test_mode = hasattr(config, 'test_mode') and config.test_mode
        analysis_file = generate_enhanced_summary_report(
            str(enhanced_output_path),
            config.instruments,
            filename=f"ENHANCED_SUMMARY_{date_tag}.txt",
            test_mode=test_mode
        )
        
        logger.info(f"Enhanced datastore analysis saved to: {analysis_file}")
        
        # Restore original config
        config.output_path = original_output_path
        
    else:
        logger.info("Running standard pipeline without datastore")
        # Update config to use enhanced output path
        original_output_path = config.output_path
        config.output_path = str(enhanced_output_path)
        
        run_report_pipeline(config)
        
        # Restore original config
        config.output_path = original_output_path


def generate_datastore_analysis(output_path: str, instruments: List[str]) -> str:
    """
    Generate a comprehensive datastore analysis report.
    
    Args:
        output_path: Path to save the analysis report
        instruments: List of instruments to analyze
        
    Returns:
        Path to the generated analysis file
    """
    datastore = EnhancedDatastore(get_datastore_path())
    
    analysis_content = []
    analysis_content.append("="*80)
    analysis_content.append("DATASTORE ANALYSIS REPORT")
    analysis_content.append("="*80)
    analysis_content.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    analysis_content.append("")
    
    for instrument in instruments:
        analysis_content.append(f"INSTRUMENT: {instrument}")
        analysis_content.append("-" * 40)
        
        # Get dashboard data
        dashboard = datastore.generate_quality_dashboard(instrument)
        
        # Summary
        summary = dashboard.get('summary', {})
        analysis_content.append(f"Error Rate Trend: {summary.get('error_rate_trend', 'N/A')}")
        analysis_content.append(f"Current Error Rate: {summary.get('current_error_rate', 0):.2f}%")
        analysis_content.append(f"Average Error Rate: {summary.get('average_error_rate', 0):.2f}%")
        analysis_content.append(f"Total Historical Runs: {summary.get('total_historical_runs', 0)}")
        analysis_content.append("")
        
        # Patterns
        patterns = dashboard.get('patterns', {})
        analysis_content.append(f"Pattern Analysis:")
        analysis_content.append(f"  Repeated Patterns: {patterns.get('repeated_patterns', 0)}")
        analysis_content.append(f"  Error Clusters: {patterns.get('error_clusters', 0)}")
        analysis_content.append(f"  Systematic Issues: {patterns.get('systematic_issues', 0)}")
        analysis_content.append("")
        
        # Top patterns
        top_patterns = patterns.get('top_patterns', [])
        if top_patterns:
            analysis_content.append("Top Repeated Patterns:")
            for pattern in top_patterns:
                analysis_content.append(f"  - {pattern['ptid']} - {pattern['variable']}: {pattern['count']} times")
        
        # Systematic issues
        systematic = patterns.get('systematic_issues_detail', [])
        if systematic:
            analysis_content.append("Systematic Issues:")
            for issue in systematic:
                analysis_content.append(f"  - {issue['variable']} ({issue['error_type']}): {issue['count']} occurrences")
        
        analysis_content.append("")
        analysis_content.append("="*40)
        analysis_content.append("")
    
    # Save analysis report
    output_file = Path(output_path) / f"datastore_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write('\n'.join(analysis_content))
    
    logger.info(f"Datastore analysis report saved to: {output_file}")
    return str(output_file)

def run_report_pipeline(config: QCConfig, enable_datastore: Optional[bool] = None):
    """
    Main entry point for the QC report pipeline.

    This function orchestrates the entire process, from fetching data to
    generating the final reports.

    Args:
        config: The configuration object for the pipeline.
        enable_datastore: Whether to enable datastore functionality.
                         If None, auto-enables for complete_visits mode.
    """
    # Auto-enable datastore for complete_visits mode if not specified
    if enable_datastore is None:
        enable_datastore = (config.mode == 'complete_visits')
    
    # Only enable datastore for complete_visits mode
    if config.mode != 'complete_visits':
        enable_datastore = False
    
    print("")
    print("="*80)
    print("⏲️ STARTING QC REPORT PIPELINE")
    if enable_datastore:
        print("🗄️ DATABASE TRACKING ENABLED")
    print("="*80)
    print("")
    
    # Create the main output directory based on run type and date
    run_type_str = config.mode.replace("_", " ").title().replace(" ", "")
    date_tag = datetime.datetime.today().strftime("%d%b%Y").upper()
    run_dir_name = f"QC_{run_type_str}_{date_tag}"

    output_path = Path(config.output_path) / run_dir_name
    output_path.mkdir(parents=True, exist_ok=True)

    (
        df_errors,
        df_logs,
        df_passed,
        all_records_df,
        complete_visits_df,
        detailed_logs_df,
    ) = process_instruments_etl(config, output_path)

    export_results_to_csv(
        df_errors,
        df_logs,
        df_passed,
        all_records_df,
        complete_visits_df,
        detailed_logs_df,
        output_dir=output_path,
    )

    if not all_records_df.empty:
        generate_aggregate_error_count_report(
            df_errors,
            config.instruments,
            all_records_df,
            output_dir=output_path,
            primary_key_field=config.primary_key_field,
        )
        generate_tool_status_reports(
            processed_records_df=all_records_df,
            pass_fail_log=[
                {str(k): v for k, v in row.items()}
                for row in detailed_logs_df.to_dict("records")
            ],
            output_dir=output_path,
            file_suffix=date_tag,
            qc_run_by=config.user_initials or "N/A",
            primary_key_field=config.primary_key_field,
            errors_df=df_errors,
            instruments=config.instruments,
        )

    # Store validation data in database if enabled
    if enable_datastore:
        try:
            db_summary = _store_validation_in_database(
                df_errors, all_records_df, config, output_path
            )
            logger.info(f"Database storage complete: {db_summary}")
        except Exception as e:
            logger.error(f"Database storage failed: {e}")
            # Don't fail the entire pipeline if database storage fails

def _store_validation_in_database(df_errors: pd.DataFrame, 
                                 all_records_df: pd.DataFrame,
                                 config: QCConfig,
                                 output_path: Path) -> Dict[str, Any]:
    """
    Store validation results in the database and create a summary file.
    
    Args:
        df_errors: DataFrame containing validation errors
        all_records_df: DataFrame containing all processed records
        config: Configuration object
        output_path: Path to output directory
        
    Returns:
        Dictionary with database storage summary
    """
    datastore = EnhancedDatastore(get_datastore_path())
    
    # Create timestamp for run ID
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Group by instrument and store each separately
    instruments = config.instruments if config.instruments else ['all_instruments']
    stored_runs = []
    
    for instrument in instruments:
        # Filter errors for this instrument if possible
        if 'instrument' in df_errors.columns:
            instrument_errors = df_errors[df_errors['instrument'] == instrument]
        else:
            instrument_errors = df_errors
            
        # Create run ID for tracking
        expected_run_id = f"{instrument}_{timestamp}"
        
        # Store in database
        run_id = datastore.store_validation_run(
            instrument=instrument,
            errors_df=instrument_errors,
            total_records=len(all_records_df),
            run_config={
                'mode': config.mode,
                'user_initials': config.user_initials,
                'timestamp': timestamp
            }
        )
        
        stored_runs.append({
            'run_id': run_id or expected_run_id,
            'instrument': instrument,
            'total_records': len(all_records_df),
            'total_errors': len(instrument_errors)
        })
    
    # Create database summary file
    db_summary = {
        'timestamp': timestamp,
        'database_path': get_datastore_path(),
        'mode': config.mode,
        'total_instruments': len(instruments),
        'stored_runs': stored_runs,
        'total_records_processed': len(all_records_df),
        'total_errors_found': len(df_errors)
    }
    
    # Write database summary to file
    db_summary_file = output_path / f"DATABASE_SUMMARY_{timestamp}.json"
    with open(db_summary_file, 'w', encoding='utf-8') as f:
        json.dump(db_summary, f, indent=2, ensure_ascii=False)
    
    # Also create a human-readable summary
    readable_summary_file = output_path / f"DATABASE_SUMMARY_{timestamp}.txt"
    with open(readable_summary_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("DATABASE STORAGE SUMMARY\n")
        f.write("="*80 + "\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"Database Path: {get_datastore_path()}\n")
        f.write(f"Mode: {config.mode}\n")
        f.write(f"Total Records Processed: {len(all_records_df)}\n")
        f.write(f"Total Errors Found: {len(df_errors)}\n")
        f.write(f"Total Instruments: {len(instruments)}\n")
        f.write("\n" + "="*80 + "\n")
        f.write("STORED RUNS:\n")
        f.write("="*80 + "\n")
        
        for run in stored_runs:
            f.write(f"Run ID: {run['run_id']}\n")
            f.write(f"  Instrument: {run['instrument']}\n")
            f.write(f"  Records: {run['total_records']}\n")
            f.write(f"  Errors: {run['total_errors']}\n")
            f.write(f"  Error Rate: {(run['total_errors'] / run['total_records'] * 100):.2f}%\n")
            f.write("\n")
    
    logger.info(f"Database summary saved to: {db_summary_file}")
    logger.info(f"Human-readable summary saved to: {readable_summary_file}")
    
    return db_summary


def _collect_processed_records_info(
    df: pd.DataFrame, instrument: str, primary_key_field: str
) -> pd.DataFrame:
    """
    Collects key information about processed records for status reporting.

    This includes ptid, event name, instrument, and the discriminant
    variable for dynamic instruments.

    Args:
        df: The DataFrame of records processed for a single instrument.
        instrument: The name of the instrument.
        primary_key_field: The name of the primary key field.

    Returns:
        A DataFrame with essential information for status reports.
    """
    info_cols = [primary_key_field, "redcap_event_name"]
    rec = df[info_cols].copy()
    rec["instrument_name"] = instrument

    if is_dynamic_rule_instrument(instrument):
        discriminant_var = get_discriminant_variable(instrument)
        if discriminant_var in df.columns:
            rec[discriminant_var] = df[discriminant_var]
        else:
            rec[discriminant_var] = None

    return rec


# ───────────────────────────────── Data Validation with Json Rules ─────────────────────────────────
def validate_data(
    data: pd.DataFrame,
    validation_rules: Dict[str, Any],
    instrument_name: str,
    primary_key_field: str,
    event_name: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validates a DataFrame of instrument data against a set of rules.

    The validation process is two-fold:
    1.  **Vectorized Simple Checks**: Fast, bulk checks for types, ranges,
        and allowed values are performed on the entire DataFrame.
    2.  **Per-Record Complex Checks**: For logic that cannot be vectorized
        (e.g., conditional fields), records are iterated for in-depth validation.

    Args:
        data: DataFrame containing the data for a specific instrument.
        validation_rules: A dictionary of JSON validation rules for the instrument.
        instrument_name: The name of the instrument being validated.
        event_name: If provided, filters the DataFrame to this specific event.

    Returns:
        A tuple containing:
        - A list of dictionaries, where each dictionary is a validation error.
        - A list of dictionaries representing detailed validation logs.
        - A list of dictionaries for validations that passed.
    """
    errors: List[Dict[str, Any]] = []
    validation_logs: List[Dict[str, Any]] = []
    passed_validations: List[Dict[str, Any]] = []

    df = data.copy()
    if event_name:
        df = df[df["redcap_event_name"] == event_name]

    # --- Handle instruments with dynamic rule selection ---
    if is_dynamic_rule_instrument(instrument_name):
        df, dynamic_errors = process_dynamic_validation(df, instrument_name)
        errors.extend(dynamic_errors)
    else:
        errs, df = _run_vectorized_simple_checks(df, validation_rules, instrument_name)
        errors.extend(errs)

    # --- Per-record complex validation ---
    # Build schema without temporal rules since datastore is not available in this context
    cerb_schema = build_cerberus_schema_for_instrument(
        instrument_name, 
        include_temporal_rules=False,  # Skip temporal rules when datastore is not available
        include_compatibility_rules=True  # Keep compatibility rules for proper validation
    )

    for _, row in df.iterrows():
        record = row.to_dict()

        qc, rules = _get_schema_and_rules_for_record(
            record, cerb_schema, instrument_name, validation_rules, primary_key_field
        )

        result = qc.validate_record(record)

        _log_validation_results(
            record,
            rules,
            result.errors,
            qc,
            instrument_name,
            errors,
            validation_logs,
            passed_validations,
            primary_key_field,
        )

    return errors, validation_logs, passed_validations

def _get_schema_and_rules_for_record(
    record: Dict[str, Any],
    cerb_schema: Dict[str, Any],
    instrument_name: str,
    default_rules: Dict[str, Any],
    primary_key_field: str,
) -> Tuple[QualityCheck, Dict[str, Any]]:
    """
    Selects the appropriate schema and rules for a record.
    
    Handles dynamic instruments by selecting a sub-schema and rules based on a
    discriminant variable's value in the record.

    Args:
        record: The data record (as a dictionary).
        cerb_schema: The top-level Cerberus schema for the instrument.
        instrument_name: The name of the instrument.
        default_rules: The default set of validation rules.

    Returns:
        A tuple containing the configured `QualityCheck` object and the
        applicable dictionary of validation rules.
    """
    if is_dynamic_rule_instrument(instrument_name):
        discriminant_var = get_discriminant_variable(instrument_name)
        variant = str(record.get(discriminant_var, "")).upper()
        
        # Fallback to the first defined variant if the key is missing or empty
        if not variant or variant not in cerb_schema:
            variant = list(cerb_schema.keys())[0]

        sub_schema = cerb_schema[variant]
        qc = QualityCheck(pk_field=primary_key_field, schema=sub_schema)
        # Load the specific rules for this variant
        rules = load_dynamic_rules_for_instrument(instrument_name)[variant]
    else:
        qc = QualityCheck(pk_field=primary_key_field, schema=cerb_schema)
        rules = default_rules

    return qc, rules


def _log_validation_results(
    record: Dict[str, Any],
    rules: Dict[str, Any],
    errs_dict: Dict[str, Any],
    qc: QualityCheck,
    instrument_name: str,
    errors: List[Dict[str, Any]],
    validation_logs: List[Dict[str, Any]],
    passed_validations: List[Dict[str, Any]],
    primary_key_field: str,
):
    """
    Logs the outcome of a validation check for each field in a record.

    For each variable in the rule set, this function records whether it passed
    or failed validation, creating detailed log entries.

    Args:
        record: The record that was validated.
        rules: The validation rules applied to the record.
        errs_dict: A dictionary of errors from the validator.
        qc: The `QualityCheck` instance used for validation.
        instrument_name: The name of the instrument.
        errors: The master list of errors to append to.
        validation_logs: The master list of validation logs to append to.
        passed_validations: The master list of passed validations to append to.
        primary_key_field: The name of the primary key field.
    """
    pk_val = record.get(primary_key_field)
    event = record.get("redcap_event_name")

    # Get the correct rule mapping based on instrument type
    if is_dynamic_rule_instrument(instrument_name):
        # For dynamic instruments, the rules are already specific, so we can get the mapping directly
        instrument_json_mapping = get_rule_mappings(instrument_name)
        # The variant is needed to get the correct file
        discriminant_var = get_discriminant_variable(instrument_name)
        variant = str(record.get(discriminant_var, "")).upper()
        files = instrument_json_mapping.get(variant, [])
    else:
        # For standard instruments, get the global mapping
        instrument_json_mapping = get_instrument_json_mapping()
        files = instrument_json_mapping.get(instrument_name, [])

    for var, var_rules in rules.items():
        raw_val = record.get(var)
        # Use the validator's type casting to get the interpreted value
        str_val = str(raw_val) if raw_val is not None else ""
        interp_val = qc.validator.cast_record({var: str_val}).get(var, raw_val)

        expected_t = var_rules.get("type")
        fld_errs = errs_dict.get(var, [])
        err_msg = fld_errs[0] if fld_errs else None

        rule_file = ",".join(files) if isinstance(files, list) else files

        validation_logs.append(
            {
                primary_key_field: pk_val,
                "variable": var,
                "json_rule": json.dumps(var_rules),
                "rule_file": rule_file,
                "redcap_event_name": event,
                "instrument_name": instrument_name,
            }
        )

        if err_msg:
            errors.append(
                {
                    primary_key_field: pk_val,
                    "redcap_event_name": event,
                    "instrument_name": instrument_name,
                    "variable": var,
                    "current_value": interp_val,
                    "expected_value": expected_t,
                    "error": err_msg,
                }
            )
        else:
            passed_validations.append(
                {
                    primary_key_field: pk_val,
                    "variable": var,
                    "current_value": interp_val,
                    "json_rule": json.dumps(var_rules),
                    "rule_file": rule_file,
                    "redcap_event_name": event,
                    "instrument_name": instrument_name,
                }
            )


# ──────────────────────────────────── Main ETL-Optimized Processing Function ─────────────────────────────────


def process_instruments_etl(
    config: QCConfig,
    output_path: Optional[Union[str, Path]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Orchestrates the ETL-optimized processing of instruments based on a config.

    Args:
        config: A `QCConfig` object containing all pipeline settings.
        output_path: Optional path to use for ETL output. If None, uses config.output_path.

    Returns:
        A tuple of DataFrames:
        (df_errors, df_logs, df_passed, all_records_df, complete_visits_df, detailed_validation_logs)
    """
    output_dir = Path(config.output_path)
    output_dir.mkdir(exist_ok=True)

    # Step 1: Load all necessary validation rules into a cache
    logger.info(f"Loading validation rules for {len(config.instruments)} instruments")
    rules_cache = load_rules_for_instruments(config.instruments)

    # Step 2: Fetch data using the ETL approach with upfront filtering
    logger.info("Fetching data using configuration-driven ETL approach.")
    try:
        data_df = fetch_etl_data(config, output_path)
        logger.info(f"ETL fetch completed: {len(data_df)} records ready for processing")
    except Exception as e:
        logger.error(f"ETL fetch failed: {e}", exc_info=True)
        raise RuntimeError(f"ETL data fetch failed: {e}") from e

    # Step 3: Apply complete visits filtering BEFORE building the instrument data cache
    complete_visits_df = pd.DataFrame()
    if config.mode == "complete_visits" and not data_df.empty:
        complete_visits_df, _ = build_complete_visits_df(data_df, config.instruments)
        
        # Filter data_df to only include records from complete visits
        if not complete_visits_df.empty:
            # Create a mask for complete visits
            complete_visits_mask = data_df.set_index(['ptid', 'redcap_event_name']).index.isin(
                complete_visits_df.set_index(['ptid', 'redcap_event_name']).index
            )
            data_df = data_df[complete_visits_mask].copy()
            logger.info(f"Filtered to {len(data_df)} records from {len(complete_visits_df)} complete visits")
        else:
            logger.warning("No complete visits found - no data will be processed")
            data_df = pd.DataFrame()  # Empty the dataframe if no complete visits

    # Step 4: Prepare data and mappings with filtered data
    if not data_df.empty:
        debug_info = debug_variable_mapping(data_df, config.instruments, rules_cache)
        logger.info(f"Variable mapping analysis: {debug_info['mapping_summary']['overall_coverage']:.1f}% coverage")
        for instrument, missing_vars in debug_info['missing_variables'].items():
            if missing_vars:
                logger.warning(f"Missing variables for {instrument}: {missing_vars[:5]}{'...' if len(missing_vars) > 5 else ''}")

    _, instrument_variable_map = build_variable_maps(config.instruments, rules_cache)
    instrument_data_cache = {}
    if not data_df.empty:
        instrument_data_cache = prepare_instrument_data_cache(
            data_df,
            config.instruments,
            instrument_variable_map,
            rules_cache,
            config.primary_key_field,
        )

    logger.info("Starting validation processing...")

    all_errors: List[Dict[str, Any]] = []
    all_logs: List[Dict[str, Any]] = []
    all_passed: List[Dict[str, Any]] = []
    records_for_status: List[pd.DataFrame] = []
    detailed_validation_logs: List[Dict[str, Any]] = []

    # Step 5: Process each instrument
    for i, instrument in enumerate(config.instruments, 1):
        logger.info(f"Processing {instrument} ({i}/{len(config.instruments)})")
        df = instrument_data_cache.get(instrument, pd.DataFrame())
        if df.empty:
            logger.warning(f"No data available for instrument '{instrument}' after ETL filtering.")
            continue
        
        # Build screening logs based on instrument completeness
        logs_for_this = build_detailed_validation_logs(
            df, instrument, primary_key_field=config.primary_key_field
        )
        detailed_validation_logs.extend(logs_for_this)
        
        rules = rules_cache[instrument]
        df = _preprocess_cast_types(df, rules)
        errors, logs, passed_records = validate_data(
            df, rules, instrument_name=instrument, primary_key_field=config.primary_key_field
        )
        
        all_errors.extend(errors)
        all_logs.extend(logs)
        all_passed.extend(passed_records)
        records_for_status.append(
            _collect_processed_records_info(
                df, instrument, primary_key_field=config.primary_key_field
            )
        )

    df_errors = pd.DataFrame(all_errors) if all_errors else pd.DataFrame()
    df_logs = pd.DataFrame(all_logs) if all_logs else pd.DataFrame()
    df_passed = pd.DataFrame(all_passed) if all_passed else pd.DataFrame()
    
    all_records_df = pd.DataFrame()
    if records_for_status:
        all_records_df = pd.concat(records_for_status, ignore_index=True).drop_duplicates(
            subset=[config.primary_key_field, "redcap_event_name", "instrument_name"]
        )

    logger.info(
        f"🎯 VALIDATION SUMMARY: {len(df_errors)} errors found across {len(config.instruments)} instruments"
    )

    print("")
    print("="*80)
    print("🎉 ETL INSTRUMENT PROCESSING COMPLETED SUCCESSFULLY")
    print("="*80)

    return (
        df_errors,
        df_logs,
        df_passed,
        all_records_df,
        complete_visits_df,
        pd.DataFrame(detailed_validation_logs) if detailed_validation_logs else pd.DataFrame(),
    )

# ───────────────────────────────── Export Functions ─────────────────────────────────
def export_results_to_csv(
    df_errors: pd.DataFrame,
    df_logs: pd.DataFrame,
    df_passed: pd.DataFrame,
    all_records_df: pd.DataFrame,
    complete_visits_df: pd.DataFrame,
    detailed_validation_logs_df: pd.DataFrame,
    output_dir: Path,
):
    """
    Exports the results of the ETL process to CSV files in organized directories.

    Args:
        df_errors: DataFrame of all validation errors.
        df_logs: DataFrame of comprehensive validation logs.
        df_passed: DataFrame of all passed validations.
        all_records_df: DataFrame with info on all processed records.
        complete_visits_df: DataFrame of completed visits.
        detailed_validation_logs_df: DataFrame of pre-validation screening logs.
        output_dir: The base directory for output files.
    """
    date_tag = datetime.datetime.today().strftime("%d%b%Y").upper()

    # --- Save Key Summary Files to the Run-Specific Directory ---
    if not df_errors.empty:
        df_errors.to_csv(output_dir / f"final_error_dataset_{date_tag}.csv", index=False)

    if not complete_visits_df.empty:
        complete_visits_df.to_csv(
            output_dir / f"complete_visits_dataset_{date_tag}.csv", index=False
        )

    # --- Create Subdirectories for Detailed Logs ---
    validation_logs_dir = output_dir / "Validation_Logs"
    validation_logs_dir.mkdir(exist_ok=True)

    # --- Save Detailed Logs to Validation_Logs Subdirectory ---
    if not df_logs.empty:
        df_logs.to_csv(
            validation_logs_dir / f"comprehensive_validation_logs_{date_tag}.csv",
            index=False,
        )

    if not df_passed.empty:
        df_passed.to_csv(
            validation_logs_dir / f"passed_validations_{date_tag}.csv", index=False
        )

    if not detailed_validation_logs_df.empty:
        detailed_validation_logs_df.to_csv(
            validation_logs_dir / f"record_event_screening_logs_{date_tag}.csv",
            index=False,
        )

    print(f"📁 KEY SUMMARY FILES SAVED TO: {output_dir}")
    print(f"📁 DETAILED LOGS SAVED TO: {validation_logs_dir}")


# ── Aggregate Error Count Report ────────────────────────────────────────────────
def generate_aggregate_error_count_report(
    df_errors: pd.DataFrame,
    instrument_list: List[str],
    all_records_df: pd.DataFrame,
    output_dir: Path,
    primary_key_field: str,
):
    """
    Summarizes error counts per ptid & event, writing the report to the output directory.
    
    Args:
        df_errors: DataFrame containing all validation errors.
        instrument_list: List of all instruments included in the run.
        all_records_df: DataFrame containing all records that were processed.
        output_dir: The directory to save the report to.
        primary_key_field: The name of the primary key field.
    """
    if all_records_df.empty:
        logger.warning("No records found — skipping aggregate error report.")
        return

    combos = (
        all_records_df[[primary_key_field, "redcap_event_name"]]
        .drop_duplicates()
        .reset_index()
        .drop(columns="index")
    )

    if df_errors.empty:
        report = combos.copy()
        for instr in instrument_list:
            report[instr] = 0
    else:
        counts = (
            df_errors.groupby(
                [primary_key_field, "redcap_event_name", "instrument_name"]
            )
            .size()
            .reset_index(name="error_count")
        )
        pivot = counts.pivot_table(
            index=[primary_key_field, "redcap_event_name"],
            columns="instrument_name",
            values="error_count",
            fill_value=0,
        ).reset_index()
        report = combos.merge(
            pivot, on=[primary_key_field, "redcap_event_name"], how="left"
        )

    for instr in instrument_list:
        if instr not in report.columns:
            report[instr] = 0
        report[instr] = report[instr].fillna(0).astype(int)

    report["total_error_count"] = report[instrument_list].sum(axis=1)
    cols = (
        [primary_key_field, "redcap_event_name"]
        + instrument_list
        + ["total_error_count"]
    )
    report = report[cols]

    date_tag = datetime.datetime.today().strftime("%d%b%Y").upper()
    path = output_dir / f"QC_Report_ErrorCount_{date_tag}.csv"
    report.to_csv(path, index=False)
    print(f"📊 AGGREGATE ERROR COUNT REPORT GENERATED AND SAVED TO: {path}")


# ── Tool Status Reports ─────────────────────────────────────────────────────────
def generate_tool_status_reports(
    processed_records_df: pd.DataFrame,
    pass_fail_log: List[Dict[str, Any]],
    output_dir: Path,
    file_suffix: str,
    qc_run_by: str,
    primary_key_field: str,
    errors_df: pd.DataFrame,
    instruments: List[str],
):
    """
    Generates a single QC status report CSV in the specified wide format.
    Also exports a JSON file with selected columns.

    Args:
        processed_records_df: DataFrame with information on all processed records.
        pass_fail_log: List of pass/fail logs for each record and instrument.
        output_dir: The directory to save the report.
        file_suffix: Suffix for the report file, typically the date.
        qc_run_by: The identifier for who ran the QC.
        primary_key_field: The name of the primary key field.
        errors_df: DataFrame containing all validation errors.
        instruments: List of all instruments in the run.
    """
    if processed_records_df.empty:
        logger.warning("No processed records found — skipping status report.")
        return

    # Start with a unique list of visits
    status_report_df = processed_records_df[[primary_key_field, "redcap_event_name"]].drop_duplicates().reset_index(drop=True)

    # Pivot the errors to get a pass/fail status for each instrument
    if not errors_df.empty:
        error_pivot = errors_df.pivot_table(
            index=[primary_key_field, "redcap_event_name"],
            columns="instrument_name",
            aggfunc='size',
            fill_value=0
        )
        # A value > 0 means there was at least one error, so it's a "Fail"
        for instrument in error_pivot.columns:
            error_pivot[instrument] = error_pivot[instrument].apply(lambda x: 'Fail' if x > 0 else 'Pass')
        
        # Merge the error status back into the main report
        status_report_df = status_report_df.merge(error_pivot, on=[primary_key_field, "redcap_event_name"], how="left")
    
    # Ensure all instrument columns exist, filling with "Pass" if no errors were found
    for instrument in instruments:
        if instrument not in status_report_df.columns:
            status_report_df[instrument] = "Pass"
        else:
            status_report_df[instrument] = status_report_df[instrument].fillna("Pass")

    # --- Add reporting metrics ---
    instrument_statuses = status_report_df[instruments]
    all_passed_mask = (instrument_statuses == 'Pass').all(axis=1)
    status_report_df['qc_status_complete'] = np.where(all_passed_mask, '2', '0')
    status_report_df['qc_run_by'] = qc_run_by
    status_report_df['qc_last_run'] = datetime.datetime.today().strftime("%Y-%m-%d")
    failed_instruments_summary = instrument_statuses.apply(
        lambda row: f"Failed in instruments: {', '.join(row[row == 'Fail'].index)}",
        axis=1
    )
    status_report_df['qc_status'] = np.where(all_passed_mask, 'All Passed', failed_instruments_summary)
    status_report_df['quality_control_check_complete'] = status_report_df['qc_status_complete']

    # Add form_header column (if not present, fill with empty string)
    if "form_header" not in status_report_df.columns:
        status_report_df["form_header"] = ""

    # Reorder columns to match the required format
    final_columns = [primary_key_field, "redcap_event_name"] + instruments + \
                    ['qc_status_complete', 'qc_run_by', 'qc_last_run', 'qc_status', 'quality_control_check_complete']
    status_report_df = status_report_df[final_columns]

    # Save the report to CSV
    report_path = output_dir / f"QC_Status_Report_{file_suffix}.csv"
    status_report_df.to_csv(report_path, index=False)
    print(f"📊 STATUS REPORT GENERATED AND SAVED TO: {report_path}")

    # --- Export selected columns to JSON ---
    json_columns = [
        primary_key_field,
        "redcap_event_name",
        "qc_status_complete",
        "qc_run_by",
        "qc_last_run",
        "qc_status",
        "quality_control_check_complete",
    ]
    # Ensure all columns exist
    for col in json_columns:
        if col not in status_report_df.columns:
            status_report_df[col] = ""

    json_export_df = status_report_df[json_columns]
    json_records = json_export_df.to_dict(orient="records")
    # Use upload_ready_path from config_manager instead of json_path
    json_path = Path(upload_ready_path) / f"QC_Status_Report_{file_suffix}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_records, f, indent=2)
    print(f"📊 STATUS REPORT JSON EXPORTED TO: {json_path}")