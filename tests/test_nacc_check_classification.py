"""Tests for variable context enrichment from the REDCap data dictionary."""

import json

# ---------------------------------------------------------------------------
# _strip_html
# ---------------------------------------------------------------------------


class TestStripHtml:
    def test_plain_text_unchanged(self):
        from src.pipeline.reports.report_pipeline import _strip_html

        assert _strip_html("1a. Birth month") == "1a. Birth month"

    def test_removes_div_and_p_tags(self):
        from src.pipeline.reports.report_pipeline import _strip_html

        raw = '<div class="rich-text-field-label"><p>5a. Depression/dysphoria</p></div>'
        assert _strip_html(raw) == "5a. Depression/dysphoria"

    def test_removes_inline_span(self):
        from src.pipeline.reports.report_pipeline import _strip_html

        raw = '2b. Age at visit <span style="color:red">*</span>'
        assert _strip_html(raw) == "2b. Age at visit *"

    def test_empty_string(self):
        from src.pipeline.reports.report_pipeline import _strip_html

        assert _strip_html("") == ""


# ---------------------------------------------------------------------------
# _is_missingness_error
# ---------------------------------------------------------------------------


class TestIsMissingnessError:
    def test_null_value_not_allowed(self):
        from src.pipeline.reports.report_pipeline import _is_missingness_error

        assert _is_missingness_error("null value not allowed") is True

    def test_cannot_be_blank(self):
        from src.pipeline.reports.report_pipeline import _is_missingness_error

        assert _is_missingness_error("field cannot be blank") is True

    def test_must_be_blank(self):
        from src.pipeline.reports.report_pipeline import _is_missingness_error

        assert _is_missingness_error("must be blank when X = 0") is True

    def test_range_error_is_not_missingness(self):
        from src.pipeline.reports.report_pipeline import _is_missingness_error

        assert _is_missingness_error("must be between 1 and 12") is False

    def test_compatibility_rule_is_not_missingness(self):
        from src.pipeline.reports.report_pipeline import _is_missingness_error

        assert (
            _is_missingness_error(
                "('bedep', ['unallowed value 0']) for if {'depd': {'allowed': [1]}} "
                "then {'bedep': {'allowed': [1]}} - compatibility rule no: 0"
            )
            is False
        )


# ---------------------------------------------------------------------------
# _build_variable_context
# ---------------------------------------------------------------------------


