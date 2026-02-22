"""
Processing context for the QC pipeline.
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from ..config.config_manager import QCConfig


@dataclass
class ProcessingContext:
    """Context object containing all data and configuration needed for processing."""

    data_df: pd.DataFrame
    instrument_list: list[str]
    rules_cache: dict[str, Any]
    primary_key_field: str
    config: QCConfig | None = None

    @property
    def is_empty(self) -> bool:
        return self.data_df.empty

    def get_instrument_variables(self, instrument: str) -> list[str]:
        return list(self.rules_cache.get(instrument, {}).keys())

    def filter_to_instruments(self, instruments: list[str]) -> "ProcessingContext":
        return ProcessingContext(
            data_df=self.data_df,
            instrument_list=[i for i in instruments if i in self.instrument_list],
            rules_cache={i: r for i, r in self.rules_cache.items() if i in instruments},
            primary_key_field=self.primary_key_field,
            config=self.config,
        )
