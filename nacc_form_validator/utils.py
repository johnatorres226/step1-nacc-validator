"""This module provides utility functions for the QC pipeline.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

Original source: https://github.com/naccdata/nacc-form-validator
"""

import logging
import math
import re
from typing import Any

from dateutil import parser

# utils.py

"""Utility functions."""


log = logging.getLogger(__name__)


def convert_to_date(value) -> Any:
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


def convert_to_datetime(value) -> Any:
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


def compare_values(comparator: str, value: Any, base_value: Any) -> bool:
    """Compare two values.

    Args:
        comparator: str, The comparator
        value: The value being evaluated on
        base_value: The value being evaluated against

    Returns:
        bool: True if the formula is satisfied, else False
    """
    # try close enough equality if both are floats first
    both_floats = False
    if isinstance(value, (str, int, float)) \
            and isinstance(base_value, (str, int, float)):
        try:
            float(value)  # don't actually set it to a in case we die at b
            float(base_value)
            both_floats = True
        except ValueError:
            pass

    # test these first as they don't care about null values
    if comparator == "==":
        return value == base_value if not both_floats else \
            math.isclose(float(value), float(base_value), abs_tol=1e-2)

    if comparator == "!=":
        return value != base_value if not both_floats else \
            not math.isclose(float(value), float(base_value), abs_tol=1e-2)

    if comparator not in ["<=", ">=", "<", ">"]:
        raise TypeError(f"Unrecognized comparator: {comparator}")

    # for < and >, follow same convention as jsonlogic for null values
    # for >= and <=, allow equality case (both None)
    if value is None and base_value is None:
        return True if comparator in ["<=", ">="] else False

    if value is None or base_value is None:
        return False

    try:
        # Attempt numeric comparison first
        num_value = float(value)
        num_base_value = float(base_value)
        if comparator == ">=":
            return num_value >= num_base_value
        if comparator == ">":
            return num_value > num_base_value
        if comparator == "<=":
            return num_value <= num_base_value
        if comparator == "<":
            return num_value < num_base_value
    except (ValueError, TypeError):
        # Fallback to string comparison
        str_value = str(value)
        str_base_value = str(base_value)
        if comparator == ">=":
            return str_value >= str_base_value
        if comparator == ">":
            return str_value > str_base_value
        if comparator == "<=":
            return str_value <= str_base_value
        if comparator == "<":
            return str_value < str_base_value

    return False  # Should not be reached
