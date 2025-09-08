#!/usr/bin/env python3
"""
Performance Analysis Tool for UDSv4 REDCap QC Validator

Measures execution time for each pipeline stage and identifies bottlenecks.
"""

import re
import subprocess
import time
from pathlib import Path
from typing import Dict

import pandas as pd


def run_pipeline_with_timing(mode: str, detailed: bool = False) -> Dict[str, float]:
    """Run the pipeline and extract timing information from logs."""

    # Build command
    python_exe = "C:/Users/johtorres/Documents/Github_Repos/final-projects/(Step 1) udsv4-redcap-qc-validator/.venv/Scripts/python.exe"
    cmd = [python_exe, "-m", "src.cli.cli", "run", "-i", "PERF", "-l"]
    if detailed:
        cmd.append("-dr")

    print(f"Running {'detailed' if detailed else 'standard'} mode...")
    print(f"Command: {' '.join(cmd)}")

    # Run pipeline and capture output
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())
    total_wall_time = time.time() - start_time

    if result.returncode != 0:
        print(f"Pipeline failed: {result.stderr}")
        return {}

    # Parse timing information from logs
    output_lines = result.stdout.split('\n')
    timings = {
        'total_wall_time': total_wall_time,
        'stage_1_data_fetch': 0.0,
        'stage_2_rules_loading': 0.0,
        'stage_3_data_preparation': 0.0,
        'stage_4_validation': 0.0,
        'stage_5_report_generation': 0.0,
        'pipeline_total': 0.0
    }

    # Extract stage timings from log output
    for line in output_lines:
        if 'Data fetch completed:' in line:
            match = re.search(r'(\d+\.?\d*) records in (\d+\.?\d*)s', line)
            if match:
                timings['stage_1_data_fetch'] = float(match.group(2))

        elif 'Rules loading completed:' in line:
            match = re.search(r'in (\d+\.?\d*)s', line)
            if match:
                timings['stage_2_rules_loading'] = float(match.group(1))

        elif 'Data preparation completed:' in line:
            match = re.search(r'in (\d+\.?\d*)s', line)
            if match:
                timings['stage_3_data_preparation'] = float(match.group(1))

        elif 'Validation completed:' in line:
            match = re.search(r'in (\d+\.?\d*)s', line)
            if match:
                timings['stage_4_validation'] = float(match.group(1))

        elif 'Report generation completed:' in line:
            match = re.search(r'in (\d+\.?\d*)s', line)
            if match:
                timings['stage_5_report_generation'] = float(match.group(1))

        elif 'Total execution time:' in line:
            match = re.search(r'(\d+\.?\d*)s', line)
            if match:
                timings['pipeline_total'] = float(match.group(1))

    return timings


def analyze_detailed_reports(output_dir: Path) -> Dict[str, Dict]:
    """Analyze the generated reports for file sizes and row counts."""

    report_analysis = {}

    # Core reports (always generated)
    core_reports = {
        'Errors': 'Final_Error_Dataset_*.csv',
        'Data_Fetched': 'Data_Fetched_*.csv',
        'JSON_Status': 'QC_Status_Report_*.json'
    }

    # Detailed reports (only in detailed mode)
    detailed_reports = {
        'Validation_Logs': 'Log_EventCompletenessScreening_*.csv',
        'Passed_Validations': 'Log_PassedValidations_*.csv',
        'Aggregate_Errors': 'QC_Report_ErrorCount_*.csv',
        'Status_Report': 'QC_Status_Report_*.csv',
        'PTID_Visits': 'PTID_CompletedVisits_*.csv',
        'Rules_Validation': 'Log_RulesValidation_*.csv',
        'Generation_Summary': 'Generation_Summary_*.csv'
    }

    all_reports = {**core_reports, **detailed_reports}

    for report_name, pattern in all_reports.items():
        files = list(output_dir.rglob(pattern))
        if files:
            file_path = files[0]  # Take the most recent
            file_size_mb = file_path.stat().st_size / (1024 * 1024)

            # Count rows for CSV files
            row_count = 0
            if file_path.suffix == '.csv':
                try:
                    df = pd.read_csv(file_path)
                    row_count = len(df)
                except BaseException:
                    row_count = -1

            report_analysis[report_name] = {
                'file_size_mb': file_size_mb,
                'row_count': row_count,
                'file_path': str(file_path)
            }

    return report_analysis


