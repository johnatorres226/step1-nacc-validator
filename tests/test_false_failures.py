"""
False Failure Detection Tests

Loads the most recent QC output and verifies errors correspond to real data issues.
Requires a prior run to have produced output in the output/ directory.

- TestErrorDatasetCompleteness: runs on any default run (errors CSV only)
- TestFalseFailures: requires a detailed run (Data_Fetched/ must be present)
"""

import re
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def latest_errors() -> pd.DataFrame:
    """Load error CSV from the most recent output directory (flat path)."""
    output_dir = Path("output")
    if not output_dir.exists():
        pytest.skip("No output/ directory found — run QC validation first")

    dirs = sorted(
        [d for d in output_dir.iterdir() if d.is_dir()],
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    if not dirs:
        pytest.skip("No output directories found")

    error_csvs = list(dirs[0].glob("Final_Error_Dataset_*.csv"))
    if not error_csvs:
        pytest.skip(f"No error CSV found in {dirs[0]} — run QC validation first")

    df = pd.read_csv(error_csvs[0])
    if "variable_context" not in df.columns or "field_label" not in df.columns:
        pytest.skip("Output predates current schema — re-run QC validation to refresh")
    return df


@pytest.fixture(scope="module")
def latest_source_data() -> pd.DataFrame:
    """Load source data from Data_Fetched/ — only present on detailed runs."""
    output_dir = Path("output")
    if not output_dir.exists():
        pytest.skip("No output/ directory — run QC validation first")

    dirs = sorted(
        [d for d in output_dir.iterdir() if d.is_dir()],
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )
    if not dirs:
        pytest.skip("No output directories found")

    data_dir = dirs[0] / "Data_Fetched"
    if not data_dir.exists():
        pytest.skip("No Data_Fetched/ directory — re-run with 'run -dr' (detailed mode)")

    report_csvs = list(data_dir.glob("Report_Data_*.csv"))
    if not report_csvs:
        pytest.skip(f"No source data CSV found in {data_dir}")

    return pd.read_csv(report_csvs[0])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestErrorDatasetCompleteness:
    """Error CSV has the required schema — runs on any default output."""

    def test_required_columns_present(self, latest_errors):
        required = [
            "ptid",
            "variable",
            "field_label",
            "error_message",
            "current_value",
            "instrument_name",
            "variable_context",
        ]
        missing = [c for c in required if c not in latest_errors.columns]
        assert not missing, f"Error dataset missing columns: {missing}"

    def test_no_nulls_in_critical_columns(self, latest_errors):
        for col in ["ptid", "variable", "error_message"]:
            null_count = latest_errors[col].isna().sum()
            assert null_count == 0, f"Column '{col}' has {null_count} null values"


class TestFalseFailures:
    """Cross-validate errors against source data — requires detailed run output."""

    def _validate_error(self, error_row: pd.Series, data_df: pd.DataFrame) -> str:
        """Return 'valid', 'false_positive', 'complex', or 'data_missing'."""
        ptid = error_row["ptid"]
        variable = error_row["variable"].lower()
        error_msg = error_row["error_message"]
        current_value = error_row["current_value"]

        records = data_df[data_df["ptid"] == ptid]
        if records.empty:
            return "data_missing"

        if "compatibility rule" in error_msg.lower():
            return "complex"

        data_cols = {col.lower(): col for col in data_df.columns}
        actual_col = data_cols.get(variable)
        if actual_col is None:
            return "data_missing"

        actual = (
            str(records.iloc[0][actual_col]) if not pd.isna(records.iloc[0][actual_col]) else ""
        )
        reported = "" if pd.isna(current_value) else str(current_value)

        if "null value not allowed" in error_msg:
            return "valid" if actual == "" else "false_positive"

        if "unallowed value" in error_msg.lower():
            m = re.search(r"unallowed value ([^\]'\"]+)", error_msg)
            if m:
                ev = m.group(1).strip("'\" ")
                try:
                    match = float(actual) == float(ev) if "." in actual else actual == ev
                except (ValueError, TypeError):
                    match = actual == ev
                return "valid" if match else "false_positive"

        if "must be blank" in error_msg.lower():
            return "valid" if actual != "" else "false_positive"

        return "valid" if actual == reported else "false_positive"

    def test_false_positive_rate_under_threshold(self, latest_errors, latest_source_data):
        counts = {"valid": 0, "false_positive": 0, "complex": 0, "data_missing": 0}
        false_positives = []

        for _, row in latest_errors.iterrows():
            status = self._validate_error(row, latest_source_data)
            counts[status] += 1
            if status == "false_positive":
                false_positives.append(
                    f"  PTID {row['ptid']} | {row['variable']} | {row['error_message'][:80]}"
                )

        total = len(latest_errors)
        rate = (counts["false_positive"] / total * 100) if total > 0 else 0
        detail = "\n".join(false_positives[:10])

        assert rate < 5.0, (
            f"False positive rate {rate:.2f}% exceeds 5% threshold "
            f"({counts['false_positive']}/{total}).\n{detail}"
        )

    def test_cross_form_errors_have_both_variables_in_data(self, latest_errors, latest_source_data):
        """Both trigger and target variables exist in source data for compat rule errors."""
        compat_errors = latest_errors[
            latest_errors["error_message"].str.contains("compatibility rule", case=False, na=False)
        ]
        if compat_errors.empty:
            pytest.skip("No compatibility rule errors in output")

        sample = compat_errors.sample(n=min(20, len(compat_errors)), random_state=42)
        data_cols = {c.lower() for c in latest_source_data.columns}
        missing = []

        for _, row in sample.iterrows():
            msg = row["error_message"]
            trigger = re.search(r"for if \{'([^']+)':", msg)
            target = re.search(r"^\('([^']+)',", msg)
            if trigger and target:
                for var in (trigger.group(1).lower(), target.group(1).lower()):
                    if var not in data_cols:
                        missing.append(f"PTID {row['ptid']}: variable '{var}' not in data")

        assert not missing, "Cross-form variables missing from data:\n" + "\n".join(missing)
