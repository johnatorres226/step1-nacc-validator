# tests/test_datastore.py

import pytest
import pandas as pd
from datetime import datetime

# Temporarily add src to path to allow for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from pipeline.datastore import PandasDatastore

@pytest.fixture
def sample_dataframe():
    """Fixture to create a sample pandas DataFrame for testing."""
    data = {
        'subject_id': [1, 1, 2, 3, 3, 3],
        'visit_date': [
            datetime(2022, 1, 1),
            datetime(2023, 1, 1),
            datetime(2022, 6, 15),
            datetime(2021, 5, 1),
            datetime(2022, 5, 1),
            datetime(2023, 5, 1),
        ],
        'value1': [10, 20, 30, 40, 50, 60],
        'value2': ['A', 'B', 'C', 'D', 'E', 'F'],
    }
    return pd.DataFrame(data)

@pytest.fixture
def datastore(sample_dataframe):
    """Fixture to create a PandasDatastore instance."""
    return PandasDatastore(pk_field='subject_id', orderby='visit_date', all_records_df=sample_dataframe)

def test_initialization(datastore, sample_dataframe):
    """Test that the datastore is initialized correctly."""
    assert datastore.pk_field == 'subject_id'
    assert datastore.orderby == 'visit_date'
    assert datastore.all_records.equals(sample_dataframe.sort_values(by='visit_date'))

def test_get_previous_record_exists(datastore):
    """Test retrieving a previous record when one exists."""
    current_record = {
        'subject_id': 1,
        'visit_date': datetime(2023, 1, 1),
        'value1': 20,
    }
    previous_record = datastore.get_previous_record(pk_val=1, current_record=current_record)
    
    assert previous_record is not None
    assert previous_record['subject_id'] == 1
    assert previous_record['visit_date'] == datetime(2022, 1, 1)
    assert previous_record['value1'] == 10

def test_get_previous_record_is_first_visit(datastore):
    """Test retrieving a previous record for the first visit of a subject."""
    current_record = {
        'subject_id': 1,
        'visit_date': datetime(2022, 1, 1),
        'value1': 10,
    }
    previous_record = datastore.get_previous_record(pk_val=1, current_record=current_record)
    assert previous_record is None

def test_get_previous_record_subject_not_found(datastore):
    """Test retrieving a record for a subject that does not exist."""
    current_record = {
        'subject_id': 99,
        'visit_date': datetime(2023, 1, 1),
    }
    previous_record = datastore.get_previous_record(pk_val=99, current_record=current_record)
    assert previous_record is None

def test_get_previous_record_orderby_field_missing(datastore):
    """Test behavior when the orderby field is missing from the current record."""
    current_record = {
        'subject_id': 1,
        # 'visit_date' is missing
    }
    previous_record = datastore.get_previous_record(pk_val=1, current_record=current_record)
    assert previous_record is None

def test_get_previous_record_multiple_previous(datastore):
    """Test retrieving the immediately preceding record when multiple previous visits exist."""
    current_record = {
        'subject_id': 3,
        'visit_date': datetime(2023, 5, 1),
    }
    previous_record = datastore.get_previous_record(pk_val=3, current_record=current_record)
    
    assert previous_record is not None
    assert previous_record['subject_id'] == 3
    assert previous_record['visit_date'] == datetime(2022, 5, 1)
    assert previous_record['value1'] == 50

def test_placeholder_validation_methods(datastore):
    """Test that the placeholder validation methods return True."""
    assert datastore.is_valid_rxcui(12345) is True
    assert datastore.is_valid_adcid(99) is True
