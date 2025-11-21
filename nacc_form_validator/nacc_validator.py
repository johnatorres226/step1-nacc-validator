"""Module for defining NACC specific data validation rules (extending cerberus
library).

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

Original source: https://github.com/naccdata/nacc-form-validator
"""

"""Module for defining NACC specific data validation rules (extending cerberus
library)."""

import copy
import logging
import math
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple

from cerberus.validator import Validator
from dateutil import parser

from nacc_form_validator import utils
from nacc_form_validator.datastore import Datastore
from nacc_form_validator.errors import CustomErrorHandler, ErrorDefs
from nacc_form_validator.json_logic import jsonLogic
from nacc_form_validator.keys import SchemaDefs

log = logging.getLogger(__name__)


class ValidationException(Exception):
    """Raised when an system error occurs during validation."""


class NACCValidator(Validator):
    """NACCValidator class to extend cerberus.Validator."""

    def __init__(self, schema: Dict[str, Any], *args, **kwargs):
        """
        Args:
            schema: Validation schema as Dict[variable, rule objects]
        """

        super().__init__(schema=schema, *args, **kwargs)

        # Data type map for each field
        self.__dtypes: Dict[str, str] = self.__populate_data_types()

        # Datastore instance
        self.__datastore: Optional[Datastore] = None

        # Primary key field of the project
        self.__pk_field: Optional[str] = None

        # Cache of previous records that has been retrieved by subject
        self.__prev_records: Dict[str, Dict[str, Any]] = {}

        # Cache of initial records that has been retrieved by subject
        self.__initial_records: Dict[str, Dict[str, Any]] = {}

        # List of system errors occured by field
        self.__sys_errors: Dict[str, List[str]] = {}

    @property
    def dtypes(self) -> Dict[str, str]:
        """Returns the field->datatype mapping for the fields defined in the
        validation schema."""
        return self.__dtypes

    def __populate_data_types(self) -> Dict[str, str]:
        """Convert cerberus data types to python data types. Populates a
        field->data type mapping for each field in the schema.

        Returns:
            Dict[str, str]: Dict of [field, data_type] or None
        """

        if not self.schema:
            return {}

        data_types = {}
        for key, configs in self.schema.items():
            if SchemaDefs.TYPE in configs:
                if configs[SchemaDefs.TYPE] == "integer":
                    data_types[key] = "int"
                elif configs[SchemaDefs.TYPE] == "string":
                    data_types[key] = "str"
                elif configs[SchemaDefs.TYPE] == "float":
                    data_types[key] = "float"
                elif configs[SchemaDefs.TYPE] == "boolean":
                    data_types[key] = "bool"
                elif configs[SchemaDefs.TYPE] == "date":
                    data_types[key] = "date"
                elif configs[SchemaDefs.TYPE] == "datetime":
                    data_types[key] = "datetime"
                else:
                    log.warning(
                        "Unsupported datatype %s for field %s",
                        configs[SchemaDefs.TYPE],
                        key,
                    )

        return data_types

    @property
    def datastore(self) -> Optional[Datastore]:
        """Returns the datastore object or None."""
        return self.__datastore

    @datastore.setter
    def datastore(self, datastore: Datastore):
        """Set the Datastore instance.

        Args:
            datastore: Datastore instance to retrieve longitudinal data
        """

        self.__datastore = datastore

    @property
    def primary_key(self) -> Optional[str]:
        """Returns the primary key field name or None."""
        return self.__pk_field

    @primary_key.setter
    def primary_key(self, pk_field: str):
        """Set the pk_field attribute.

        Args:
            pk_field: Primary key field of the project
        """

        self.__pk_field = pk_field

    @property
    def sys_errors(self) -> Dict[str, List[str]]:
        """Returns the list of system errors occurred during validation.

        This is different from the validation errors and can be empty.
        Examples: Datastore not set for temporal checks
                  Error in rule definition file
        """
        return self.__sys_errors

    def __add_system_error(self, field: str, err_msg: str):
        """Add system error message.

        Args:
            field: Variable name
            err_msg: Error message
        """
        if field in self.__sys_errors:
            self.__sys_errors[field].append(err_msg)
        else:
            self.__sys_errors[field] = [err_msg]

    def reset_sys_errors(self):
        """Clear the system errors."""

        self.__sys_errors.clear()

    def reset_record_cache(self):
        """Clear the previous records cache."""

        self.__prev_records.clear()

    def get_error_messages(self) -> Dict[int, str]:
        """Returns the list of error messages by error code.

        Check ~cerberus.errors.BasicErrorHandler for more info.

        Returns:
            Dict[int, str]: list of error messages
        """
        return self.error_handler.messages

    def cast_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Cast the fields in the record to appropriate data types.

        Args:
            record: Input record Dict[field, value]

        Returns:
            Dict[str, object]: Casted record Dict[field, value]
        """

        if not self.dtypes:
            return record

        for key, value in record.items():
            # Set empty fields to None (to trigger nullable validations),
            # otherwise data type validation is triggered.
            # Don't remove empty fields from the record, if removed, any
            # validation rules defined for that field will not be triggered.
            if value == "":
                record[key] = None
                continue
            if value is None:
                continue

            if key in self.dtypes:
                try:
                    if self.dtypes[key] == "int":
                        record[key] = int(value)
                    elif self.dtypes[key] == "float":
                        record[key] = float(value)
                    elif self.dtypes[key] == "bool":
                        record[key] = bool(value)
                    elif self.dtypes[key] == "date":
                        record[key] = utils.convert_to_date(value)
                    elif self.dtypes[key] == "datetime":
                        record[key] = utils.convert_to_datetime(value)
                except (ValueError, TypeError, parser.ParserError) as error:
                    log.error(
                        "Failed to cast variable %s, value %s to type %s - %s",
                        key,
                        value,
                        self.dtypes[key],
                        error,
                    )
                    record[key] = value

        for key in self.schema:
            if key not in record:
                record[key] = None

        return record

    def __ensure_datastore_set(self, field: str) -> bool:
        """Ensure the datastore is properly set.

        Args:
            field: Variable name

        Returns:
            True, if datastore properly set, else False

        Raises:
            ValidationException: If Datastore or primary key not set
        """
        if not self.__datastore:
            err_msg = "Datastore not set, cannot validate temporal rules"
            self.__add_system_error(field, err_msg)
            raise ValidationException(err_msg)

        if not self.primary_key:
            err_msg = "Primary key field not set, cannot validate temporal rules"
            self.__add_system_error(field, err_msg)
            raise ValidationException(err_msg)

        if self.primary_key not in self.document or not self.document[
                self.primary_key]:
            self._error(field, ErrorDefs.NO_PRIMARY_KEY, self.primary_key)
            return False

        return True

    def __get_previous_record(
        self,
        field: str,
        ignore_empty_fields: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get the previous record from the Datastore; if not skipping empty
        records, stores it in the prev_records cache.

        Args:
            field: Variable name
            ignore_empty_fields (optional): If provided, will only grab the first
                   previous record where ignore_empty_fields are not empty.

        Returns:
            Dict[str, Any]: Casted record Dict[field, value]
        """
        if not self.__ensure_datastore_set(field):
            return None

        record_id = self.document[self.primary_key]

        # If the previous record was already retrieved and not ignore_empty_fields,
        # use it. Similarly only save into cache if ignore_empty_fields is None/empty
        if not ignore_empty_fields and record_id in self.__prev_records:
            return self.__prev_records[record_id]

        # Grab previous record
        prev_ins = (
            self.__datastore.get_previous_nonempty_record(  # type: ignore
                self.document, ignore_empty_fields) if ignore_empty_fields else
            self.__datastore.get_previous_record(self.document)  # type: ignore
        )

        if prev_ins:
            prev_ins = self.cast_record(prev_ins)

        if not ignore_empty_fields:
            self.__prev_records[record_id] = prev_ins  # type: ignore

        return prev_ins

    def __get_initial_record(
        self,
        field: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the initial record from the Datastore. Returns IVP packet for
        the modules that has initial and follwup packets, else the first record
        sorted by visit date or form date.

        Args:
            field: Variable name

        Returns:
            Dict[str, Any]: Casted record Dict[field, value]
        """

        if not self.__ensure_datastore_set(field):
            return None

        record_id = self.document[self.primary_key]

        # If the initial record was already retrieved return it
        if record_id in self.__initial_records:
            return self.__initial_records[record_id]

        initital_record = self.__datastore.get_initial_record(  # type: ignore
            self.document)
        if initital_record:
            initital_record = self.cast_record(initital_record)
            self.__initial_records[record_id] = initital_record

        return initital_record

    def __get_value_for_key(self,
                            key: str,
                            return_self: bool = True) -> Optional[Any]:
        """Find the value for the specified key.

        Args:
            key: Field name or special key such as current_year
            return_self: Whether or not to return the key itself as the value
                         if none of the conditions are satisifed. If False, just
                         returns None

        Returns:
            Any: Value of the specified key or None
        """
        if key == SchemaDefs.CRR_DATE:
            return datetime.now().date()

        if key == SchemaDefs.CRR_YEAR:
            return datetime.now().date().year

        if key == SchemaDefs.CRR_MONTH:
            return datetime.now().date().month

        if key == SchemaDefs.CRR_DAY:
            return datetime.now().date().day

        if self.document and key in self.document:
            return self.document[key]

        return key if return_self else None

    # pylint: disable=(unused-argument)
    def _validate_formatting(self, formatting: str, field: str,
                             value: object) -> None:
        """Adding formatting attribute to support specifying string dates. This
        is not an actual validation, just a placeholder method.

        Args:
            formatting: format specified in the schema def
            field: Variable name
            value: Variable value

        Note: Don't remove below docstring,
        Cerberus uses it to validate the schema definition.

        The rule's arguments are validated against this schema:
            {
                'nullable': False,
                'type': 'string',
                'allowed': ['date', 'datetime']
            }
        """

        if field not in self.dtypes or self.dtypes[field] != "str":
            err_msg = "formatting definition not supported for non string types"
            self.__add_system_error(field, err_msg)
            raise ValidationException(err_msg)

    def _validate_nullable(self, nullable, field, value):
        """Override nullable rule to drop custom defined rules.

        The rule's arguments are validated against this schema:
            {'type': 'boolean'}
        """
        super()._validate_nullable(nullable, field, value)
        if value is None:
            super()._drop_remaining_rules("compare_age")

    def _convert_value_to_date(
            self,
            target_value: object,
            field: str,
            value: object,
            error_def: ErrorDefs,
            default_dtype: str = 'undefined') -> Optional[date]:
        """Converts the given value to a date object.

        Args:
            target_value: Target value specified in the schema def
            field: Variable name
            value: Variable value
            error_def: The ErrorDef to raise on error
            default_dtype: dtype to use if undefined
        """
        dtype = self.dtypes[field] if field in self.dtypes else default_dtype
        try:
            if dtype == "str":
                return utils.convert_to_date(value)
            elif dtype == "date":
                return value  # type: ignore
            elif dtype == "datetime":
                return value.date()  # type: ignore
            elif dtype == "int" and target_value == SchemaDefs.CRR_YEAR:
                return datetime(value, 1, 1).date()  # type: ignore
            else:
                message = f"{target_value} not supported for {dtype} datatype"
                self._error(field, error_def, message)
                return None
        except (ValueError, TypeError, parser.ParserError) as error:
            self._error(field, error_def, str(error))
            return None

    def _format_min_max(self, target_value: object, field: str, value: object,
                        error_def: ErrorDefs) -> Tuple[object, object]:
        """Format the target value.

        Args:
            target_value: Target value specified in the schema def
            field: Variable name
            value: Variable value
            error_def: The ErrorDef to raise on error
        """
        if SchemaDefs.FORMATTING in self.schema[field]:
            methodname = f"convert_to_{self.schema[field][SchemaDefs.FORMATTING]}"
            func = getattr(utils, methodname, None)
            if func and callable(func):
                try:
                    target_value = func(target_value)
                    value = func(value)
                except (
                        AttributeError,
                        parser.ParserError,
                        TypeError,
                        ValueError,
                ) as error:
                    self._error(field, error_def, str(error))
                    return None, None
            else:
                err_msg = f"{methodname} not defined in the validator module"
                self.__add_system_error(field, err_msg)
                raise ValidationException(err_msg)

        return target_value, value

    def _validate_max(self, max_value: object, field: str, value: object):
        """Override max rule to support validations wrt current date/year.

        Args:
            max_value: Maximum value specified in the schema def
            field: Variable name
            value: Variable value

        Note: Don't remove below docstring,
        Cerberus uses it to validate the schema definition.

        The rule's arguments are validated against this schema:
            {'nullable': False}
        """
        if max_value in (SchemaDefs.CRR_DATE, SchemaDefs.CRR_YEAR):
            dtype = 'int' if max_value == SchemaDefs.CRR_YEAR else 'str'
            input_date = self._convert_value_to_date(
                max_value,
                field,
                value,
                ErrorDefs.INVALID_DATE_MAX,
                default_dtype=dtype)
            if not input_date:
                return

            curr_date = datetime.now().date()

            if max_value == SchemaDefs.CRR_DATE and input_date > curr_date:
                self._error(field, ErrorDefs.CURR_DATE_MAX, str(curr_date))
            elif max_value == SchemaDefs.CRR_YEAR and input_date.year > curr_date.year:
                self._error(field, ErrorDefs.CURR_YEAR_MAX, curr_date.year)
        else:
            max_value, value = self._format_min_max(max_value, field, value,
                                                    ErrorDefs.INVALID_DATE_MAX)
            super()._validate_max(max_value, field, value)

    def _validate_min(self, min_value: object, field: str, value: object):
        """Override min rule to support validations wrt current date/year.

        Args:
            min_value: Minimum value specified in the schema def
            field: Variable name
            value: Variable value

        Note: Don't remove below docstring,
        Cerberus uses it to validate the schema definition.

        The rule's arguments are validated against this schema:
            {'nullable': False}
        """

        if min_value in (SchemaDefs.CRR_DATE, SchemaDefs.CRR_YEAR):
            dtype = 'int' if min_value == SchemaDefs.CRR_YEAR else 'str'
            input_date = self._convert_value_to_date(
                min_value,
                field,
                value,
                ErrorDefs.INVALID_DATE_MIN,
                default_dtype=dtype)
            if not input_date:
                return

            curr_date = datetime.now().date()

            if min_value == SchemaDefs.CRR_DATE and input_date < curr_date:
                self._error(field, ErrorDefs.CURR_DATE_MIN, str(curr_date))
            elif min_value == SchemaDefs.CRR_YEAR and input_date.year < curr_date.year:
                self._error(field, ErrorDefs.CURR_YEAR_MIN, curr_date.year)
        else:
            min_value, value = self._format_min_max(min_value, field, value,
                                                    ErrorDefs.INVALID_DATE_MIN)
            super()._validate_min(min_value, field, value)

    def _validate_filled(self, filled: bool, field: str, value: object):
        """Custom method to check whether the 'filled' rule is met. This is
        different from 'nullable' rule.

        Args:
            filled: Constraint value specified in the schema def
            field: Variable name
            value: Variable value

        Note: Don't remove below docstring,
        Cerberus uses it to validate the schema definition.

        The rule's arguments are validated against this schema:
            {'type': 'boolean'}
        """

        if not filled and value is not None:
            self._error(field, ErrorDefs.FILLED_FALSE)
        elif filled and value is None:
            self._error(field, ErrorDefs.FILLED_TRUE)

    def _check_subschema_valid(
        self,
        all_conditions: Dict[str, object],
        operator: str,
        record: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Creates a temporary validator to check a set of conditions.

        Args:
            all_conditions: Set of conditions to be validated
            operator: Logical operation (AND | OR) to merge the conditions
            record: The record to validate on. If not provided, defaults to the
                    document

        Returns:
            Tuple[bool, object]: Validation result, errors
        """
        if not record:
            record = self.document

        valid = operator != "OR"
        errors: Dict[str, Any] = {}

        for field, conds in all_conditions.items():
            subschema = {field: conds}

            temp_validator = NACCValidator(
                subschema,
                allow_unknown=True,
                error_handler=CustomErrorHandler(subschema),
            )

            # pass the same datastore
            if self.primary_key and self.datastore:
                temp_validator.primary_key = self.primary_key
                temp_validator.datastore = self.datastore

            if operator == "OR":
                valid = valid or temp_validator.validate(record,
                                                         normalize=False)
                # if something passed, don't need to evaluate rest,
                # and ignore any errors found
                if valid:
                    errors = {}
                    break
                # otherwise keep track of all errors
                errors.update(temp_validator.errors)

            # Evaluate as logical AND operation
            elif not temp_validator.validate(record, normalize=False):
                valid = False
                errors = temp_validator.errors
                break

        return valid, errors

    # pylint: disable=(too-many-locals, unused-argument)
    def _validate_compatibility(self, constraints: List[Mapping], field: str,
                                value: object):
        """Validate the List of compatibility checks specified for a field.

        Args:
            constraints: List of constraints specified for the variable
            field: Variable name
            value: Variable value

        Note: Don't remove below docstring,
        Cerberus uses it to validate the schema definition.

        The rule's arguments are validated against this schema:
            {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'index': {
                            'type': 'integer',
                            'required': False
                        },
                        'if_op': {
                            'type': 'string',
                            'required': False,
                            'allowed': ['AND', 'OR', 'and', 'or']
                        },
                        'then_op': {
                            'type': 'string',
                            'required': False,
                            'allowed': ['AND', 'OR', 'and', 'or']
                        },
                        'else_op': {
                            'type': 'string',
                            'required': False,
                            'allowed': ['AND', 'OR', 'and', 'or']
                        },
                        'if': {
                            'type': 'dict',
                            'required': True,
                            'empty': False
                        },
                        'then': {
                            'type': 'dict',
                            'required': True,
                            'empty': False
                        },
                        'else': {
                            'type': 'dict',
                            'required': False,
                            'empty': False
                        }
                    }
                }
            }
        """

        # Evaluate each constraint in the List individually,
        # validation fails if any of the constraints fails.
        rule_no = -1
        for constraint in constraints:
            # Extract operators if specified, default is AND
            if_operator = constraint.get(SchemaDefs.IF_OP, "AND").upper()
            then_operator = constraint.get(SchemaDefs.THEN_OP, "AND").upper()
            else_operator = constraint.get(SchemaDefs.ELSE_OP, "AND").upper()

            # Extract constraint index if specified, or increment by 1
            rule_no = constraint.get(SchemaDefs.INDEX, rule_no + 1)

            # Extract conditions for if clause
            if_conds = constraint[SchemaDefs.IF]

            # Extract conditions for then clause
            then_conds = constraint[SchemaDefs.THEN]

            # Extract conditions for else clause, this is optional
            else_conds = constraint.get(SchemaDefs.ELSE, None)

            # Check if dependencies satisfied the If clause
            error_def = ErrorDefs.COMPATIBILITY
            errors = None
            valid, _ = self._check_subschema_valid(if_conds, if_operator)

            # If the If clause valid, validate the Then clause
            if valid:
                valid, errors = self._check_subschema_valid(
                    then_conds, then_operator)

            # Otherwise validate the else clause, if they exist
            elif else_conds:
                valid, errors = self._check_subschema_valid(
                    else_conds, else_operator)
                error_def = ErrorDefs.COMPATIBILITY_ELSE
            else:  # if the If condition is not satisfied, do nothing
                pass

            # Something in the then/else clause failed - report errors
            if errors:
                for error in errors.items():
                    if error_def == ErrorDefs.COMPATIBILITY:
                        self._error(field, error_def, rule_no, str(error),
                                    if_conds, then_conds)
                    else:
                        self._error(field, error_def, rule_no, str(error),
                                    if_conds, else_conds)

    # pylint: disable=(too-many-locals)
    def _validate_temporalrules(self, temporalrules: List[Mapping], field: str,
                                value: object):
        """Validate the List of longitudial checks specified for a field.

        Args:
            temporalrules: Longitudial checks definitions for the variable
            field: Variable name
            value: Variable value

        Raises:
            ValidationException: If Datastore or primary key not set

        Note: Don't remove below docstring,
        Cerberus uses it to validate the schema definition.

        The rule's arguments are validated against this schema:
            {
                'type': 'list',
                'schema': {
                    'type': 'dict',
                    'schema': {
                        'index': {
                            'type': 'integer',
                            'required': False
                        },
                        'prev_op': {
                            'type': 'string',
                            'required': False,
                            'allowed': ['AND', 'OR', 'and', 'or']
                        },
                        'curr_op': {
                            'type': 'string',
                            'required': False,
                            'allowed': ['AND', 'OR', 'and', 'or']
                        },
                        'previous': {
                            'type': 'dict',
                            'required': True,
                            'empty': False
                        },
                        'current': {
                            'type': 'dict',
                            'required': True,
                            'empty': False
                        },
                        'ignore_empty': {
                            'schema': {
                                'oneof': [
                                    {'type': 'string', 'empty': False},
                                    {
                                        'type': 'list',
                                        'minlength': 1,
                                        'schema': {
                                            'type': "string"
                                        }
                                    }
                                ]
                            },
                            "required": False
                        },
                        'swap_order': {
                            'type': 'boolean',
                            'required': False
                        },
                        'initial_record': {
                            'type': 'boolean',
                            'required': False
                        }
                    }
                }
            }
        """
        rule_no = -1
        for temporalrule in temporalrules:
            swap_order = temporalrule.get(SchemaDefs.SWAP_ORDER, False)
            ignore_empty_fields = temporalrule.get(SchemaDefs.IGNORE_EMPTY,
                                                   None)
            initial_record = temporalrule.get(SchemaDefs.INITIAL_RECORD, False)

            if initial_record and ignore_empty_fields:
                err_msg = (
                    "Cannot specify both initial_record and ignore_empty in "
                    "temporalrule")
                self.__add_system_error(field, err_msg)
                raise ValidationException(err_msg)

            visit_type = "previous" if not initial_record else "initial"

            rule_no = temporalrule.get(SchemaDefs.INDEX, rule_no + 1)

            if isinstance(ignore_empty_fields, str):
                ignore_empty_fields = [ignore_empty_fields]

            prev_ins = None
            if initial_record:
                prev_ins = self.__get_initial_record(field=field)
            else:
                prev_ins = self.__get_previous_record(
                    field=field, ignore_empty_fields=ignore_empty_fields)

            # If previous record was not found, return an error unless
            # ignore_empty_fields was set. If it was set, then no record
            # being returned is okay and we pass through validation
            if not prev_ins:
                if ignore_empty_fields:
                    continue
                self._error(field, ErrorDefs.NO_PREV_VISIT, visit_type)
                return

            # Extract operators if specified, default is AND
            prev_operator = temporalrule.get(SchemaDefs.PREV_OP, "AND").upper()
            curr_operator = temporalrule.get(SchemaDefs.CURR_OP, "AND").upper()

            prev_conds = temporalrule[SchemaDefs.PREVIOUS]
            curr_conds = temporalrule[SchemaDefs.CURRENT]

            # default order of operations is to first check if conditions for
            # previous visit is satisfied, then current visit, but
            # occasionally we need to swap that order
            error, valid = None, False
            error_def = ErrorDefs.TEMPORAL

            if not swap_order:
                # Check if conditions for the previous visit is satisfied
                valid, _ = self._check_subschema_valid(prev_conds,
                                                       prev_operator,
                                                       record=prev_ins)

                # If not satisfied, continue to next rule
                if not valid:
                    continue

                # If satisfied, validate the current visit
                valid, errors = self._check_subschema_valid(
                    curr_conds, curr_operator)
            else:
                # do the other way; check if condition for current visit is satisfied
                error_def = ErrorDefs.TEMPORAL_SWAPPED
                valid, _ = self._check_subschema_valid(curr_conds,
                                                       curr_operator)

                # if not satisfied, continue to next rule
                if not valid:
                    continue

                # if satisfied, validate previous visit
                valid, errors = self._check_subschema_valid(prev_conds,
                                                            prev_operator,
                                                            record=prev_ins)

            # Cross visit validation failed - report errors
            if not valid and errors:
                for error in errors.items():
                    self._error(field, error_def, rule_no, str(error),
                                prev_conds, curr_conds, visit_type)

    def _validate_logic(self, logic: Dict[str, Any], field: str,
                        value: object):
        """Validate a mathematical formula/expression.

        Args:
            logic: Validation logic specified in the rule definition
            field: Variable name
            value: Variable value

        Note: Don't remove below docstring,
        Cerberus uses it to validate the schema definition.

        The rule's arguments are validated against this schema:
            {
                'type': 'dict',
                'schema': {
                    'formula': {'type': 'dict', 'required': True, 'empty': False},
                    'errmsg': {'type': 'string', 'required': False, 'empty': False}
                }
            }
        """

        formula = logic[SchemaDefs.FORMULA]
        err_msg = logic.get(SchemaDefs.ERRMSG, None)
        if not err_msg:
            err_msg = f"value {value} does not satisfy the specified formula"
        try:
            if not jsonLogic(formula, self.document):
                self._error(field, ErrorDefs.FORMULA, err_msg)
        except ValueError as error:
            self._error(field, ErrorDefs.FORMULA, str(error))

    def _validate_function(self, function: Dict[str, Any], field: str,
                           value: object):
        """Validate using a custom defined function.

        Args:
            function: Dict specifying function name and arguments
            field: Variable name
            value: Variable value

        Note: Don't remove below docstring,
        Cerberus uses it to validate the schema definition.

        The rule's arguments are validated against this schema:
            {
                'type': 'dict',
                'schema': {
                    'name': {'type': 'string', 'required': True, 'empty': False},
                    'args': {'type': 'dict', 'required': False}
                }
            }
        """

        function_name = "_" + function.get(SchemaDefs.FUNCTION_NAME,
                                           "undefined")
        func = getattr(self, function_name, None)
        if func and callable(func):
            kwargs = function.get(SchemaDefs.FUNCTION_ARGS, {})
            func(field, value, **kwargs)
        else:
            err_msg = f"{function_name} not defined in the validator module"
            self.__add_system_error(field, err_msg)
            raise ValidationException(err_msg)

    def _validate_compute_gds(self, keys: List[str], field: str,
                              value: object):
        """Validate Geriatric Depression Scale (GDS) calculation.

        Args:
            keys: GDS computation fields specified in the rule definition
            field: Variable name
            value: Variable value

        Note: Don't remove below docstring,
        Cerberus uses it to validate the schema definition.

        The rule's arguments are validated against this schema:
            {
                'type': 'list',
                'minlength': 15,
                'schema': {'type': 'string'}
            }
        """

        nogds = 0
        if "nogds" in self.document:
            nogds = self.document["nogds"]

        num_valid = 0
        gds = 0
        for key in keys:
            if key in self.document and self.document[key] in [1, 0]:
                num_valid += 1
                gds += self.document[key]

        if nogds == 1:
            if value != 88:
                self._error(field, ErrorDefs.CHECK_GDS_1, 0)

            if num_valid >= 12:
                self._error(field, ErrorDefs.CHECK_GDS_2, 1)

            return

        if num_valid == 15 and gds != value:
            self._error(field, ErrorDefs.CHECK_GDS_3, 2, value, gds)
            return

        # calculate prorated GDS
        num_unanswered = 15 - num_valid
        if num_unanswered <= 3:
            raw_gds = gds + (gds / num_valid) * (num_unanswered)

            # ensures 0.5 rounds up, not down
            gds = int(math.floor(raw_gds + 0.5))

            if gds != value:
                self._error(field, ErrorDefs.CHECK_GDS_4, 3, value, gds)

        if (not nogds or nogds == 0) and num_valid < 12:
            self._error(field, ErrorDefs.CHECK_GDS_5, 4)
            return

    def _validate_compare_with(self, comparison: Dict[str, Any], field: str,
                               value: object):
        """Apply the specified comparison.

        Args:
            comparison: Comparison specified in the rule definition
            field: Variable name
            value: Variable value

        Note: Don't remove below docstring,
        Cerberus uses it to validate the schema definition.

        The rule's arguments are validated against this schema:
            {
                'type': 'dict',
                'schema': {
                    'comparator': {
                        'type': 'string',
                        'required': True,
                        'empty': False,
                        'allowed': [">", "<", ">=", "<=", "==", "!="]
                    },
                    'base': {
                        'type': ['string', 'number'],
                        'required': True,
                        'empty': False
                    },
                    'adjustment': {
                        'type': ['string', 'number'],
                        'required': False,
                        'empty': False,
                        'dependencies': 'op'
                    },
                    'op': {
                        'type': 'string',
                        'required': False,
                        'empty': False,
                        'allowed': ["+", "-", "*", "/", "abs"],
                        'dependencies': 'adjustment'
                    },
                    'previous_record': {
                        'type': 'boolean',
                        'required': False
                    },
                    'ignore_empty': {
                        'type': 'boolean',
                        'required': False,
                        'dependencies': 'previous_record'
                    },
                    'initial_record': {
                        'type': 'boolean',
                        'required': False
                    }
                }
            }
        """

        comparator = comparison[SchemaDefs.COMPARATOR]
        base = comparison[SchemaDefs.BASE]
        adjustment = comparison.get(SchemaDefs.ADJUST, None)
        operator = comparison.get(SchemaDefs.OP, None)

        prev_record = comparison.get(SchemaDefs.PREV_RECORD, False)
        ignore_empty = comparison.get(SchemaDefs.IGNORE_EMPTY, False)
        initial_record = comparison.get(SchemaDefs.INITIAL_RECORD, False)

        if prev_record and initial_record:
            err_msg = (
                "Cannot specify both prev_record and initial_record for " +
                "comparison rule")
            self.__add_system_error(field, err_msg)
            raise ValidationException(err_msg)

        if initial_record and ignore_empty:
            err_msg = (
                "Cannot specify both initial_record and ignore_empty for " +
                "comparison rule")
            self.__add_system_error(field, err_msg)
            raise ValidationException(err_msg)

        visit_type = "previous" if not initial_record else "initial"
        base_str = f"{base} ({visit_type} record)" if (
            prev_record or initial_record) else base
        comparison_str = f"{field} {comparator} {base_str}"
        if adjustment and operator:
            if operator == "abs":
                comparison_str = f"abs({field} - {base_str}) {comparator} {adjustment}"
            else:
                comparison_str += f" {operator} {adjustment}"

        if prev_record or initial_record:
            ignore_empty_fields = [base] if ignore_empty else None
            if prev_record:
                record = self.__get_previous_record(
                    field=base, ignore_empty_fields=ignore_empty_fields)
                # pass through validation if no records found and ignore_empty is True
                if not record and ignore_empty:
                    return
            else:
                record = self.__get_initial_record(field=base)

            base_val = record[base] if record else None
        else:
            base_val = self.__get_value_for_key(base)

        if base_val is None:
            error = (ErrorDefs.COMPARE_WITH_PREV
                     if prev_record else ErrorDefs.COMPARE_WITH)
            self._error(field, error, comparison_str, visit_type)
            return

        try:
            adjusted_value = base_val
            if adjustment and operator:
                adjustment = self.__get_value_for_key(adjustment)
                if operator == "+":
                    adjusted_value = base_val + adjustment
                elif operator == "-":
                    adjusted_value = base_val - adjustment
                elif operator == "*":
                    adjusted_value = base_val * adjustment
                elif operator == "/":
                    adjusted_value = base_val / adjustment
                elif operator == "abs":
                    value = abs(value - base_val)  # type: ignore
                    adjusted_value = adjustment

            valid = utils.compare_values(comparator, value, adjusted_value)
            if not valid:
                self._error(field, ErrorDefs.COMPARE_WITH, comparison_str)
        except (TypeError, ValueError):
            self._error(field, ErrorDefs.COMPARE_WITH, comparison_str)

    def _check_with_rxnorm(self, field: str, value: Optional[int]):
        """Check whether the specified value is a valid RXCUI
        https://www.nlm.nih.gov/research/umls/rxnorm/overview.html
        https://mor.nlm.nih.gov/RxNav/

        Args:
            field: Variable name
            value: Variable value

        Raises:
            ValidationException: If Datastore not set
        """

        # No need to validate if blank or 0 (No RXCUI code available)
        if not value or value == 0:
            return

        if not self.datastore:
            err_msg = "Datastore not set, cannot validate RXNORM codes"
            self.__add_system_error(field, err_msg)
            raise ValidationException(err_msg)

        if not self.datastore.is_valid_rxcui(value):
            self._error(field, ErrorDefs.RXNORM, value)

    def _validate_compare_age(self, comparison: Dict[str, Any], field: str,
                              value: object):
        """Validate a comparison between the field and a list of compare_to
        values.

        Args:
            comparison: Comparison specified in the rule definition
            field: Variable name
            value: Variable value

        Note: Don't remove below docstring,
        Cerberus uses it to validate the schema definition.

        The rule's arguments are validated against this schema:
            {
                'type': 'dict',
                'schema': {
                    'comparator': {
                        'type': 'string',
                        'required': True,
                        'empty': False,
                        'allowed': [">", "<", ">=", "<=", "==", "!="]
                    },
                    'birth_year': {
                        'type': ['string', 'integer'],
                        'required': True,
                        'empty': False
                    },
                    'birth_month': {
                        'type': ['string', 'integer'],
                        'required': False
                    },
                    'birth_day': {
                        'type': ['string', 'integer'],
                        'required': False
                    },
                    'compare_to': {
                        'required': True,
                        'schema': {
                            'oneof': [
                                {'type': 'string', 'empty': False},
                                {'type': 'integer', 'empty': False},
                                {
                                    'type': 'list',
                                    'minlength': 1,
                                    'schema': {
                                        'type': ['string', 'integer']
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        """
        comparator = comparison[SchemaDefs.COMPARATOR]
        ages_to_compare = comparison[SchemaDefs.COMPARE_TO]

        if isinstance(ages_to_compare, (str, int)):
            ages_to_compare = [ages_to_compare]

        try:
            value = utils.convert_to_date(value)
        except (ValueError, TypeError, parser.ParserError) as error:
            self._error(field, ErrorDefs.DATE_CONVERSION, value, error)
            return

        comparison_str = (
            f"age at {field} {comparator} {', '.join(map(str, ages_to_compare))}"
        )

        # calculates age at the value of this field given the
        # birth fields and assumes the ages_to_compare values to are also numerical
        birth_month = self.__get_value_for_key(
            comparison.get(SchemaDefs.BIRTH_MONTH, 1))
        birth_day = self.__get_value_for_key(
            comparison.get(SchemaDefs.BIRTH_DAY, 1))
        birth_year = self.__get_value_for_key(
            comparison[SchemaDefs.BIRTH_YEAR])

        try:
            birth_date = utils.convert_to_date(f"{birth_month:02d} \
                                               /{birth_day:02d} \
                                               /{birth_year:04d}")
        except (TypeError, ValueError):
            self._error(field, ErrorDefs.INVALID_BIRTH_DATES)
            return

        # age calculation is based off of how RT has defined it in A1
        age = (value - birth_date).days / 365.25

        for compare_field in ages_to_compare:
            compare_value = self.__get_value_for_key(compare_field)
            try:
                valid = utils.compare_values(comparator, age, compare_value)
                if not valid:
                    self._error(field, ErrorDefs.COMPARE_AGE, compare_field,
                                comparison_str)
            except TypeError as error:
                self._error(
                    field,
                    ErrorDefs.COMPARE_AGE_INVALID_COMPARISON,
                    compare_field,
                    field,
                    age,
                    str(error),
                )

    def _check_adcid(self, field: str, value: int, own: bool = True):
        """Check whether a given ADCID is valid.

        Args:
            field: name of ADCID field
            value: ADCID value
            own (optional): whether to check own ADCID or another center's ADCID.

        Raises:
            ValidationException: If Datastore not set
        """

        if not self.datastore:
            err_msg = "Datastore not set, cannot validate ADCID"
            self.__add_system_error(field, err_msg)
            raise ValidationException(err_msg)

        if not self.datastore.is_valid_adcid(value, own):
            self._error(
                field,
                ErrorDefs.ADCID_NOT_MATCH
                if own else ErrorDefs.ADCID_NOT_VALID,
                value,
            )

    def _score_variables(
        self,
        field: str,
        value: int,
        mode: str,
        scoring_key: Dict[str, Any],
        logic: Dict[str, Any],
        calc_var_name: str = "__total_sum",
    ) -> None:
        """Sums all the variables that are correct or incorrect depending on
        the mode based on scoring_key. Stores the result a special variable
        defined by calc_var_name (defaults to __total_sum, note double
        underscore to ensure uniqueness) and runs the defined logic formula
        against it in a subschema. `logic` field MUST specify the
        calc_var_name.

        If any of the keys in the scoring_key are missing/blank/non-integer value,
        this validation is skipped.

        'function': {
            'name': 'score_variables',
            'args': {
                'mode': 'correct' or 'incorrect',
                'scoring_key': {
                    'key1': correct_val,
                    'key2': correct_val,
                    ...
                },
                'logic': {
                    ... same schema as logic ...
                }
            }
        }

        Args:
            field: Name of the scored field
            value: Value of the scored field
            mode: Whether to count all correct or all incorrect variables
            scoring_key: Scoring key for all variables
            logic: Logic formula to run result on
            calc_var_name: The name of the variable to store the calculation
                under. Should be unique to the record.
        """
        total_sum = 0
        for key, correct_value in scoring_key.items():
            if self.document.get(key, None) is None:
                log.warning(
                    f"Field {key} not present or blank, skipping validation")
                return

            correct = self.document[key] == correct_value
            if (correct and mode == "correct") or (not correct
                                                   and mode == "incorrect"):
                total_sum += 1

        condition = {field: {"nullable": True, "logic": logic}}

        if calc_var_name in self.document:
            raise ValueError(
                f"{calc_var_name} already exists in record, cannot use " +
                "as calc_var_name")

        record = copy.deepcopy(self.document)
        record[calc_var_name] = total_sum

        valid, errors = self._check_subschema_valid(
            all_conditions=condition,  # type: ignore
            operator="AND",
            record=record)

        # Logic formula failed, report errors
        if errors:
            for error in errors.items():
                self._error(field, ErrorDefs.SCORING_INVALID, value)