"""Error-code and schema related constants.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

Original source: https://github.com/naccdata/nacc-form-validator
"""

"""Error-code and schema related constants."""

from typing import Mapping, Optional

from cerberus.errors import (
    BasicErrorHandler,
    ErrorDefinition,
    ErrorTree,
    ValidationError,
)

from nacc_form_validator.keys import SchemaDefs

# pylint: disable=(too-few-public-methods)


class ErrorDefs:
    """Class to define custom errors."""

    # IMPORTANT - When adding a new error DON'T change the existing codes
    # Error codes are used to map b/w cerberus errors and NACC QC check codes
    # Cerberus uses bit 5 and bit 7 to mark specific error types
    # Check https://docs.python-cerberus.org/customize.html for more info
    CURR_DATE_MAX = ErrorDefinition(0x1000, "max")
    CURR_YEAR_MAX = ErrorDefinition(0x1001, "max")
    INVALID_DATE_MAX = ErrorDefinition(0x1002, "max")
    CURR_DATE_MIN = ErrorDefinition(0x1003, "min")
    CURR_YEAR_MIN = ErrorDefinition(0x1004, "min")
    INVALID_DATE_MIN = ErrorDefinition(0x1005, "min")
    FILLED_TRUE = ErrorDefinition(0x1006, "filled")
    FILLED_FALSE = ErrorDefinition(0x1007, "filled")
    COMPATIBILITY = ErrorDefinition(0x1008, "compatibility")
    COMPATIBILITY_ELSE = ErrorDefinition(0x1009, "compatibility")
    TEMPORAL = ErrorDefinition(0x2000, "temporalrules")
    NO_PRIMARY_KEY = ErrorDefinition(0x2001, "temporalrules")
    NO_PREV_VISIT = ErrorDefinition(0x2002, "temporalrules")
    FORMULA = ErrorDefinition(0x2003, "logic")
    CHECK_GDS_1 = ErrorDefinition(0x2004, "compute_gds")
    CHECK_GDS_2 = ErrorDefinition(0x2005, "compute_gds")
    CHECK_GDS_3 = ErrorDefinition(0x2006, "compute_gds")
    CHECK_GDS_4 = ErrorDefinition(0x2007, "compute_gds")
    CHECK_GDS_5 = ErrorDefinition(0x2008, "compute_gds")
    COMPARE_WITH = ErrorDefinition(0x2009, "compare_with")
    COMPARE_WITH_PREV = ErrorDefinition(0x3000, "compare_with")
    RXNORM = ErrorDefinition(0x3001, "check_with")
    DATE_CONVERSION = ErrorDefinition(0x3002, "compare_age")
    COMPARE_AGE = ErrorDefinition(0x3003, "compare_age")
    COMPARE_AGE_INVALID_COMPARISON = ErrorDefinition(0x3004, "compare_age")
    TEMPORAL_SWAPPED = ErrorDefinition(0x3005, "temporalrules")
    ADCID_NOT_MATCH = ErrorDefinition(0x3006, "function")
    ADCID_NOT_VALID = ErrorDefinition(0x3007, "function")
    SCORING_INVALID = ErrorDefinition(0x3008, "function")
    INVALID_BIRTH_DATES = ErrorDefinition(0x3009, "compare_age")


class CustomErrorHandler(BasicErrorHandler):
    """Class to provide custom error messages."""

    def __init__(self,
                 schema: Optional[Mapping] = None,
                 tree: Optional[ErrorTree] = None):
        """
        Args:
            schema (optional): Validation schema as dict[field, rule objects].
            tree (optional): Validation errors tree.
        """

        super().__init__()
        self.__set_custom_error_codes()
        self._custom_schema = schema

    def __set_custom_error_codes(self):
        """Add custom error codes specific to NACC validation rules."""
        # IMPORTANT - When adding a new error DON'T change the existing codes
        # Cerberus uses bit 5 and bit 7 to mark specific error types
        # Check https://docs.python-cerberus.org/customize.html for more info
        # Error messages are synced with ErrorDefs using the error code
        # Error codes are used to map b/w cerberus errors and NACC QC check codes
        custom_errors = {
            0x1000:
            "cannot be greater than current date {0}",
            0x1001:
            "cannot be greater than current year {0}",
            0x1002:
            "max date/year comparison error - {0}",
            0x1003:
            "cannot be less than current date {0}",
            0x1004:
            "cannot be less than current year {0}",
            0x1005:
            "min date/year comparison error - {0}",
            0x1006:
            "cannot be empty",
            0x1007:
            "must be empty",
            0x1008:
            "{1} for if {2} then {3} - compatibility rule no: {0}",
            0x1009:
            "{1} for if {2} else {3} - compatibility rule no: {0}",
            0x2000:
            "{1} for if {2} in {4} visit then {3} " +
            "in current visit - temporal rule no: {0}",
            0x2001:
            "primary key variable {0} not set in current visit data",
            0x2002:
            "failed to retrieve the {0} visit, cannot proceed with " +
            "validation",
            0x2003:
            "error in formula evaluation - {0}",
            0x2004:
            "If GDS not attempted (nogds=1), total GDS score should be 88 " +
            "- GDS rule no: {0}",
            0x2005:
            "If GDS not attempted (nogds=1), there cannot be >=12 " +
            "questions with valid scores - GDS rule no: {0}",
            0x2006:
            "incorrect GDS score {1}, expected value {2} - GDS rule no: {0}",
            0x2007:
            "incorrect prorated GDS score {1}, expected value {2} - GDS " +
            "rule no: {0}",
            0x2008:
            "If GDS attempted (nogds = 0 or blank), at least 12 questions " +
            "need to have valid scores - GDS rule no: {0}",
            0x2009:
            "input value doesn't satisfy the condition {0}",
            0x3000:
            "failed to retrieve record for {1} visit, cannot proceed " +
            "with validation {0}",
            0x3001:
            "Drug ID {0} is not a valid RXCUI",
            0x3002:
            "failed to convert value {0} to a date: {1}",
            0x3003:
            "input value {0} doesn't satisfy the condition: {1}",
            0x3004:
            "Error in comparing {0} to age at {1} ({2}): {3}",
            0x3005:
            "{1} for if {3} in current visit then {2} " +
            "in {4} visit - temporal rule no: {0}",
            0x3006:
            "Provided ADCID {0} does not match your center's ADCID",
            0x3007:
            "Provided ADCID {0} is not in the valid list of ADCIDs",
            0x3008:
            "Provided value {0} does not match the expected score",
            0x3009:
            "Cannot compute birth date, one or more components empty or " +
            "malformed",
        }

        self.messages.update(custom_errors)

    def _format_message(self, field: str, error: ValidationError):
        """Display custom error message. Use the 'meta' tag in the schema to
        specify a custom error message e.g. "meta": {"errmsg": "<custom
        message>"}

        Args:
            field: Variable name
            error: Error object generated by applying validation rules
        """

        if self._custom_schema and field in self._custom_schema:
            error_msg = (self._custom_schema[field].get(
                SchemaDefs.META, {}).get(SchemaDefs.ERRMSG, ""))
            if error_msg:
                return field + ": " + error_msg

        return super()._format_message(field, error)