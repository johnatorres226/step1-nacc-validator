"""
Tests for the analytics module - DataQualityAnalyzer and related functionality.
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch

from src.pipeline.analytics import (
    DataQualityAnalyzer,
    CoverageReport,
    QualitySummary,
    create_simplified_debug_info
)


class TestCoverageReport:
    """Test CoverageReport dataclass."""
    
    def test_coverage_report_creation(self):
        """Test creating a coverage report."""
        report = CoverageReport(
            instrument_name="a1",
            total_rule_variables=10,
            matched_variables=8,
            missing_variables=["var1", "var2"],
            coverage_percentage=80.0
        )
        
        assert report.instrument_name == "a1"
        assert report.total_rule_variables == 10
        assert report.matched_variables == 8
        assert len(report.missing_variables) == 2
        assert report.coverage_percentage == 80.0
        assert not report.is_complete
    
    def test_coverage_report_is_complete(self):
        """Test is_complete property."""
        complete_report = CoverageReport(
            instrument_name="a1",
            total_rule_variables=10,
            matched_variables=10,
            missing_variables=[],
            coverage_percentage=100.0
        )
        
        assert complete_report.is_complete


class TestDataQualityAnalyzer:
    """Test DataQualityAnalyzer functionality."""
    
    @pytest.fixture
    def sample_data(self):
        """Sample DataFrame for testing."""
        return pd.DataFrame({
            'ptid': ['001', '002', '003'],
            'redcap_event_name': ['v1', 'v1', 'v2'],
            'a1_var1': [1, 2, 3],
            'a1_var2': ['A', 'B', 'C'],
            'b1_var1': [10, 20, 30],
            'orphaned_col': ['x', 'y', 'z']
        })
    
    @pytest.fixture
    def sample_rules_cache(self):
        """Sample rules cache for testing."""
        return {
            'a1': {
                'a1_var1': {'type': 'integer'},
                'a1_var2': {'type': 'string'},
                'a1_missing': {'type': 'string'}  # This variable is missing from data
            },
            'b1': {
                'b1_var1': {'type': 'integer'}
            }
        }
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization with different verbosity levels."""
        analyzer = DataQualityAnalyzer()
        assert analyzer.verbosity_level == "summary"
        
        analyzer_detailed = DataQualityAnalyzer(verbosity_level="detailed")
        assert analyzer_detailed.verbosity_level == "detailed"
    
    @patch('src.pipeline.analytics.is_dynamic_rule_instrument')
    def test_analyze_coverage(self, mock_is_dynamic, sample_data, sample_rules_cache):
        """Test coverage analysis for instruments."""
        mock_is_dynamic.return_value = False
        
        analyzer = DataQualityAnalyzer()
        reports = analyzer.analyze_coverage(sample_data, ['a1', 'b1'], sample_rules_cache)
        
        assert len(reports) == 2
        
        # Check a1 report
        a1_report = reports[0]
        assert a1_report.instrument_name == 'a1'
        assert a1_report.total_rule_variables == 3
        assert a1_report.matched_variables == 2  # a1_var1, a1_var2 present
        assert 'a1_missing' in a1_report.missing_variables
        assert a1_report.coverage_percentage == pytest.approx(66.67, rel=1e-2)
        
        # Check b1 report
        b1_report = reports[1]
        assert b1_report.instrument_name == 'b1'
        assert b1_report.total_rule_variables == 1
        assert b1_report.matched_variables == 1
        assert b1_report.coverage_percentage == 100.0
        assert b1_report.is_complete
    
    @patch('src.pipeline.analytics.get_core_columns')
    @patch('src.pipeline.analytics.get_completion_columns')
    @patch('src.pipeline.analytics.get_special_columns')
    @patch('src.pipeline.analytics.is_dynamic_rule_instrument')
    def test_find_orphaned_columns(self, mock_is_dynamic, mock_special, mock_completion, 
                                  mock_core, sample_data, sample_rules_cache):
        """Test finding orphaned columns."""
        mock_is_dynamic.return_value = False
        mock_core.return_value = ['ptid']
        mock_completion.return_value = ['redcap_event_name']
        mock_special.return_value = []
        
        analyzer = DataQualityAnalyzer()
        # First run coverage analysis
        analyzer.analyze_coverage(sample_data, ['a1', 'b1'], sample_rules_cache)
        
        # Then find orphaned columns
        orphaned = analyzer.find_orphaned_columns(sample_data, sample_rules_cache)
        
        assert 'orphaned_col' in orphaned
        assert 'ptid' not in orphaned  # Core column
        assert 'redcap_event_name' not in orphaned  # Completion column
        assert 'a1_var1' not in orphaned  # Rule variable
    
    @patch('src.pipeline.analytics.is_dynamic_rule_instrument')
    def test_generate_summary(self, mock_is_dynamic, sample_data, sample_rules_cache):
        """Test generating quality summary."""
        mock_is_dynamic.return_value = False
        
        analyzer = DataQualityAnalyzer()
        analyzer.analyze_coverage(sample_data, ['a1', 'b1'], sample_rules_cache)
        
        summary = analyzer.generate_summary(sample_data)
        
        assert summary.total_instruments == 2
        assert summary.total_data_columns == 6
        assert summary.total_rule_variables == 4  # 3 for a1, 1 for b1
        assert summary.matched_variables == 3  # 2 for a1, 1 for b1
        assert summary.complete_instruments == 1  # Only b1 is complete
        assert summary.overall_coverage_percentage == 75.0  # 3/4 * 100
    
    @patch('src.pipeline.analytics.is_dynamic_rule_instrument')
    def test_get_detailed_report_summary(self, mock_is_dynamic, sample_data, sample_rules_cache):
        """Test getting detailed report with summary verbosity."""
        mock_is_dynamic.return_value = False
        
        analyzer = DataQualityAnalyzer(verbosity_level="summary")
        analyzer.analyze_coverage(sample_data, ['a1', 'b1'], sample_rules_cache)
        
        report = analyzer.get_detailed_report(sample_data)
        
        assert 'summary' in report
        assert report['summary']['total_instruments'] == 2
        assert report['summary']['overall_coverage'] == "75.0%"
        assert report['summary']['complete_instruments'] == 1
    
    @patch('src.pipeline.analytics.is_dynamic_rule_instrument')
    def test_get_detailed_report_detailed(self, mock_is_dynamic, sample_data, sample_rules_cache):
        """Test getting detailed report with detailed verbosity."""
        mock_is_dynamic.return_value = False
        
        analyzer = DataQualityAnalyzer(verbosity_level="detailed")
        analyzer.analyze_coverage(sample_data, ['a1', 'b1'], sample_rules_cache)
        
        report = analyzer.get_detailed_report(sample_data)
        
        assert 'summary' in report
        assert 'coverage_by_instrument' in report
        assert 'issues' in report
        
        coverage_data = report['coverage_by_instrument']
        assert len(coverage_data) == 2
        assert coverage_data[0]['instrument'] == 'a1'
        assert coverage_data[0]['coverage'] == "66.7%"
    
    @patch('src.pipeline.analytics.is_dynamic_rule_instrument')
    def test_get_detailed_report_full(self, mock_is_dynamic, sample_data, sample_rules_cache):
        """Test getting detailed report with full verbosity."""
        mock_is_dynamic.return_value = False
        
        analyzer = DataQualityAnalyzer(verbosity_level="full")
        analyzer.analyze_coverage(sample_data, ['a1', 'b1'], sample_rules_cache)
        
        report = analyzer.get_detailed_report(sample_data)
        
        assert 'summary' in report
        assert 'coverage_reports' in report
        assert 'orphaned_columns' in report
        assert 'detailed_analysis' in report
        assert 'instruments_by_coverage' in report['detailed_analysis']
        assert 'most_common_missing_variables' in report['detailed_analysis']
    
    @patch('src.pipeline.analytics.is_dynamic_rule_instrument')
    def test_group_instruments_by_coverage(self, mock_is_dynamic, sample_data, sample_rules_cache):
        """Test grouping instruments by coverage ranges."""
        mock_is_dynamic.return_value = False
        
        analyzer = DataQualityAnalyzer()
        analyzer.analyze_coverage(sample_data, ['a1', 'b1'], sample_rules_cache)
        
        groups = analyzer._group_instruments_by_coverage()
        
        assert 'complete' in groups
        assert 'high' in groups
        assert 'medium' in groups
        assert 'low' in groups
        
        assert 'b1' in groups['complete']  # 100% coverage
        assert 'a1' in groups['low']       # 66.7% coverage (< 70%)
    
    @patch('src.pipeline.analytics.is_dynamic_rule_instrument')
    def test_get_common_missing_variables(self, mock_is_dynamic, sample_data, sample_rules_cache):
        """Test getting most common missing variables."""
        mock_is_dynamic.return_value = False
        
        analyzer = DataQualityAnalyzer()
        analyzer.analyze_coverage(sample_data, ['a1', 'b1'], sample_rules_cache)
        
        common_missing = analyzer._get_common_missing_variables()
        
        assert len(common_missing) >= 1
        assert common_missing[0][0] == 'a1_missing'  # Most common missing variable
        assert common_missing[0][1] == 1  # Appears in 1 instrument


