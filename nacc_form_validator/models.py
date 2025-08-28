"""Data models for the QC pipeline.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.

Original source: https://github.com/naccdata/nacc-form-validator
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from cerberus.errors import DocumentErrorTree


@dataclass
class ValidationResult:
    """Represents the outcome of a single record's validation.

    Attributes:
        passed: True if the record satisfied all validation rules.
        sys_failure: True if a system-level error (e.g., a faulty rule
                     or database connection issue) occurred during validation,
                     preventing a reliable outcome.
        errors: A dictionary where keys are field names and values are lists
                of human-readable error messages for that field.
        error_tree: An optional, more detailed tree structure of validation
                    errors provided by the Cerberus validator. This is useful
                    for debugging rules.
    """

    passed: bool
    sys_failure: bool
    errors: Dict[str, List[str]]
    error_tree: Optional[DocumentErrorTree]