class TestBuildVariableContext:
    """Tests for _build_variable_context with a mocked data dictionary."""

    _MOCK_DD = {
        "birthmo": {
            "form": "a1_participant_demographics",
            "field_label": "1a. Participant's month of birth",
            "choices": "1, January | 2, February | 3, March",
        },
        "depd": {
            "form": "b5_npiq",
            "field_label": "5a. Depression/dysphoria",
            "choices": "1, Yes | 0, No | 9, Unknown",
        },
        "bedep": {
            "form": "b9_clinician_judgment",
            "field_label": "12b. Depressed mood",
            "choices": "0, No | 1, Yes | 9, Unknown",
        },
    }

    def _patch(self, monkeypatch):
        from src.pipeline.reports import report_pipeline

        monkeypatch.setattr(report_pipeline, "_DATA_DICT", self._MOCK_DD)
        monkeypatch.setattr(report_pipeline, "_DATA_DICT_LOADED", True)

    def test_missingness_returns_only_field_label(self, monkeypatch):
        self._patch(monkeypatch)
        from src.pipeline.reports.report_pipeline import _build_variable_context

        result = json.loads(_build_variable_context("birthmo", "null value not allowed"))
        assert result["field_label"] == "1a. Participant's month of birth"
        assert "choices" not in result
        assert "form" not in result

    def test_conformity_returns_full_entry(self, monkeypatch):
        self._patch(monkeypatch)
        from src.pipeline.reports.report_pipeline import _build_variable_context

        result = json.loads(_build_variable_context("birthmo", "must be between 1 and 12"))
        assert result["variable"] == "birthmo"
        assert result["form"] == "a1_participant_demographics"
        assert result["field_label"] == "1a. Participant's month of birth"
        assert "choices" in result

    def test_conformity_omits_choices_when_empty(self, monkeypatch):
        from src.pipeline.reports import report_pipeline

        dd = {"zipcode": {"form": "a1", "field_label": "ZIP code", "choices": ""}}
        monkeypatch.setattr(report_pipeline, "_DATA_DICT", dd)
        monkeypatch.setattr(report_pipeline, "_DATA_DICT_LOADED", True)
        from src.pipeline.reports.report_pipeline import _build_variable_context

        result = json.loads(_build_variable_context("zipcode", "must be between 006 and 999"))
        assert "choices" not in result

    def test_compat_rule_returns_array_with_both_variables(self, monkeypatch):
        self._patch(monkeypatch)
        from src.pipeline.reports.report_pipeline import _build_variable_context

        msg = (
            "('bedep', ['unallowed value 0']) for if {'depd': {'allowed': [1]}} "
            "then {'bedep': {'allowed': [1]}} - compatibility rule no: 0"
        )
        result = json.loads(_build_variable_context("bedep", msg))
        assert isinstance(result, list)
        assert len(result) == 2
        vars_in_result = {r["variable"] for r in result}
        assert vars_in_result == {"bedep", "depd"}

    def test_compat_rule_includes_full_entry_for_each_variable(self, monkeypatch):
        self._patch(monkeypatch)
        from src.pipeline.reports.report_pipeline import _build_variable_context

        msg = (
            "('bedep', ['unallowed value 0']) for if {'depd': {'allowed': [1]}} "
            "then {'bedep': {'allowed': [1]}} - compatibility rule no: 0"
        )
        result = json.loads(_build_variable_context("bedep", msg))
        for entry in result:
            assert "form" in entry
            assert "field_label" in entry
            assert "choices" in entry

    def test_unknown_variable_returns_empty_string(self, monkeypatch):
        self._patch(monkeypatch)
        from src.pipeline.reports.report_pipeline import _build_variable_context

        assert _build_variable_context("unknown_var_xyz", "some error") == ""

    def test_compat_rule_deeply_nested_then_includes_all_vars(self, monkeypatch):
        """All variables from if/then clauses must appear in context, not just the trigger."""
        from src.pipeline.reports import report_pipeline

        extended_dd = {
            **self._MOCK_DD,
            "lmndist": {
                "form": "b8_neurological_examination_findings",
                "field_label": "4c. Face or limb findings in an LMN distribution",
                "choices": (
                    "0, Absent | 1, Focal or Unilateral"
                    " | 2, Bilateral & Largely Symmetric"
                    " | 3, Bilateral & Largely Asymmetric | 8, Not Assessed"
                ),
            },
            "othersign": {
                "form": "b8_neurological_examination_findings",
                "field_label": "4. Cortical/Pyramidal/Other Signs",
                "choices": "0, No abnormal signs | 1, Yes | 8, Not assessed",
            },
            "limbaprax": {
                "form": "b8_neurological_examination_findings",
                "field_label": "Limb apraxia",
                "choices": (
                    "1, Focal or Unilateral"
                    " | 2, Bilateral & Largely Symmetric"
                    " | 3, Bilateral & Largely Asymmetric"
                ),
            },
            "umndist": {
                "form": "b8_neurological_examination_findings",
                "field_label": "UMN distribution",
                "choices": (
                    "1, Focal or Unilateral"
                    " | 2, Bilateral & Largely Symmetric"
                    " | 3, Bilateral & Largely Asymmetric"
                ),
            },
        }
        monkeypatch.setattr(report_pipeline, "_DATA_DICT", extended_dd)
        monkeypatch.setattr(report_pipeline, "_DATA_DICT_LOADED", True)
        from src.pipeline.reports.report_pipeline import _build_variable_context

        msg = (
            "('lmndist', ['unallowed value 0']) for if {'othersign': {'allowed': [1]}} "
            "then {'limbaprax': {'allowed': [1, 2, 3]}, 'umndist': {'allowed': [1, 2, 3]}, "
            "'lmndist': {'allowed': [1, 2, 3]}} - compatibility rule no: 2"
        )
        result = json.loads(_build_variable_context("lmndist", msg))
        assert isinstance(result, list)
        vars_in_result = {r["variable"] for r in result}
        # failing var + IF trigger + all THEN clause vars must all be present
        assert vars_in_result == {"lmndist", "othersign", "limbaprax", "umndist"}
        assert len(result) == 4
        # failing variable must be first
        assert result[0]["variable"] == "lmndist"

    def test_empty_dict_returns_empty_string(self, monkeypatch):
        from src.pipeline.reports import report_pipeline

        monkeypatch.setattr(report_pipeline, "_DATA_DICT", {})
        monkeypatch.setattr(report_pipeline, "_DATA_DICT_LOADED", True)
        from src.pipeline.reports.report_pipeline import _build_variable_context

        assert _build_variable_context("birthmo", "null value not allowed") == ""
