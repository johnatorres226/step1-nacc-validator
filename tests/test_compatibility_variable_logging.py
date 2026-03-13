"""
Test for compatibility rule error variable logging bug.

Bug: When a compatibility rule fails, the error is logged with the wrong variable name.
- Expected: The actual failing variable from the THEN/ELSE clause (e.g., 'apraxsp')
- Actual (before fix): The trigger variable from the IF clause (e.g., 'othersign')

This is a regression test to ensure the fix is preserved when updating nacc_form_validator.

Example from b8_neurological_examination_findings:
    Rule: if othersign=1, then apraxsp must be in [1,2,3]
    When apraxsp=0 (invalid), error should report variable='apraxsp', not 'othersign'

Upstream package: https://github.com/naccdata/nacc-form-validator
Issue: https://github.com/naccdata/nacc-form-validator/issues/[TBD]

Solution: We parse the error message in report_pipeline.py to extract the actual
failing variable name from compatibility rule errors.
"""

from src.pipeline.reports.report_pipeline import _extract_failing_variable


def test_extract_failing_variable_from_compatibility_error():
    """Test that _extract_failing_variable correctly parses compatibility errors."""

    # Compatibility error format: "('variable', [...]) for if {...} then/else {...}"
    error_msg = (
        "('apraxsp', ['unallowed value 0']) for if {'othersign': {'allowed': [1]}} "
        "then {'apraxsp': {'allowed': [1, 2, 3]}} - compatibility rule no: 0"
    )

    # Field name is the trigger variable (wrong)
    field_name = "othersign"

    # Should extract 'apraxsp' from the error message
    actual_var = _extract_failing_variable(field_name, error_msg)
    assert actual_var == "apraxsp", f"Expected 'apraxsp', got '{actual_var}'"


def test_extract_failing_variable_else_clause():
    """Test extraction for ELSE clause compatibility errors."""

    error_msg = (
        "('result_var', ['unallowed value 50']) for if {'trigger_var': {'allowed': [1]}} "
        "else {'result_var': {'allowed': [30, 40]}} - compatibility rule no: 0"
    )

    field_name = "trigger_var"
    actual_var = _extract_failing_variable(field_name, error_msg)
    assert actual_var == "result_var"


def test_extract_failing_variable_non_compatibility_error():
    """Non-compatibility errors should return the original field_name unchanged."""

    # Regular validation error (not compatibility)
    error_msg = "unallowed value"
    field_name = "some_field"

    actual_var = _extract_failing_variable(field_name, error_msg)
    assert actual_var == field_name, "Non-compatibility errors should return field_name"


def test_extract_failing_variable_with_special_characters():
    """Test variable names with underscores and numbers."""

    error_msg = (
        "('var_name_123', ['must be empty']) for if {'trigger': {'allowed': [1]}} "
        "then {'var_name_123': {'filled': False}} - compatibility rule no: 2"
    )

    field_name = "trigger"
    actual_var = _extract_failing_variable(field_name, error_msg)
    assert actual_var == "var_name_123"


def test_extract_failing_variable_real_world_b8_example():
    """Test with actual error message from NM0117 b8_neurol output."""

    # This is the exact error message format from the production CSV
    error_msg = (
        "('apraxsp', ['unallowed value 0']) for if "
        "{'othersign': {'allowed': [1]}} then "
        "{'limbaprax': {'allowed': [1, 2, 3]}, "
        "'umndist': {'allowed': [1, 2, 3]}, "
        "'lmndist': {'allowed': [1, 2, 3]}, "
        "'vfieldcut': {'allowed': [1, 2, 3]}, "
        "'limbatax': {'allowed': [1, 2, 3]}, "
        "'myoclon': {'allowed': [1, 2, 3]}, "
        "'unisomato': {'allowed': [1, 2, 3]}, "
        "'aphasia': {'allowed': [1, 2, 3]}, "
        "'alienlimb': {'allowed': [1, 2, 3]}, "
        "'hspatneg': {'allowed': [1, 2, 3]}, "
        "'pspoagno': {'allowed': [1, 2, 3]}, "
        "'smtagno': {'allowed': [1, 2, 3]}, "
        "'opticatax': {'allowed': [1, 2, 3]}, "
        "'apraxgaze': {'allowed': [1, 2, 3]}, "
        "'vhgazepal': {'allowed': [1, 2, 3]}, "
        "'dysarth': {'allowed': [1, 2, 3]}, "
        "'apraxsp': {'allowed': [1, 2, 3]}} - compatibility rule no: 2"
    )

    field_name = "othersign"
    actual_var = _extract_failing_variable(field_name, error_msg)

    # Should extract 'apraxsp' not 'othersign'
    assert actual_var == "apraxsp", (
        f"Real-world b8_neurol error should extract 'apraxsp' from message, got '{actual_var}'"
    )


def test_extract_failing_variable_with_nested_quotes():
    """Test extraction with nested quotes in error message."""

    error_msg = (
        "('complex_var', [\"value can't be 0\"]) for if "
        "{'trigger': {'allowed': [1]}} then "
        "{'complex_var': {'allowed': [1, 2]}} - compatibility rule no: 5"
    )

    field_name = "trigger"
    actual_var = _extract_failing_variable(field_name, error_msg)
    assert actual_var == "complex_var"
