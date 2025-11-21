# quality_check.py

"""Module for performing data quality checks.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

Original source: https://github.com/naccdata/nacc-form-validator

This module defines the `QualityCheck` class, which serves as the primary
entry point for validating a single record against a Cerberus schema. It
initializes a `NACCValidator` instance and uses it to perform the validation,
capturing any errors or system failures that occur.
"""

"""Module for performing data quality checks."""

from typing import Any, Dict, List, Optional, Tuple

from cerberus.errors import DocumentErrorTree
from cerberus.schema import SchemaError

from nacc_form_validator.datastore import Datastore
from nacc_form_validator.errors import CustomErrorHandler
from nacc_form_validator.nacc_validator import NACCValidator, ValidationException


class QualityCheckException(Exception):
    """Raised if something goes wrong while loading rule definitions."""


class QualityCheck:
    """Class to initiate validator object with the provided schema and run the
    data quality checks."""

    def __init__(
        self,
        pk_field: str,
        schema: Dict[str, Dict[str, Any]],
        strict: bool = True,
        datastore: Optional[Datastore] = None,
    ):
        """

        Args:
            pk_field: Primary key field of the project
            schema: Validation rules schema as Dict[field, rule objects].
            strict (optional): Validation mode, defaults to True.
                    If False, unknown forms/fields are skipped from validation
            datastore (optional): Datastore instance to retrieve previous data
        """

        self.__pk_field: str = pk_field
        self.__strict: bool = strict
        self.__schema: Dict[str, Dict[str, Any]] = schema

        # Validator object for rule evaluation
        self.__validator: NACCValidator = None  # type: ignore
        self.__init_validator(datastore)

    @property
    def pk_field(self) -> str:
        """primary key field.

        Returns:
            str: primary key field of validated data
        """
        return self.__pk_field

    @property
    def schema(self) -> Dict[str, Dict[str, Any]]:
        """The schema property.

        Returns:
            Dict[str, Dict[str, Any]]:
            Schema of validation rules defined in the project
        """
        return self.__schema

    @property
    def validator(self) -> NACCValidator:
        """The validator property.

        Returns:
            NACCValidator: Validator object for rule evaluation
        """
        return self.__validator

    def __init_validator(self, datastore: Optional[Datastore] = None):
        """Initialize the validator object.

        Raises:
            QualityCheckException: If there is an schema error
        """
        try:
            self.__validator = NACCValidator(
                self.schema,
                allow_unknown=not self.__strict,
                error_handler=CustomErrorHandler(self.schema),
            )
        except (SchemaError, RuntimeError) as error:
            raise QualityCheckException(f"Schema Error - {error}") from error

        if datastore and self.pk_field != datastore.pk_field:
            raise QualityCheckException(
                f"Mismatched primary key fields - {self.pk_field}, {datastore.pk_field}"
            )

        self.validator.primary_key = self.pk_field
        self.validator.datastore = datastore

    def validate_record(
        self, record: Dict[str, str]
    ) -> Tuple[bool, bool, Dict[str, List[str]], DocumentErrorTree]:
        """Evaluate the record against the defined rules using cerberus.

        Args:
            record (Dict[str, str]): Record to be validated, Dict[field, value]

        Returns:
            bool: True if the record satisfied all rules
            bool: True if system error occurred
            Dict[str, List[str]: Dict of formatted error messages by variable
            DocumentErrorTree: A dict like object of ValidationError instances
            (check https://docs.python-cerberus.org/errors.html)
        """

        # All the fields in the input record represented as string values,
        # cast the fields to appropriate data types according to the schema
        cst_record = self.validator.cast_record(record.copy())

        # Validate the record against the defined schema
        sys_failure = False
        passed = False
        try:
            self.validator.reset_sys_errors()
            self.validator.reset_record_cache()
            passed = self.validator.validate(cst_record, normalize=False)
        except ValidationException:
            sys_failure = True

        if sys_failure:
            errors = self.validator.sys_errors
            error_tree = None
        else:
            errors = self.validator.errors
            error_tree = self.validator.document_error_tree

        return passed, sys_failure, errors, error_tree