class TestCreateSimplifiedDebugInfo:
    """Test the simplified debug info function."""
    
    @pytest.fixture
    def sample_data(self):
        """Sample DataFrame for testing."""
        return pd.DataFrame({
            'ptid': ['001', '002'],
            'a1_var1': [1, 2],
            'a1_var2': ['A', 'B']
        })
    
    @pytest.fixture
    def sample_rules_cache(self):
        """Sample rules cache for testing."""
        return {
            'a1': {
                'a1_var1': {'type': 'integer'},
                'a1_var2': {'type': 'string'}
            }
        }
    
    @patch('src.pipeline.analytics.is_dynamic_rule_instrument')
    @patch('src.pipeline.analytics.get_core_columns')
    @patch('src.pipeline.analytics.get_completion_columns')
    @patch('src.pipeline.analytics.get_special_columns')
    def test_create_simplified_debug_info_summary(self, mock_special, mock_completion, 
                                                 mock_core, mock_is_dynamic, 
                                                 sample_data, sample_rules_cache):
        """Test creating simplified debug info with summary verbosity."""
        mock_is_dynamic.return_value = False
        mock_core.return_value = ['ptid']
        mock_completion.return_value = []
        mock_special.return_value = []
        
        result = create_simplified_debug_info(
            sample_data, ['a1'], sample_rules_cache, "summary"
        )
        
        assert 'summary' in result
        assert result['summary']['total_instruments'] == 1
        assert result['summary']['overall_coverage'] == "100.0%"
    
    @patch('src.pipeline.analytics.is_dynamic_rule_instrument')
    @patch('src.pipeline.analytics.get_core_columns')
    @patch('src.pipeline.analytics.get_completion_columns')
    @patch('src.pipeline.analytics.get_special_columns')
    def test_create_simplified_debug_info_detailed(self, mock_special, mock_completion, 
                                                  mock_core, mock_is_dynamic, 
                                                  sample_data, sample_rules_cache):
        """Test creating simplified debug info with detailed verbosity."""
        mock_is_dynamic.return_value = False
        mock_core.return_value = ['ptid']
        mock_completion.return_value = []
        mock_special.return_value = []
        
        result = create_simplified_debug_info(
            sample_data, ['a1'], sample_rules_cache, "detailed"
        )
        
        assert 'summary' in result
        assert 'coverage_by_instrument' in result
        assert 'issues' in result
        
        assert len(result['coverage_by_instrument']) == 1
        assert result['coverage_by_instrument'][0]['instrument'] == 'a1'
