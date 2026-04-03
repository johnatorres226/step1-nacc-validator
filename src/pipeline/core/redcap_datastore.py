"""
In-memory REDCap datastore for temporal rule validation.

This module provides a datastore implementation that uses in-memory data from
the current batch to support temporal validation rules. This allows cross-visit
comparisons within the scope of data already fetched from REDCap.

LIMITATION: This datastore only has visibility into records present in the
current batch. It cannot access historical records not included in the fetch.
Full historical datastore would require REDCap API queries or external database.
"""

import logging
from typing import Any

import pandas as pd

from nacc_form_validator.datastore import Datastore

logger = logging.getLogger(__name__)


class REDCapDatastore(Datastore):
    """
    In-memory datastore implementation for temporal rule validation.

    This class implements the NACC Datastore interface using a pandas DataFrame
    of records from the current batch. It enables temporal validation rules to
    compare current records against previous/initial visits within the batch.

    Attributes:
        _data: DataFrame containing all records in current batch
        _pk_field: Primary key field name (e.g., 'ptid')
        _orderby: Field to sort records by (e.g., 'visitdate')
    """

    def __init__(
        self,
        data: pd.DataFrame,
        pk_field: str = "ptid",
        orderby: str = "visitdate",
    ):
        """
        Initialize the in-memory datastore.

        Args:
            data: DataFrame containing all records from current batch
            pk_field: Primary key field to identify participants
            orderby: Field to sort records by (typically visit date)
        """
        super().__init__(pk_field, orderby)
        self._data = data.copy()
        self._pk_field = pk_field
        self._orderby = orderby

        # Sort by participant and visit date for efficient lookups
        if self._orderby in self._data.columns:
            self._data = self._data.sort_values([self._pk_field, self._orderby])

        logger.debug(
            "REDCapDatastore initialized with %d records, orderby=%s",
            len(self._data),
            self._orderby,
        )

    def _get_participant_records(self, current_record: dict[str, Any]) -> pd.DataFrame:
        """Get all records for the participant in current_record."""
        pk_value = current_record.get(self._pk_field)
        if not pk_value:
            return pd.DataFrame()

        mask = self._data[self._pk_field] == pk_value
        return self._data[mask]

    def get_previous_record(self, current_record: dict[str, Any]) -> dict[str, Any] | None:
        """
        Return the previous visit record for the specified participant.

        Args:
            current_record: Record currently being validated

        Returns:
            Previous record dict or None if no previous record found
        """
        participant_records = self._get_participant_records(current_record)
        if participant_records.empty:
            return None

        current_date = current_record.get(self._orderby)
        if not current_date:
            return None

        # Find records before current visit date
        if self._orderby in participant_records.columns:
            earlier = participant_records[participant_records[self._orderby] < current_date]
            if not earlier.empty:
                # Return the most recent previous record
                return earlier.iloc[-1].to_dict()

        return None

    def get_previous_nonempty_record(
        self,
        current_record: dict[str, Any],
        ignore_empty_fields: list[str],
    ) -> dict[str, Any] | None:
        """
        Return the previous record where specified fields are not empty.

        Args:
            current_record: Record currently being validated
            ignore_empty_fields: Fields to check for non-empty values

        Returns:
            Previous non-empty record or None if none found
        """
        participant_records = self._get_participant_records(current_record)
        if participant_records.empty:
            return None

        current_date = current_record.get(self._orderby)
        if not current_date:
            return None

        # Find records before current visit date
        if self._orderby in participant_records.columns:
            earlier = participant_records[participant_records[self._orderby] < current_date]

            # Filter to records where all specified fields are non-empty
            for field in ignore_empty_fields:
                if field in earlier.columns:
                    earlier = earlier[earlier[field].notna() & (earlier[field] != "")]

            if not earlier.empty:
                return earlier.iloc[-1].to_dict()

        return None

    def get_initial_record(self, current_record: dict[str, Any]) -> dict[str, Any] | None:
        """
        Return the initial (first) record for the participant.

        For UDS data, returns the IVP (Initial Visit Packet) record if available,
        otherwise returns the first record sorted by visit date.

        Args:
            current_record: Record currently being validated

        Returns:
            Initial record dict or None if not found
        """
        participant_records = self._get_participant_records(current_record)
        if participant_records.empty:
            return None

        # Try to find IVP packet first
        if "packet" in participant_records.columns:
            ivp_records = participant_records[participant_records["packet"].str.upper() == "I"]
            if not ivp_records.empty:
                return ivp_records.iloc[0].to_dict()

        # Otherwise return first record by visit date
        if self._orderby in participant_records.columns:
            return participant_records.iloc[0].to_dict()

        return None

    def get_uds_ivp_record(self, current_record: dict[str, Any]) -> dict[str, Any] | None:
        """
        Return the UDS IVP record for the participant.

        Args:
            current_record: Record currently being validated

        Returns:
            UDS IVP record dict or None if not found
        """
        participant_records = self._get_participant_records(current_record)
        if participant_records.empty:
            return None

        # Filter to UDS IVP records (packet = 'I')
        if "packet" in participant_records.columns:
            ivp_records = participant_records[participant_records["packet"].str.upper() == "I"]
            if not ivp_records.empty:
                return ivp_records.iloc[0].to_dict()

        return None

    def is_valid_rxcui(self, drugid: int) -> bool:
        """
        Check whether a given drug ID is valid RXCUI.

        NOTE: This implementation cannot validate RXCUI codes without external
        API access. Returns True to avoid false negatives.

        Args:
            drugid: Provided drug ID

        Returns:
            True (validation skipped - would require external API)
        """
        # Cannot validate RXCUI without external API access
        logger.debug("RXCUI validation skipped for %s (requires external API)", drugid)
        return True

    def is_valid_adcid(self, adcid: int, own: bool) -> bool:
        """
        Check whether a given ADCID is valid.

        NOTE: This implementation cannot validate ADCIDs without external
        database access. Returns True to avoid false negatives.

        Args:
            adcid: Provided ADCID
            own: Whether to check own ADCID or another center's ADCID

        Returns:
            True (validation skipped - would require external database)
        """
        # Cannot validate ADCID without external database access
        logger.debug("ADCID validation skipped for %s (requires external database)", adcid)
        return True
