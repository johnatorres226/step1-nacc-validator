"""
Data Quality Analytics Module

Provides simplified and configurable data quality analysis tools to replace
complex debug functionality with structured, maintainable analytics.
"""

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.pipeline.config_manager import (
    get_completion_columns,
    get_core_columns,
    get_special_columns,
    is_dynamic_rule_instrument,
)
from src.pipeline.processors.instrument_processors import DynamicInstrumentProcessor


logger = logging.getLogger(__name__)


@dataclass
class CoverageReport:
    """Report of data coverage analysis."""
    instrument_name: str
    total_rule_variables: int
    matched_variables: int
    missing_variables: list[str]
    coverage_percentage: float

    @property
    def is_complete(self) -> bool:
        """True if all rule variables are present in data."""
        return self.coverage_percentage == 100.0


@dataclass
class QualitySummary:
    """High-level summary of data quality analysis."""
    total_instruments: int
    total_data_columns: int
    total_rule_variables: int
    matched_variables: int
    orphaned_columns_count: int
    overall_coverage_percentage: float
    complete_instruments: int


class DataQualityAnalyzer:
    """
    Simplified data quality analyzer with configurable verbosity levels.

    Replaces the complex debug_variable_mapping function with a cleaner,
    more maintainable approach to data quality analysis.
    """

    def __init__(self, verbosity_level: str = "summary"):
        """
        Initialize analyzer.

        Args:
            verbosity_level: One of "summary", "detailed", "full"
        """
        self.verbosity_level = verbosity_level
        self._coverage_reports: list[CoverageReport] = []
        self._orphaned_columns: list[str] = []

    def analyze_coverage(
        self,
        data_df: pd.DataFrame,
        instrument_list: list[str],
        rules_cache: dict[str, dict[str, Any]]
    ) -> list[CoverageReport]:
        """
        Analyze data coverage for given instruments.

        Args:
            data_df: DataFrame to analyze
            instrument_list: List of instruments to check
            rules_cache: Cache of loaded JSON rules

        Returns:
            List of coverage reports for each instrument
        """
        coverage_reports = []

        for instrument in instrument_list:
            rules = rules_cache.get(instrument, {})

            if is_dynamic_rule_instrument(instrument):
                processor = DynamicInstrumentProcessor(instrument)
                rule_vars = set(processor.get_all_variables())
            else:
                rule_vars = set(rules.keys())

            # Calculate coverage
            data_vars = [var for var in rule_vars if var in data_df.columns]
            missing_vars = [
                var for var in rule_vars if var not in data_df.columns]
            coverage_pct = len(data_vars) / len(rule_vars) * \
                100 if rule_vars else 100.0

            report = CoverageReport(
                instrument_name=instrument,
                total_rule_variables=len(rule_vars),
                matched_variables=len(data_vars),
                missing_variables=missing_vars,
                coverage_percentage=coverage_pct
            )
            coverage_reports.append(report)

        self._coverage_reports = coverage_reports
        return coverage_reports

    def find_orphaned_columns(
        self,
        data_df: pd.DataFrame,
        rules_cache: dict[str, dict[str, Any]]
    ) -> list[str]:
        """
        Find columns present in data but not defined in any rules.

        Args:
            data_df: DataFrame to analyze
            rules_cache: Cache of loaded JSON rules for calculating all rule variables

        Returns:
            List of orphaned column names
        """
        # Get all rule variables from coverage reports and rules cache
        all_rule_variables = set()

        # From coverage analysis
        for report in self._coverage_reports:
            # Get variables for this instrument
            instrument = report.instrument_name
            rules = rules_cache.get(instrument, {})

            if is_dynamic_rule_instrument(instrument):
                processor = DynamicInstrumentProcessor(instrument)
                rule_vars = set(processor.get_all_variables())
            else:
                rule_vars = set(rules.keys())

            all_rule_variables.update(rule_vars)

        data_cols = set(data_df.columns)
        core_cols = set(get_core_columns())
        completion_cols = set(get_completion_columns())
        special_cols = set(get_special_columns())

        expected_cols = all_rule_variables | core_cols | completion_cols | special_cols
        orphaned = list(data_cols - expected_cols)

        self._orphaned_columns = orphaned
        return orphaned

    def generate_summary(
            self, data_df: pd.DataFrame | None = None) -> QualitySummary:
        """
        Generate high-level summary of data quality.

        Args:
            data_df: Optional DataFrame to get column count

        Returns:
            Quality summary object
        """
        if not self._coverage_reports:
            logger.warning("No coverage analysis performed yet")
            return QualitySummary(0, 0, 0, 0, 0, 0.0, 0)

        total_instruments = len(self._coverage_reports)
        total_rule_variables = sum(
            r.total_rule_variables for r in self._coverage_reports)
        matched_variables = sum(
            r.matched_variables for r in self._coverage_reports)
        complete_instruments = sum(
            1 for r in self._coverage_reports if r.is_complete)
        total_data_columns = len(data_df.columns) if data_df is not None else 0

        overall_coverage = (matched_variables / total_rule_variables * 100
                            if total_rule_variables > 0 else 100.0)

        return QualitySummary(
            total_instruments=total_instruments,
            total_data_columns=total_data_columns,
            total_rule_variables=total_rule_variables,
            matched_variables=matched_variables,
            orphaned_columns_count=len(self._orphaned_columns),
            overall_coverage_percentage=overall_coverage,
            complete_instruments=complete_instruments
        )

    def get_detailed_report(
            self, data_df: pd.DataFrame | None = None) -> dict[str, Any]:
        """
        Get detailed report based on verbosity level.

        Args:
            data_df: Optional DataFrame for additional statistics

        Returns:
            Detailed analysis report
        """
        summary = self.generate_summary(data_df)

        if self.verbosity_level == "summary":
            return {
                "summary": {
                    "total_instruments": summary.total_instruments,
                    "overall_coverage": f"{
                        summary.overall_coverage_percentage:.1f}%",
                    "complete_instruments": summary.complete_instruments,
                    "orphaned_columns_count": summary.orphaned_columns_count}}

        if self.verbosity_level == "detailed":
            return {
                "summary": summary.__dict__,
                "coverage_by_instrument": [
                    {
                        "instrument": r.instrument_name,
                        "coverage": f"{r.coverage_percentage:.1f}%",
                        "missing_count": len(r.missing_variables)
                    }
                    for r in self._coverage_reports
                ],
                "issues": {
                    "incomplete_instruments": [
                        r.instrument_name for r in self._coverage_reports
                        if not r.is_complete
                    ],
                    "orphaned_columns_count": len(self._orphaned_columns)
                }
            }

        # "full"
        return {
            "summary": summary.__dict__,
            "coverage_reports": [
                r.__dict__ for r in self._coverage_reports],
            "orphaned_columns": self._orphaned_columns,
            "detailed_analysis": {
                "instruments_by_coverage": self._group_instruments_by_coverage(),
                "most_common_missing_variables": self._get_common_missing_variables()}}

    def _group_instruments_by_coverage(self) -> dict[str, list[str]]:
        """Group instruments by coverage ranges."""
        groups = {
            "complete": [],      # 100%
            "high": [],          # 90-99%
            "medium": [],        # 70-89%
            "low": []           # <70%
        }

        for report in self._coverage_reports:
            if report.coverage_percentage == 100:
                groups["complete"].append(report.instrument_name)
            elif report.coverage_percentage >= 90:
                groups["high"].append(report.instrument_name)
            elif report.coverage_percentage >= 70:
                groups["medium"].append(report.instrument_name)
            else:
                groups["low"].append(report.instrument_name)

        return groups

    def _get_common_missing_variables(self) -> list[tuple[str, int]]:
        """Get most commonly missing variables across instruments."""
        missing_counts = {}

        for report in self._coverage_reports:
            for var in report.missing_variables:
                missing_counts[var] = missing_counts.get(var, 0) + 1

        # Return top 10 most common missing variables
        return sorted(
            missing_counts.items(),
            key=lambda x: x[1],
            reverse=True)[
            :10]


def create_simplified_debug_info(
    data_df: pd.DataFrame,
    instrument_list: list[str],
    rules_cache: dict[str, dict[str, Any]],
    verbosity: str = "summary"
) -> dict[str, Any]:
    """
    Simplified replacement for debug_variable_mapping.

    Args:
        data_df: DataFrame to analyze
        instrument_list: List of instruments to check
        rules_cache: Cache of loaded JSON rules
        verbosity: Verbosity level ("summary", "detailed", "full")

    Returns:
        Simplified debug information
    """
    analyzer = DataQualityAnalyzer(verbosity_level=verbosity)

    # Perform analysis
    analyzer.analyze_coverage(data_df, instrument_list, rules_cache)
    analyzer.find_orphaned_columns(data_df, rules_cache)

    return analyzer.get_detailed_report(data_df)