def print_performance_summary(standard_timings: Dict, detailed_timings: Dict,
                              standard_reports: Dict, detailed_reports: Dict):
    """Print a comprehensive performance analysis."""

    print("\n" + "=" * 80)
    print("PERFORMANCE ANALYSIS RESULTS")
    print("=" * 80)

    # Stage-by-stage timing comparison
    print("\n📊 STAGE TIMING COMPARISON:")
    print("-" * 60)
    print(f"{'Stage':<25} {'Standard':<12} {'Detailed':<12} {'Difference':<12}")
    print("-" * 60)

    stages = [
        ('Data Fetching', 'stage_1_data_fetch'),
        ('Rules Loading', 'stage_2_rules_loading'),
        ('Data Preparation', 'stage_3_data_preparation'),
        ('Validation', 'stage_4_validation'),
        ('Report Generation', 'stage_5_report_generation'),
        ('Total Pipeline', 'pipeline_total'),
        ('Wall Clock Time', 'total_wall_time')
    ]

    for stage_name, key in stages:
        std_time = standard_timings.get(key, 0)
        det_time = detailed_timings.get(key, 0)
        diff = det_time - std_time
        print(f"{stage_name:<25} {std_time:<12.2f} {det_time:<12.2f} {diff:<12.2f}")

    # Report generation breakdown
    print("\n📁 REPORT GENERATION ANALYSIS:")
    print("-" * 60)

    report_gen_overhead = detailed_timings.get(
        'stage_5_report_generation', 0) - standard_timings.get('stage_5_report_generation', 0)
    print(f"Report generation overhead: {report_gen_overhead:.2f}s")
    print(f"This accounts for {(report_gen_overhead /
                                detailed_timings.get('pipeline_total', 1)) *
                               100:.1f}% of detailed run time")

    # File size analysis
    print("\n📈 FILE SIZE ANALYSIS:")
    print("-" * 60)

    # Core files
    print("Core Files (Standard + Detailed):")
    core_files = ['Errors', 'Data_Fetched', 'JSON_Status']
    for file_name in core_files:
        if file_name in detailed_reports:
            info = detailed_reports[file_name]
            print(
                f"  {
                    file_name:<20}: {
                    info['row_count']:>8,} rows, {
                    info['file_size_mb']:>8.2f} MB")

    # Detailed-only files
    print("\nDetailed-Only Files:")
    detailed_only = [
        'Validation_Logs',
        'Passed_Validations',
        'Rules_Validation',
        'Status_Report',
        'PTID_Visits']
    total_detailed_size = 0
    for file_name in detailed_only:
        if file_name in detailed_reports:
            info = detailed_reports[file_name]
            total_detailed_size += info['file_size_mb']
            print(
                f"  {
                    file_name:<20}: {
                    info['row_count']:>8,} rows, {
                    info['file_size_mb']:>8.2f} MB")

    print(f"\nTotal additional file size: {total_detailed_size:.2f} MB")

    # Performance bottlenecks
    print("\n🎯 PERFORMANCE BOTTLENECKS:")
    print("-" * 60)

    if 'Rules_Validation' in detailed_reports:
        rules_info = detailed_reports['Rules_Validation']
        print(
            f"⚠️  Rules Validation Log: {
                rules_info['row_count']:,} rows ({
                rules_info['file_size_mb']:.1f} MB)")
        print("   This is likely the main performance bottleneck in detailed mode")

    # Recommendations
    print("\n💡 OPTIMIZATION RECOMMENDATIONS:")
    print("-" * 60)
    print("1. Consider making Rules Validation Log optional or sampling-based")
    print("2. Implement lazy loading for large detailed reports")
    print("3. Add compression for large CSV exports")
    print("4. Consider parallel processing for independent report generation")


def main():
    """Main performance analysis function."""

    print("UDSv4 REDCap QC Validator - Performance Analysis")
    print("=" * 60)

    # Run standard mode
    standard_timings = run_pipeline_with_timing("standard", detailed=False)

    # Find the latest standard output directory
    output_dirs = list(Path('output').glob('QC_CompleteVisits_*'))
    if output_dirs:
        latest_standard_dir = max(output_dirs, key=lambda x: x.stat().st_mtime)
        standard_reports = analyze_detailed_reports(latest_standard_dir)
    else:
        standard_reports = {}

    print("Standard mode completed\n")

    # Run detailed mode
    detailed_timings = run_pipeline_with_timing("detailed", detailed=True)

    # Find the latest detailed output directory
    output_dirs = list(Path('output').glob('QC_CompleteVisits_*'))
    if output_dirs:
        latest_detailed_dir = max(output_dirs, key=lambda x: x.stat().st_mtime)
        detailed_reports = analyze_detailed_reports(latest_detailed_dir)
    else:
        detailed_reports = {}

    print("Detailed mode completed\n")

    # Print comprehensive analysis
    print_performance_summary(
        standard_timings,
        detailed_timings,
        standard_reports,
        detailed_reports)


if __name__ == "__main__":
    main()
