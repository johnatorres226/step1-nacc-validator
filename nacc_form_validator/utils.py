"""This module provides utility functions for the QC pipeline.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

Original source: https://github.com/naccdata/nacc-form-validator
"""

"""Utility functions."""

import logging
import math
import re
from datetime import date, datetime
from typing import Any, Optional

from dateutil import parser

log = logging.getLogger(__name__)


def convert_to_date(value: Any) -> date:
    """Convert the input value to date object.

    Args:
        value: value to convert

    Returns:
        Any: date object or original value if conversion failed
    """
    if not isinstance(value, str):
        raise ValueError(
            f'"convert to date" not supported for non string value {value}')

    yearfirst = False
    if re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}$", value):
        yearfirst = True

    try:
        return parser.parse(value, yearfirst=yearfirst).date()
    except (ValueError, TypeError, parser.ParserError) as error:
        raise parser.ParserError(error) from error


def convert_to_datetime(value: Any) -> datetime:
    """Convert the input value to datetime object.

    Args:
        value: value to convert

    Returns:
        Any: datetime object or original value if conversion failed
    """

    if not isinstance(value, str):
        raise ValueError(
            f'"convert to datetime" not supported for non string value {value}'
        )

    yearfirst = False
    if re.match(r"^\d{4}[-/]\d{2}[-/]\d{2}$", value):
        yearfirst = True

    try:
        return parser.parse(value, yearfirst=yearfirst)
    except (ValueError, TypeError, parser.ParserError) as error:
        raise parser.ParserError(error) from error


def get_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

    return None


def compare_values(comparator: str, value: Any, base_value: Any) -> bool:
    """Compare two values.

    Args:
        comparator: str, The comparator
        value: The value being evaluated on
        base_value: The value being evaluated against

    Returns:
        bool: True if the formula is satisfied, else False
    """
    if comparator not in ["==", "!=", "<=", ">=", "<", ">"]:
        raise TypeError(f"Unrecognized comparator: {comparator}")

    # for < and >, follow same convention as jsonlogic for null values
    # for >= and <=, allow equality case (both None)
    if value is None and base_value is None:
        return True if comparator in ["<=", "==", ">="] else False
    # if only one is None, return True for !=
    if ((value is None) != (base_value is None)) and comparator == "!=":
        return True
    if value is None:
        return True if comparator in ["<", "<="] else False
    if base_value is None:
        return False if comparator in ["<", "<="] else True

    # try close enough equality if both are floats
    float_value = get_float(value)
    float_base_value = get_float(base_value)
    if float_value is not None and float_base_value is not None:
        comp = math.isclose(float_value, float_base_value, abs_tol=1e-2)
        if comparator == "==":
            return comp

        if comparator == "!=":
            return not comp

    # now try as normal
    if comparator == "==":
        return value == base_value
    if comparator == "!=":
        return value != base_value
    if comparator == ">=":
        return value >= base_value
    if comparator == ">":
        return value > base_value
    if comparator == "<=":
        return value <= base_value
    if comparator == "<":
        return value < base_value

    return False