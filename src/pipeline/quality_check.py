# quality_check.py

"""Module for performing data quality checks.

This module defines the `QualityCheck` class, which serves as the primary
entry point for validating a single record against a Cerberus schema. It
initializes a `NACCValidator` instance and uses it to perform the validation,
capturing any errors or system failures that occur.
"""

from typing import Any, Dict, Mapping, Optional

from cerberus.schema import SchemaError

from pipeline.datastore import Datastore
from pipeline.errors import CustomErrorHandler
from pipeline.models import ValidationResult
from pipeline.nacc_validator import NACCValidator, ValidationException


class QualityCheckException(Exception):
    """Custom exception for errors during QualityCheck initialization."""


class QualityCheck:
    """Coordinates the validation of a single data record against a schema.

    This class wraps the `NACCValidator`, configuring it with a specific schema,
    primary key, and optional datastore for cross-record validation. It provides
    a simple interface to validate a record and retrieve structured results.

    Attributes:
        pk_field: The primary key field of the data being validated.
        schema: The Cerberus validation schema.
        validator: The configured `NACCValidator` instance.
    """

    def __init__(
        self,
        pk_field: str,
        schema: Mapping[str, Any],
        strict: bool = True,
        datastore: Optional[Datastore] = None,
    ):
        """Initializes the QualityCheck instance and its validator.

        Args:
            pk_field: Primary key field name for the data.
            schema: A dictionary representing the Cerberus validation schema.
            strict: If True, unknown fields in records will raise an error.
                    If False, they will be ignored. Defaults to True.
            datastore: An optional `Datastore` instance for validations
                       that require access to other records.

        Raises:
            QualityCheckException: If the schema is invalid or if there's a
                                   mismatch in primary keys with the datastore.
        """
        self.pk_field: str = pk_field
        self.schema: Mapping[str, Any] = schema
        self.__strict: bool = strict
        # The 'compatibility' rule is not a standard Cerberus rule.
        # It's a custom rule implemented in NACCValidator.
        # We need to inform Cerberus about this custom rule to avoid warnings.
        self.validator: NACCValidator = self._init_validator(datastore)
        self.validator.allow_unknown = {'schema': {'compatibility': {'type': 'list'}}}


    def _init_validator(self, datastore: Optional[Datastore]) -> NACCValidator:
        """Creates and configures the NACCValidator instance.

        Args:
            datastore: The datastore to be used by the validator.

        Returns:
            A configured `NACCValidator` instance.

        Raises:
            QualityCheckException: If there is a schema compilation error or
                                   a primary key mismatch with the datastore.
        """
        try:
            validator = NACCValidator(
                self.schema,
                allow_unknown=not self.__strict,
                error_handler=CustomErrorHandler(self.schema),
            )
        except (SchemaError, RuntimeError) as e:
            raise QualityCheckException(f"Schema Error: {e}") from e

        if datastore and self.pk_field != datastore.pk_field:
            raise QualityCheckException(
                "Mismatched primary key fields: "
                f"QualityCheck pk is '{self.pk_field}', "
                f"but Datastore pk is '{datastore.pk_field}'."
            )

        validator.primary_key = self.pk_field
        validator.datastore = datastore
        return validator

    def validate_record(self, record: Dict[str, Any]) -> ValidationResult:
        """Validates a single record against the configured schema.

        This method performs type casting on the input record before running
        the validation. It captures validation results, including system-level
        failures (e.g., errors in rule logic) separately from standard
        validation errors.

        Args:
            record: The data record to validate, as a dictionary.

        Returns:
            A `ValidationResult` object containing the outcome of the validation.
        
        Raises:
            QualityCheckException: If the validator was not initialized correctly.
        """
        if not self.validator:
            # This should not be reachable due to the __init__ structure,
            # but it's a safeguard.
            raise QualityCheckException("Validator is not initialized.")

        # Cast fields to appropriate data types as defined in the schema.
        # A copy is made to avoid modifying the original record.
        cst_record = self.validator.cast_record(record.copy())

        sys_failure = False
        passed = False
        try:
            # Reset state for the new validation run
            self.validator.reset_sys_errors()
            self.validator.reset_record_cache()
            passed = self.validator.validate(cst_record, normalize=False)
        except ValidationException:
            # Captures critical errors within the validation logic itself
            sys_failure = True

        errors = (
            self.validator.sys_errors if sys_failure else self.validator.errors
        )
        error_tree = (
            None if sys_failure else self.validator.document_error_tree
        )

        return ValidationResult(
            passed=passed,
            sys_failure=sys_failure,
            errors=errors,
            error_tree=error_tree,
        )
