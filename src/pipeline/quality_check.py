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
    primary key for the data validation, and optional datastore for temporal 
    validations. It provides a simple interface to validate a record and 
    retrieve structured results.

    Attributes:
        pk_field: The primary key field name for the record.
        schema: The validation schema rules.
        datastore: Optional datastore for temporal and previous record validations.
        validator: The configured `NACCValidator` instance.
    """

    def __init__(
        self,
        schema: Mapping[str, Any],
        pk_field: str,
        datastore: Optional[Datastore] = None,
        strict: bool = False,
    ) -> None:
        """Initialize the QualityCheck with schema, primary key, and optional datastore.

        Args:
            schema: The Cerberus validation schema to apply.
            pk_field: The name of the primary key field.
            datastore: Optional datastore instance for temporal validations.
                      If None, temporal validations will be skipped with warnings.
            strict: Whether to disallow unknown fields in validation.

        Raises:
            QualityCheckException: If the schema is invalid or there's a
                                   configuration error.
        """
        self.pk_field: str = pk_field
        self.schema: Mapping[str, Any] = schema
        self.datastore: Optional[Datastore] = datastore
        self.strict: bool = strict
        self.validator: NACCValidator = self._init_validator()

    # @profile  # Uncomment if using `line_profiler` or similar tools
    def _init_validator(self) -> NACCValidator:
        """Creates and configures the NACCValidator instance.

        Returns:
            A configured `NACCValidator` instance.

        Raises:
            QualityCheckException: If there is a schema compilation error or
                                   datastore configuration mismatch.
        """
        try:
            validator = NACCValidator(
                self.schema,
                allow_unknown=not self.strict,  # Use strict mode setting
                error_handler=CustomErrorHandler(self.schema),
            )
        except (SchemaError, RuntimeError) as e:
            raise QualityCheckException(f"Schema Error: {e}") from e

        # Set primary key
        validator.primary_key = self.pk_field
        
        # Set datastore if provided and validate primary key compatibility
        if self.datastore:
            if self.datastore.pk_field != self.pk_field:
                raise QualityCheckException(
                    f"Mismatched primary key fields: schema='{self.pk_field}', "
                    f"datastore='{self.datastore.pk_field}'"
                )
            validator.datastore = self.datastore
        
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
