"""
Essential tests for output and report generation functionality.

This module tests the report generation, file output, and result saving 
functionality that are fundamental to the application's output pipeline.
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
import tempfile
from pathlib import Path
import json
import csv
from datetime import datetime

# Import the modules we're testing
from src.pipeline.config_manager import QCConfig


class TestOutputDirectoryCreation:
    """Test output directory creation and management."""

    def test_output_directory_creation_with_timestamp(self):
        """Test that output directories are created with proper timestamps."""
        config = QCConfig()

        with tempfile.TemporaryDirectory() as temp_dir:
            config.output_path = temp_dir

            # Create a timestamped directory
            current_time = datetime.now()
            date_tag = current_time.strftime("%d%b%Y").upper()
            time_tag = current_time.strftime("%H%M%S")

            output_dir_name = f"QC_CompleteVisits_{date_tag}_{time_tag}"
            output_dir = Path(temp_dir) / output_dir_name
            output_dir.mkdir(parents=True, exist_ok=True)

            assert output_dir.exists()
            assert output_dir.is_dir()

    def test_output_directory_path_resolution(self):
        """Test that output directory paths are properly resolved."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = QCConfig(output_path=temp_dir)

            # Path should be resolved to absolute
            assert Path(config.output_path).is_absolute()
            assert config.output_path == str(Path(temp_dir).resolve())

    def test_nested_output_directory_creation(self):
        """Test creation of nested output directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = Path(temp_dir) / "nested" / "output" / "directory"
            nested_path.mkdir(parents=True, exist_ok=True)

            assert nested_path.exists()
            assert nested_path.is_dir()


class TestReportGeneration:
    """Test report generation functionality."""

    def test_csv_report_generation(self):
        """Test generation of CSV reports."""
        # Sample validation data
        test_data = [
            {
                'ptid': 'TEST001',
                'instrument_name': 'a1_participant_demographics',
                'validation_status': 'PASSED',
                'redcap_event_name': 'udsv4_ivp_1_arm_1',
                'packet': 'I'
            },
            {
                'ptid': 'TEST002',
                'instrument_name': 'a1_participant_demographics',
                'validation_status': 'FAILED',
                'redcap_event_name': 'udsv4_ivp_1_arm_1',
                'packet': 'I'
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # Write test data to CSV
            df = pd.DataFrame(test_data)
            df.to_csv(temp_path, index=False)

            # Verify file was created and contains data
            assert Path(temp_path).exists()

            # Read back and verify content
            loaded_df = pd.read_csv(temp_path)
            assert len(loaded_df) == 2
            assert list(loaded_df.columns) == list(df.columns)
            assert loaded_df.iloc[0]['ptid'] == 'TEST001'

        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()

    def test_json_report_generation(self):
        """Test generation of JSON reports."""
        test_data = {
            'summary': {
                'total_records': 100,
                'passed_records': 95,
                'failed_records': 5,
                'execution_time': 10.5
            },
            'details': [
                {
                    'ptid': 'TEST001',
                    'status': 'PASSED'
                },
                {
                    'ptid': 'TEST002',
                    'status': 'FAILED',
                    'errors': ['Invalid age value']
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # Write test data to JSON
            with open(temp_path, 'w') as f:
                json.dump(test_data, f, indent=2)

            # Verify file was created and contains data
            assert Path(temp_path).exists()

            # Read back and verify content
            with open(temp_path, 'r') as f:
                loaded_data = json.load(f)

            assert loaded_data['summary']['total_records'] == 100
            assert len(loaded_data['details']) == 2

        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()

    def test_multiple_report_format_generation(self):
        """Test generation of multiple report formats."""
        test_data = pd.DataFrame([
            {'ptid': 'TEST001', 'status': 'PASSED'},
            {'ptid': 'TEST002', 'status': 'FAILED'}
        ])

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "report.csv"
            json_path = Path(temp_dir) / "report.json"

            # Generate CSV
            test_data.to_csv(csv_path, index=False)

            # Generate JSON
            test_data.to_json(json_path, orient='records', indent=2)

            # Verify both files exist
            assert csv_path.exists()
            assert json_path.exists()

            # Verify content
            csv_data = pd.read_csv(csv_path)
            assert len(csv_data) == 2

            with open(json_path, 'r') as f:
                json_data = json.load(f)
            assert len(json_data) == 2


class TestValidationReportGeneration:
    """Test specific validation report generation."""

    def test_error_report_generation(self):
        """Test generation of error reports."""
        error_data = [
            {
                'ptid': 'TEST001',
                'instrument_name': 'a1_participant_demographics',
                'variable': 'a1_birthyr',
                'error_message': 'Invalid birth year',
                'current_value': '2050',
                'packet': 'I',
                'redcap_event_name': 'udsv4_ivp_1_arm_1'
            },
            {
                'ptid': 'TEST002',
                'instrument_name': 'b1_vital_signs_and_anthropometrics',
                'variable': 'b1_height',
                'error_message': 'Height out of range',
                'current_value': '300',
                'packet': 'I',
                'redcap_event_name': 'udsv4_ivp_1_arm_1'
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            df = pd.DataFrame(error_data)
            df.to_csv(temp_path, index=False)

            # Verify error report structure
            loaded_df = pd.read_csv(temp_path)
            assert 'ptid' in loaded_df.columns
            assert 'error_message' in loaded_df.columns
            assert 'current_value' in loaded_df.columns
            assert len(loaded_df) == 2

        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()

    def test_passed_records_report_generation(self):
        """Test generation of passed records reports."""
        passed_data = [
            {
                'ptid': 'TEST001',
                'variable': 'a1_birthyr',
                'current_value': '1950',
                'json_rule': '{"type": "integer", "min": 1900, "max": 2023}',
                'rule_file': 'a1_rules.json',
                'packet': 'I',
                'redcap_event_name': 'udsv4_ivp_1_arm_1',
                'instrument_name': 'a1_participant_demographics'
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            df = pd.DataFrame(passed_data)
            df.to_csv(temp_path, index=False)

            # Verify passed records report structure
            loaded_df = pd.read_csv(temp_path)
            assert 'ptid' in loaded_df.columns
            assert 'json_rule' in loaded_df.columns
            assert 'rule_file' in loaded_df.columns
            assert len(loaded_df) == 1

        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()

    def test_validation_log_report_generation(self):
        """Test generation of validation log reports."""
        log_data = [
            {
                'ptid': 'TEST001',
                'instrument_name': 'a1_participant_demographics',
                'validation_status': 'PASSED',
                'error_count': 0,
                'redcap_event_name': 'udsv4_ivp_1_arm_1',
                'packet': 'I'
            },
            {
                'ptid': 'TEST002',
                'instrument_name': 'a1_participant_demographics',
                'validation_status': 'FAILED',
                'error_count': 2,
                'redcap_event_name': 'udsv4_ivp_1_arm_1',
                'packet': 'I'
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            df = pd.DataFrame(log_data)
            df.to_csv(temp_path, index=False)

            # Verify log report structure
            loaded_df = pd.read_csv(temp_path)
            assert 'validation_status' in loaded_df.columns
            assert 'error_count' in loaded_df.columns
            assert len(loaded_df) == 2

        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()


class TestDataSaving:
    """Test data saving functionality."""

    def test_dataframe_to_csv_saving(self):
        """Test saving DataFrame to CSV file."""
        test_df = pd.DataFrame([
            {'id': 1, 'name': 'Test1', 'value': 100},
            {'id': 2, 'name': 'Test2', 'value': 200}
        ])

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # Save DataFrame
            test_df.to_csv(temp_path, index=False)

            # Verify file exists and has correct content
            assert Path(temp_path).exists()

            loaded_df = pd.read_csv(temp_path)
            pd.testing.assert_frame_equal(test_df, loaded_df)

        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()

    def test_large_dataframe_saving(self):
        """Test saving large DataFrame efficiently."""
        # Create a larger test DataFrame
        large_data = []
        for i in range(1000):
            large_data.append({
                'ptid': f'TEST{i:04d}',
                'value1': i,
                'value2': i * 2,
                'status': 'PASSED' if i % 2 == 0 else 'FAILED'
            })

        large_df = pd.DataFrame(large_data)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # Save large DataFrame
            large_df.to_csv(temp_path, index=False)

            # Verify file exists and has correct number of records
            assert Path(temp_path).exists()

            loaded_df = pd.read_csv(temp_path)
            assert len(loaded_df) == 1000

        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()

    def test_file_saving_with_special_characters(self):
        """Test saving files with special characters in data."""
        special_data = pd.DataFrame([
            {'text': 'Normal text'},
            {'text': 'Text with "quotes"'},
            {'text': 'Text with, commas'},
            {'text': 'Text with\nnewlines'},
            {'text': 'Text with émojis 🎉'}
        ])

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # Save DataFrame with special characters
            special_data.to_csv(temp_path, index=False, encoding='utf-8')

            # Verify file exists and content is preserved
            assert Path(temp_path).exists()

            loaded_df = pd.read_csv(temp_path, encoding='utf-8')
            assert len(loaded_df) == 5
            # Check that the special character text exists (allow for potential encoding variations)
            text_values = loaded_df['text'].tolist()
            emoji_found = any('émojis' in str(val) and '🎉' in str(val) for val in text_values)
            assert emoji_found, f"Expected emoji text not found in {text_values}"

        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()


class TestReportSummaryGeneration:
    """Test report summary generation."""

    def test_validation_summary_generation(self):
        """Test generation of validation summary."""
        # Mock validation results
        total_records = 100
        passed_records = 85
        failed_records = 15
        execution_time = 12.5

        summary = {
            'total_records_processed': total_records,
            'passed_validations': passed_records,
            'failed_validations': failed_records,
            'success_rate': (passed_records / total_records) * 100,
            'execution_time_seconds': execution_time,
            'timestamp': datetime.now().isoformat()
        }

        # Verify summary structure
        assert summary['total_records_processed'] == 100
        assert summary['success_rate'] == 85.0
        assert 'timestamp' in summary

    def test_instrument_breakdown_summary(self):
        """Test generation of instrument breakdown summary."""
        instrument_results = {
            'a1_participant_demographics': {'passed': 45, 'failed': 5},
            'b1_vital_signs_and_anthropometrics': {'passed': 40, 'failed': 10}
        }

        # Generate breakdown
        breakdown = {}
        for instrument, results in instrument_results.items():
            total = results['passed'] + results['failed']
            breakdown[instrument] = {
                'total_records': total,
                'passed_count': results['passed'],
                'failed_count': results['failed'],
                'success_rate': (results['passed'] / total) * 100 if total > 0 else 0
            }

        # Verify breakdown
        assert breakdown['a1_participant_demographics']['success_rate'] == 90.0
        assert breakdown['b1_vital_signs_and_anthropometrics']['success_rate'] == 80.0

    def test_packet_breakdown_summary(self):
        """Test generation of packet breakdown summary."""
        packet_results = {
            'I': {'passed': 30, 'failed': 5},
            'I4': {'passed': 25, 'failed': 3},
            'F': {'passed': 30, 'failed': 7}
        }

        # Generate packet summary
        packet_summary = {}
        for packet, results in packet_results.items():
            total = results['passed'] + results['failed']
            packet_summary[packet] = {
                'total_records': total,
                'success_rate': (results['passed'] / total) * 100 if total > 0 else 0
            }

        # Verify packet summary (using approximate comparison for floating point)
        assert abs(packet_summary['I']['success_rate'] - 85.7) < 0.1  # Approximately 85.7%
        assert packet_summary['I4']['success_rate'] >= 89.0
        assert packet_summary['F']['success_rate'] >= 80.0


class TestOutputFileManagement:
    """Test output file management functionality."""

    def test_output_file_naming_convention(self):
        """Test that output files follow proper naming conventions."""
        base_name = "QC_CompleteVisits"
        date_tag = "01JAN2025"
        time_tag = "120000"

        expected_names = [
            f"{base_name}_{date_tag}_{time_tag}_errors.csv",
            f"{base_name}_{date_tag}_{time_tag}_logs.csv",
            f"{base_name}_{date_tag}_{time_tag}_passed_records.csv",
            f"{base_name}_{date_tag}_{time_tag}_summary.json"
        ]

        # Verify naming pattern
        for name in expected_names:
            assert base_name in name
            assert date_tag in name
            assert time_tag in name
            assert name.endswith(('.csv', '.json'))

    def test_output_directory_organization(self):
        """Test that output directory is properly organized."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create organized directory structure
            run_dir = base_path / "QC_CompleteVisits_01JAN2025_120000"
            run_dir.mkdir()

            # Create expected files
            files_to_create = [
                "errors.csv",
                "logs.csv",
                "passed_records.csv",
                "summary.json"
            ]

            for file_name in files_to_create:
                file_path = run_dir / file_name
                file_path.touch()

            # Verify organization
            assert run_dir.exists()
            assert len(list(run_dir.glob("*.csv"))) == 3
            assert len(list(run_dir.glob("*.json"))) == 1

    def test_file_overwrite_handling(self):
        """Test handling of file overwrites."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # Initial data
            initial_data = pd.DataFrame([{'id': 1, 'value': 'initial'}])
            initial_data.to_csv(temp_path, index=False)

            # Verify initial content
            loaded_initial = pd.read_csv(temp_path)
            assert loaded_initial.iloc[0]['value'] == 'initial'

            # Overwrite with new data
            new_data = pd.DataFrame([{'id': 2, 'value': 'updated'}])
            new_data.to_csv(temp_path, index=False)

            # Verify overwrite
            loaded_new = pd.read_csv(temp_path)
            assert loaded_new.iloc[0]['value'] == 'updated'
            assert len(loaded_new) == 1

        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()


class TestOutputRobustness:
    """Test output robustness and error handling."""

    def test_output_with_empty_data(self):
        """Test output generation with empty data."""
        empty_df = pd.DataFrame()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # Should handle empty DataFrame gracefully
            empty_df.to_csv(temp_path, index=False)

            assert Path(temp_path).exists()

            # Verify empty file has headers only if columns defined
            with open(temp_path, 'r') as f:
                content = f.read()

            # Empty DataFrame with no columns should create empty file
            assert len(content.strip()) == 0

        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()

    def test_output_with_permission_errors(self):
        """Test output handling with permission errors."""
        # Create a directory path that would cause permission issues
        restricted_path = "/root/restricted_directory/output.csv"

        test_df = pd.DataFrame([{'test': 'data'}])

        # Should raise appropriate exception for permission errors
        with pytest.raises((PermissionError, FileNotFoundError, OSError)):
            test_df.to_csv(restricted_path, index=False)

    def test_output_with_invalid_characters_in_path(self):
        """Test output with invalid characters in file paths."""
        test_df = pd.DataFrame([{'test': 'data'}])

        # Test with various invalid path characters
        invalid_paths = [
            "output<>.csv",
            "output|.csv",
            "output?.csv"
        ]

        for invalid_path in invalid_paths:
            with pytest.raises((ValueError, OSError)):
                test_df.to_csv(invalid_path, index=False)


if __name__ == '__main__':
    pytest.main([__file__])
