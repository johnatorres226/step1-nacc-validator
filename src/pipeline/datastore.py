"""
Defines abstract base classes for data storage and retrieval.

This module provides a blueprint for how the pipeline interacts with data sources,
ensuring a consistent interface for fetching records and validating external
data, such as drug IDs (RxCUI) and ADC IDs. It also includes enhanced functionality
for tracking validation runs and error trends.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Enhanced datastore structures
@dataclass
class ValidationRun:
    """Represents a validation run with metadata."""
    run_id: str
    timestamp: str
    instrument: str
    total_records: int
    error_count: int
    passed_count: int
    run_config: Dict[str, Any]


@dataclass
class ErrorRecord:
    """Represents an individual error record."""
    run_id: str
    ptid: str
    redcap_event_name: str
    instrument_name: str
    variable: str
    current_value: str
    expected_value: str
    error: str
    error_type: str = "validation"


@dataclass
class ErrorComparison:
    """Represents comparison between current and previous errors."""
    ptid: str
    redcap_event_name: str
    instrument_name: str
    variable: str
    status: str  # 'new', 'resolved', 'persistent'
    current_error: Optional[str] = None
    previous_error: Optional[str] = None

# pylint: disable=too-few-public-methods, no-self-use, unused-argument

class Datastore(ABC):
    """Abstract base class for a datastore providing historical data.

    This class defines the interface for accessing previously stored records,
    which is essential for longitudinal validation checks (e.g., comparing
    a value against a previous visit's value). It also includes methods for
    validating external identifiers.

    Attributes:
        pk_field (str): The name of the primary key field used to identify
                        a unique participant or subject.
        orderby (str): The field name used to sort records chronologically,
                       typically a visit date.
    """

    def __init__(self, pk_field: str, orderby: str):
        """Initializes the Datastore.

        Args:
            pk_field: The primary key field to uniquely identify a participant.
            orderby: The field to sort records by, defining their order.
        """
        self.pk_field: str = pk_field
        self.orderby: str = orderby

    @abstractmethod
    def get_previous_record(
        self,
        pk_val: Any,
        current_record: Dict[str, Any],
        ignore_empty_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves the immediately preceding record for a given participant.

        Implementations should query the underlying data source to find the
        record for the participant identified by `pk_val` that comes just
        before the `current_record` based on the `orderby` field.

        Args:
            pk_val: The primary key value of the subject.
            current_record: The record currently being validated. This can be
                            used to establish a reference point in time.
            ignore_empty_fields: A list of fields that can be ignored if they
                                 are empty when searching for a previous record.

        Returns:
            A dictionary representing the previous record, or None if no
            previous record is found.
        """
        return None

    @abstractmethod
    def get_previous_nonempty_record(
        self,
        current_record: Dict[str, Any],
        fields: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the most recent previous record where specified fields are not empty.

        This method is useful for finding the last known value for a specific
        set of fields, skipping any intermediate records where these fields
        might have been left blank.

        Args:
            current_record: The record currently being validated.
            fields: A list of field names to check for non-empty values.

        Returns:
            A dictionary representing the previous record that has non-empty
            values for the specified fields, or None if no such record exists.
        """
        return None

    @abstractmethod
    def is_valid_rxcui(self, drug_id: int) -> bool:
        """
        Checks if a given drug ID is a valid RxCUI.

        Implementations should connect to an external service or database
        (e.g., RxNorm API) to validate the identifier. See:
        - https://www.nlm.nih.gov/research/umls/rxnorm/overview.html
        - https://mor.nlm.nih.gov/RxNav/

        Args:
            drug_id: The drug ID to validate.

        Returns:
            True if the drug ID is a valid RxCUI, False otherwise.
        """
        return False

    @abstractmethod
    def is_valid_adcid(self, adcid: int) -> bool:
        """
        Checks if a given ADC ID is valid.

        Implementations should validate the ADC ID against a known list or
        an external service.

        Args:
            adcid: The ADC ID to validate.

        Returns:
            True if the ADC ID is valid, False otherwise.
        """
        return False


class PandasDatastore(Datastore):
    """A concrete implementation of the Datastore using a pandas DataFrame."""

    def __init__(self, pk_field: str, orderby: str, all_records_df: pd.DataFrame):
        """
        Initializes the PandasDatastore.

        Args:
            pk_field: The primary key field.
            orderby: The field to sort records by.
            all_records_df: The DataFrame containing all records.
        """
        super().__init__(pk_field, orderby)
        self.all_records = all_records_df.sort_values(by=orderby)

    def get_previous_record(
        self,
        pk_val: Any,
        current_record: Dict[str, Any],
        ignore_empty_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves the previous record from the DataFrame."""
        subject_records = self.all_records[self.all_records[self.pk_field] == pk_val]
        current_record_orderby_val = current_record.get(self.orderby)

        if subject_records.empty or current_record_orderby_val is None:
            return None

        # Filter for records that occurred before the current one
        previous_records = subject_records[
            subject_records[self.orderby] < current_record_orderby_val
        ]

        if previous_records.empty:
            return None

        # The last record in this filtered set is the one we want
        return previous_records.iloc[-1].to_dict()

    def is_valid_rxcui(self, drug_id: int) -> bool:
        """Placeholder for RxCUI validation. Not implemented."""
        # In a real scenario, this would query an external API or database.
        return True  # Assume valid for now

    def is_valid_adcid(self, adcid: int) -> bool:
        """Placeholder for ADC ID validation. Not implemented."""
        return True  # Assume valid for now


class EnhancedDatastore(Datastore):
    """
    Enhanced datastore with error tracking and trend analysis capabilities.
    
    This class extends the basic datastore interface to provide:
    - Validation run tracking
    - Error comparison between runs
    - Trend analysis over time
    - Pattern detection for recurring issues
    - Data quality monitoring
    
    Only supports complete_event mode runs.
    """
    
    def __init__(self, db_path: str, pk_field: str = "ptid", orderby: str = "timestamp"):
        """
        Initialize the enhanced datastore.
        
        Args:
            db_path: Path to the SQLite database file
            pk_field: Primary key field name
            orderby: Field to order records by
        """
        super().__init__(pk_field, orderby)
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        
    def _init_database(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        
        # Create validation_runs table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS validation_runs (
                run_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                instrument TEXT NOT NULL,
                total_records INTEGER NOT NULL,
                error_count INTEGER NOT NULL,
                passed_count INTEGER NOT NULL,
                run_config TEXT NOT NULL
            )
        ''')
        
        # Create error_records table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS error_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                ptid TEXT NOT NULL,
                redcap_event_name TEXT NOT NULL,
                instrument_name TEXT NOT NULL,
                variable TEXT NOT NULL,
                current_value TEXT,
                expected_value TEXT,
                error TEXT NOT NULL,
                error_type TEXT DEFAULT 'validation',
                FOREIGN KEY (run_id) REFERENCES validation_runs (run_id)
            )
        ''')
        
        # Create error_trends table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS error_trends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument TEXT NOT NULL,
                date TEXT NOT NULL,
                error_rate REAL NOT NULL,
                error_count INTEGER NOT NULL,
                total_records INTEGER NOT NULL,
                UNIQUE(instrument, date)
            )
        ''')
        
        # Create indexes for performance
        conn.execute('CREATE INDEX IF NOT EXISTS idx_error_records_run_id ON error_records(run_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_error_records_ptid ON error_records(ptid)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_error_records_variable ON error_records(variable)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_validation_runs_instrument ON validation_runs(instrument)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_validation_runs_timestamp ON validation_runs(timestamp)')
        
        conn.commit()
        conn.close()
        
    def store_validation_run(self, instrument: str, errors_df: pd.DataFrame, 
                           total_records: int, run_config: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Store a validation run and its errors.
        
        Args:
            instrument: Name of the instrument
            errors_df: DataFrame containing error records
            total_records: Total number of records processed
            run_config: Configuration used for this run
            
        Returns:
            The run_id of the stored run
        """
        # Only allow complete_event mode
        if run_config and run_config.get('mode') != 'complete_events':
            logger.warning(f"Datastore limited to complete_events mode, got: {run_config.get('mode')}")
            return None
            
        # Generate unique run ID
        run_id = f"{instrument}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Create validation run record
        validation_run = ValidationRun(
            run_id=run_id,
            timestamp=datetime.now().isoformat(),
            instrument=instrument,
            total_records=total_records,
            error_count=len(errors_df),
            passed_count=total_records - len(errors_df),
            run_config=run_config or {}
        )
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Store validation run
            conn.execute('''
                INSERT INTO validation_runs
                (run_id, timestamp, instrument, total_records, error_count, passed_count, run_config)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                validation_run.run_id,
                validation_run.timestamp,
                validation_run.instrument,
                validation_run.total_records,
                validation_run.error_count,
                validation_run.passed_count,
                json.dumps(validation_run.run_config)
            ))
            
            # Store error records
            for _, error_row in errors_df.iterrows():
                error_record = ErrorRecord(
                    run_id=run_id,
                    ptid=error_row.get('ptid', ''),
                    redcap_event_name=error_row.get('redcap_event_name', ''),
                    instrument_name=error_row.get('instrument_name', instrument),
                    variable=error_row.get('variable', ''),
                    current_value=str(error_row.get('current_value', '')),
                    expected_value=str(error_row.get('expected_value', '')),
                    error=error_row.get('error', ''),
                    error_type=error_row.get('error_type', 'validation')
                )
                
                conn.execute('''
                    INSERT INTO error_records
                    (run_id, ptid, redcap_event_name, instrument_name, variable, 
                     current_value, expected_value, error, error_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    error_record.run_id,
                    error_record.ptid,
                    error_record.redcap_event_name,
                    error_record.instrument_name,
                    error_record.variable,
                    error_record.current_value,
                    error_record.expected_value,
                    error_record.error,
                    error_record.error_type
                ))
            
            conn.commit()
            logger.info(f"Stored validation run {run_id} with {len(errors_df)} errors")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing validation run: {e}")
            raise
        finally:
            conn.close()
            
        return run_id
        
    def compare_with_previous_run(self, current_errors_df: pd.DataFrame, 
                                instrument: str) -> List[ErrorComparison]:
        """
        Compare current errors with the previous run for the same instrument.
        
        Args:
            current_errors_df: DataFrame with current errors
            instrument: Name of the instrument
            
        Returns:
            List of ErrorComparison objects
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get the previous run
        cursor = conn.execute('''
            SELECT run_id FROM validation_runs
            WHERE instrument = ?
            ORDER BY timestamp DESC
            LIMIT 2
        ''', (instrument,))
        
        runs = cursor.fetchall()
        
        if len(runs) < 2:
            # No previous run to compare with
            comparisons = []
            for _, error_row in current_errors_df.iterrows():
                comparisons.append(ErrorComparison(
                    ptid=error_row.get('ptid', ''),
                    redcap_event_name=error_row.get('redcap_event_name', ''),
                    instrument_name=error_row.get('instrument_name', instrument),
                    variable=error_row.get('variable', ''),
                    status='new',
                    current_error=error_row.get('error', ''),
                    previous_error=None
                ))
            conn.close()
            return comparisons
            
        previous_run_id = runs[1][0]
        
        # Get previous errors
        previous_errors_df = pd.read_sql_query('''
            SELECT ptid, redcap_event_name, variable, error
            FROM error_records
            WHERE run_id = ?
        ''', conn, params=(previous_run_id,))
        
        conn.close()
        
        # Create comparison
        comparisons = []
        
        # Create lookup sets for efficient comparison
        current_errors_set = set()
        current_errors_lookup = {}
        
        for _, error_row in current_errors_df.iterrows():
            key = (error_row.get('ptid', ''), error_row.get('redcap_event_name', ''), 
                   error_row.get('variable', ''))
            current_errors_set.add(key)
            current_errors_lookup[key] = error_row.get('error', '')
            
        previous_errors_set = set()
        previous_errors_lookup = {}
        
        for _, error_row in previous_errors_df.iterrows():
            key = (error_row.get('ptid', ''), error_row.get('redcap_event_name', ''), 
                   error_row.get('variable', ''))
            previous_errors_set.add(key)
            previous_errors_lookup[key] = error_row.get('error', '')
        
        # Find new errors
        for key in current_errors_set:
            if key not in previous_errors_set:
                comparisons.append(ErrorComparison(
                    ptid=key[0],
                    redcap_event_name=key[1],
                    instrument_name=instrument,
                    variable=key[2],
                    status='new',
                    current_error=current_errors_lookup[key],
                    previous_error=None
                ))
        
        # Find resolved errors
        for key in previous_errors_set:
            if key not in current_errors_set:
                comparisons.append(ErrorComparison(
                    ptid=key[0],
                    redcap_event_name=key[1],
                    instrument_name=instrument,
                    variable=key[2],
                    status='resolved',
                    current_error=None,
                    previous_error=previous_errors_lookup[key]
                ))
        
        # Find persistent errors
        for key in current_errors_set.intersection(previous_errors_set):
            comparisons.append(ErrorComparison(
                ptid=key[0],
                redcap_event_name=key[1],
                instrument_name=instrument,
                variable=key[2],
                status='persistent',
                current_error=current_errors_lookup[key],
                previous_error=previous_errors_lookup[key]
            ))
            
        return comparisons
    
    def get_trend_analysis(self, instrument: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Get trend analysis for an instrument over the specified time period.
        
        Args:
            instrument: Name of the instrument
            days_back: Number of days to look back
            
        Returns:
            Dictionary with trend analysis data
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get runs in the specified period
        from datetime import timedelta
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date - timedelta(days=days_back)
        
        cursor = conn.execute('''
            SELECT run_id, timestamp, total_records, error_count, passed_count
            FROM validation_runs
            WHERE instrument = ? AND timestamp >= ?
            ORDER BY timestamp
        ''', (instrument, cutoff_date.isoformat()))
        
        runs = cursor.fetchall()
        conn.close()
        
        if not runs:
            return {
                'instrument': instrument,
                'period_days': days_back,
                'total_runs': 0,
                'trend_direction': 'no_data',
                'current_error_rate': 0.0,
                'average_error_rate': 0.0,
                'error_rates': []
            }
        
        # Calculate error rates
        error_rates = []
        for run in runs:
            run_id, timestamp, total_records, error_count, passed_count = run
            error_rate = (error_count / total_records * 100) if total_records > 0 else 0
            error_rates.append({
                'run_id': run_id,
                'timestamp': timestamp,
                'error_rate': error_rate,
                'error_count': error_count,
                'total_records': total_records
            })
        
        # Determine trend direction
        if len(error_rates) >= 2:
            recent_avg = sum(r['error_rate'] for r in error_rates[-3:]) / min(3, len(error_rates))
            earlier_avg = sum(r['error_rate'] for r in error_rates[:-3]) / max(1, len(error_rates) - 3)
            
            if recent_avg > earlier_avg * 1.1:
                trend_direction = 'increasing'
            elif recent_avg < earlier_avg * 0.9:
                trend_direction = 'decreasing'
            else:
                trend_direction = 'stable'
        else:
            trend_direction = 'insufficient_data'
        
        return {
            'instrument': instrument,
            'period_days': days_back,
            'total_runs': len(runs),
            'trend_direction': trend_direction,
            'current_error_rate': error_rates[-1]['error_rate'] if error_rates else 0.0,
            'average_error_rate': sum(r['error_rate'] for r in error_rates) / len(error_rates),
            'error_rates': error_rates
        }
        
    def detect_error_patterns(self, instrument: str, days_back: int = 30) -> Dict[str, Any]:
        """
        Detect recurring error patterns for an instrument.
        
        Args:
            instrument: Name of the instrument
            days_back: Number of days to analyze
            
        Returns:
            Dictionary with pattern detection results
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Get all errors in the period
        errors_df = pd.read_sql_query('''
            SELECT er.ptid, er.variable, er.error, er.error_type, vr.timestamp
            FROM error_records er
            JOIN validation_runs vr ON er.run_id = vr.run_id
            WHERE vr.instrument = ? AND vr.timestamp >= ?
            ORDER BY vr.timestamp
        ''', conn, params=(instrument, cutoff_date.isoformat()))
        
        conn.close()
        
        if errors_df.empty:
            return {
                'instrument': instrument,
                'period_days': days_back,
                'repeated_patterns': 0,
                'error_clusters': 0,
                'systematic_issues': 0,
                'top_patterns': [],
                'systematic_issues_detail': []
            }
        
        # Find repeated patterns (same ptid + variable combination)
        pattern_counts = errors_df.groupby(['ptid', 'variable']).size().reset_index(name='count')
        repeated_patterns = len(pattern_counts[pattern_counts['count'] > 1])
        
        # Find error clusters (same variable, multiple participants)
        variable_counts = errors_df.groupby('variable').size().reset_index(name='count')
        error_clusters = len(variable_counts[variable_counts['count'] >= 3])
        
        # Find systematic issues (same error type + variable across multiple records)
        systematic_df = errors_df.groupby(['variable', 'error_type']).size().reset_index(name='count')
        systematic_issues = len(systematic_df[systematic_df['count'] >= 5])
        
        # Get top patterns
        top_patterns = pattern_counts.nlargest(10, 'count').to_dict('records')
        
        # Get systematic issues detail
        systematic_issues_detail = systematic_df[systematic_df['count'] >= 5].nlargest(10, 'count').to_dict('records')
        
        return {
            'instrument': instrument,
            'period_days': days_back,
            'repeated_patterns': repeated_patterns,
            'error_clusters': error_clusters,
            'systematic_issues': systematic_issues,
            'top_patterns': top_patterns,
            'systematic_issues_detail': systematic_issues_detail
        }
        
    def generate_quality_dashboard(self, instrument: str) -> Dict[str, Any]:
        """
        Generate a data quality dashboard for an instrument.
        
        Args:
            instrument: Name of the instrument
            
        Returns:
            Dictionary with dashboard data
        """
        trend_analysis = self.get_trend_analysis(instrument)
        pattern_analysis = self.detect_error_patterns(instrument)
        
        conn = sqlite3.connect(self.db_path)
        
        # Get total historical runs
        cursor = conn.execute('''
            SELECT COUNT(*) FROM validation_runs WHERE instrument = ?
        ''', (instrument,))
        total_runs = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'instrument': instrument,
            'summary': {
                'error_rate_trend': trend_analysis['trend_direction'],
                'current_error_rate': trend_analysis['current_error_rate'],
                'total_runs': total_runs,
                'average_error_rate': trend_analysis['average_error_rate'],
                'total_historical_runs': total_runs
            },
            'patterns': {
                'repeated_patterns': pattern_analysis['repeated_patterns'],
                'error_clusters': pattern_analysis['error_clusters'],
                'systematic_issues': pattern_analysis['systematic_issues'],
                'top_patterns': pattern_analysis['top_patterns'][:5],
                'systematic_issues_detail': pattern_analysis['systematic_issues_detail'][:5]
            },
            'trends': trend_analysis
        }
        
    def get_previous_record(self, pk_val: Any, current_record: Dict[str, Any], 
                          ignore_empty_fields: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Get previous record for temporal validation (inherited from base class).
        
        Note: This is primarily used for temporal validation rules, not the enhanced
        datastore functionality.
        """
        # This would need to be implemented based on the actual data structure
        # For now, return None as this is primarily for temporal validation
        return None
    
    def get_previous_nonempty_record(self, current_record: Dict[str, Any], 
                                   fields: List[str]) -> Optional[Dict[str, Any]]:
        """
        Get previous non-empty record for temporal validation (inherited from base class).
        
        Note: This is primarily used for temporal validation rules, not the enhanced
        datastore functionality.
        """
        # This would need to be implemented based on the actual data structure
        # For now, return None as this is primarily for temporal validation
        return None

    def is_valid_rxcui(self, drug_id: int) -> bool:
        """Check if drug ID is valid (inherited from base class)."""
        return True  # Placeholder implementation
        
    def is_valid_adcid(self, adcid: int) -> bool:
        """Check if ADC ID is valid (inherited from base class)."""
        return True  # Placeholder implementation

