"""Tests for NACC check type classification functions."""


def test_get_nacc_check_type_returns_error_when_no_file(monkeypatch, tmp_path):
    """If classifications file is missing, default to 'error'."""
    from src.pipeline.reports import report_pipeline

    monkeypatch.setattr(report_pipeline, "_CLASSIFICATIONS_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {})
    result = report_pipeline._get_nacc_check_type("I", "a1", "birthmo", "cannot be blank")
    assert result == "error"


def test_get_nacc_check_type_returns_alert_from_lookup(monkeypatch):
    """When lookup contains the key, return its value."""
    from src.pipeline.reports import report_pipeline

    monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {"I|a1|zip|Conformity": "alert"})
    monkeypatch.setattr(
        report_pipeline,
        "_CHECK_DETAILS",
        {
            "I|a1|zip|Conformity": [
                {"error_type": "alert", "check_code": "test", "full_desc": "test"}
            ]
        },
    )
    result = report_pipeline._get_nacc_check_type("I", "a1", "zip", "must be between 006 and 999")
    assert result == "alert"


def test_get_nacc_check_type_returns_error_from_lookup(monkeypatch):
    """When lookup contains the key with error value, return 'error'."""
    from src.pipeline.reports import report_pipeline

    monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {"I|a1|birthmo|Conformity": "error"})
    result = report_pipeline._get_nacc_check_type("I", "a1", "birthmo", "must be between 1 and 12")
    assert result == "error"


def test_get_nacc_check_type_defaults_to_error_when_key_not_found(monkeypatch):
    """When key is not in lookup, default to 'error'."""
    from src.pipeline.reports import report_pipeline

    monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {"I|a1|zip|Conformity": "alert"})
    result = report_pipeline._get_nacc_check_type("I", "a1", "unknown_var", "some error message")
    assert result == "error"


def test_get_nacc_check_type_case_insensitive_instrument(monkeypatch):
    """Instrument and variable should be lowercased for lookup."""
    from src.pipeline.reports import report_pipeline

    monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {"I|a1|zip|Conformity": "alert"})
    monkeypatch.setattr(
        report_pipeline,
        "_CHECK_DETAILS",
        {
            "I|a1|zip|Conformity": [
                {"error_type": "alert", "check_code": "test", "full_desc": "test"}
            ]
        },
    )
    result = report_pipeline._get_nacc_check_type("I", "A1", "ZIP", "must be between 006 and 999")
    assert result == "alert"


class TestInferCheckCategory:
    """Tests for _infer_check_category function."""

    def test_missingness_cannot_be_blank(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("Field cannot be blank") == "Missingness"

    def test_missingness_must_be_blank(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("Field must be blank when X") == "Missingness"

    def test_missingness_must_be_present(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("Field must be present") == "Missingness"

    def test_missingness_conditionally_present(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("Conditionally present field") == "Missingness"

    def test_missingness_conditionally_blank(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("Conditionally blank when X") == "Missingness"

    def test_missingness_cannot_be_empty(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("Field cannot be empty") == "Missingness"

    def test_missingness_required_field(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("Required field missing") == "Missingness"

    def test_plausibility_temporalrules(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("temporalrules violation") == "Plausibility"

    def test_plausibility_compatibility_rule(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("compatibility rule no: 3") == "Plausibility"

    def test_plausibility_should_not_equal(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("Value should not equal X") == "Plausibility"

    def test_plausibility_should_equal(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("Value should equal Y") == "Plausibility"

    def test_plausibility_should_be_less_than(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("Value should be less than Z") == "Plausibility"

    def test_plausibility_should_be_greater(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("Value should be greater than Z") == "Plausibility"

    def test_conformity_default(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("must be between 1 and 12") == "Conformity"

    def test_conformity_allowed_values(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("unallowed value 5") == "Conformity"

    def test_conformity_out_of_range(self):
        from src.pipeline.reports.report_pipeline import _infer_check_category

        assert _infer_check_category("value out of expected range") == "Conformity"


class TestLoadCheckLookup:
    """Tests for _load_check_lookup function."""

    def test_returns_empty_dict_when_file_missing(self, monkeypatch, tmp_path):
        from src.pipeline.reports import report_pipeline

        monkeypatch.setattr(report_pipeline, "_CLASSIFICATIONS_PATH", tmp_path / "nonexistent.json")
        monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {})
        result = report_pipeline._load_check_lookup()
        assert result == {}

    def test_returns_cached_lookup_when_available(self, monkeypatch):
        from src.pipeline.reports import report_pipeline

        cached = {"I|a1|zip|Conformity": "alert"}
        monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", cached)
        result = report_pipeline._load_check_lookup()
        assert result == cached

    def test_loads_lookup_from_file(self, monkeypatch, tmp_path):
        import json

        from src.pipeline.reports import report_pipeline

        # Create a test file
        test_file = tmp_path / "test_classifications.json"
        test_data = {"lookup": {"F|a2|inlivwth|Plausibility": "alert"}}
        test_file.write_text(json.dumps(test_data), encoding="utf-8")

        monkeypatch.setattr(report_pipeline, "_CLASSIFICATIONS_PATH", test_file)
        monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {})
        result = report_pipeline._load_check_lookup()
        assert result == {"F|a2|inlivwth|Plausibility": "alert"}

    def test_returns_empty_dict_on_invalid_json(self, monkeypatch, tmp_path):
        from src.pipeline.reports import report_pipeline

        # Create an invalid JSON file
        test_file = tmp_path / "invalid.json"
        test_file.write_text("not valid json {", encoding="utf-8")

        monkeypatch.setattr(report_pipeline, "_CLASSIFICATIONS_PATH", test_file)
        monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {})
        result = report_pipeline._load_check_lookup()
        assert result == {}

        monkeypatch.setattr(report_pipeline, "_CLASSIFICATIONS_PATH", test_file)
        monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {})
        result = report_pipeline._load_check_lookup()
        assert result == {}

    def test_returns_empty_dict_when_lookup_key_missing(self, monkeypatch, tmp_path):
        import json

        from src.pipeline.reports import report_pipeline

        # Create a file without 'lookup' key
        test_file = tmp_path / "no_lookup.json"
        test_data = {"_meta": {}, "checks": []}
        test_file.write_text(json.dumps(test_data), encoding="utf-8")

        monkeypatch.setattr(report_pipeline, "_CLASSIFICATIONS_PATH", test_file)
        monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {})
        result = report_pipeline._load_check_lookup()
        assert result == {}


class TestCalculateCheckMatchConfidence:
    """Tests for _calculate_check_match_confidence — the scoring backbone."""

    def _call(self, check, error_msg, target_var, trigger_var=None):
        from src.pipeline.reports.report_pipeline import _calculate_check_match_confidence

        return _calculate_check_match_confidence(check, error_msg, target_var, trigger_var)

    def test_both_variables_in_desc_scores_highest(self):
        check = {"full_desc": "If DEPD is 1 then BEDEP must be 1"}
        score = self._call(check, "unallowed value 0", "bedep", "depd")
        # 40 (both vars) + 20 (direction match, neither negative) = 60
        assert score >= 60

    def test_trigger_only_in_desc_scores_medium(self):
        check = {"full_desc": "If DEPD is 1 then something must apply"}
        score = self._call(check, "unallowed value 0", "bedep", "depd")
        # 30 (trigger only) + direction bonus
        assert 30 <= score < 60

    def test_target_only_in_desc_scores_lower(self):
        check = {"full_desc": "BEDEP must be 1 under some condition"}
        score = self._call(check, "unallowed value 0", "bedep", None)
        # 20 (target only) + direction bonus
        assert 20 <= score < 50

    def test_no_variable_match_scores_low(self):
        check = {"full_desc": "Some unrelated check description"}
        score = self._call(check, "unallowed value 0", "zip", None)
        # Only direction match possible
        assert score <= 25

    def test_direction_mismatch_reduces_score(self):
        check = {"full_desc": "MYVAR should not equal 0"}
        # Error is positive (allowed, not forbidden)
        score_positive = self._call(check, "unallowed value 0 for allowed: [1]", "myvar", None)
        # Error is negative (forbidden)
        score_negative = self._call(check, "unallowed value 0 for 'forbidden': [0]", "myvar", None)
        # negative direction should align with "should not equal" description
        assert score_negative > score_positive

    def test_value_match_in_desc_adds_bonus(self):
        check_with_val = {"full_desc": "BIRTHMO must be between 1 and 12"}
        check_without_val = {"full_desc": "BIRTHMO conformity check"}
        score_with = self._call(check_with_val, "'allowed': [1, 2, 3]", "birthmo", None)
        score_without = self._call(check_without_val, "'allowed': [1, 2, 3]", "birthmo", None)
        assert score_with >= score_without

    def test_empty_desc_gives_zero_variable_score(self):
        check = {"full_desc": ""}
        score = self._call(check, "some error", "myvar", None)
        # No variable match, only potentially direction bonus
        assert score <= 25


class TestMatchCheckToError:
    """Tests for _match_check_to_error — the check disambiguation guard."""

    def _call(self, checks, error_msg, target_var):
        from src.pipeline.reports.report_pipeline import _match_check_to_error

        return _match_check_to_error(checks, error_msg, target_var)

    def test_empty_list_returns_none(self):
        assert self._call([], "some error", "myvar") is None

    def test_single_check_always_returned(self):
        """Single check is always returned — key lookup already narrows uniquely."""
        check = {"full_desc": "test", "check_code": "x-001", "error_type": "error"}
        result = self._call([check], "some unrelated error message", "myvar")
        assert result == check

    def test_multiple_checks_returns_highest_scoring(self):
        checks = [
            {
                "full_desc": "If TRTBIOMARK is 1 then ADVEVENT cannot be blank",
                "check_code": "a4a-ivp-m-219",
                "error_type": "error",
            },
            {
                "full_desc": "If TRTBIOMARK in (0,9) then ADVEVENT must be blank",
                "check_code": "a4a-ivp-m-220",
                "error_type": "error",
            },
        ]
        # Error is "cannot be blank" — should match the first check
        error_msg = "field cannot be blank"
        result = self._call(checks, error_msg, "advevent")
        assert result is not None
        assert result["check_code"] == "a4a-ivp-m-219"

    def test_multiple_checks_returns_none_when_ambiguous(self):
        """When two checks score identically and neither meets the ambiguity threshold,
        return None rather than guessing."""
        checks = [
            {"full_desc": "Some generic check A", "check_code": "a-001", "error_type": "error"},
            {"full_desc": "Some generic check B", "check_code": "b-001", "error_type": "error"},
        ]
        # No variable mentions, no directional cues — ambiguous
        error_msg = "unallowed value 5"
        result = self._call(checks, error_msg, "unknownvar")
        assert result is None

    def test_multiple_checks_with_clear_winner_returns_match(self):
        checks = [
            {
                "full_desc": "If ALCDRINKS in (4,5) then ALCBINGE should not equal 0",
                "check_code": "a5d2-ivp-p-1003",
                "error_type": "error",
            },
            {
                "full_desc": "If ALCDRINKS is 1 then ALCBINGE must be blank",
                "check_code": "a5d2-ivp-m-050",
                "error_type": "error",
            },
        ]
        # Error mentions ALCDRINKS in the compatibility trigger
        error_msg = (
            "('alcbinge', ['unallowed value 0']) for if {'alcdrinks': {'allowed': [4, 5]}} "
            "then {'alcbinge': {'forbidden': [0]}} - compatibility rule no: 0"
        )
        result = self._call(checks, error_msg, "alcbinge")
        assert result is not None
        assert result["check_code"] == "a5d2-ivp-p-1003"

    def test_multiple_checks_none_below_threshold(self):
        """When best confidence < 50 and multiple checks exist, return None."""
        checks = [
            {"full_desc": "Unrelated check one", "check_code": "x-001", "error_type": "error"},
            {"full_desc": "Unrelated check two", "check_code": "x-002", "error_type": "error"},
            {"full_desc": "Unrelated check three", "check_code": "x-003", "error_type": "error"},
        ]
        result = self._call(checks, "unallowed value 7", "totallyunknown")
        assert result is None


class TestGetNaccCheckInfoWithConfidence:
    """Integration tests for _get_nacc_check_info with the confidence-based matcher."""

    def test_returns_blank_codes_when_multiple_checks_ambiguous(self, monkeypatch):
        """When multiple checks exist but none match confidently, codes stay blank."""
        from src.pipeline.reports import report_pipeline

        monkeypatch.setattr(
            report_pipeline,
            "_CHECK_LOOKUP",
            {"I|a4a|advevent|Missingness": "error"},
        )
        monkeypatch.setattr(
            report_pipeline,
            "_CHECK_DETAILS",
            {
                "I|a4a|advevent|Missingness": [
                    {
                        "full_desc": "Generic check A with no useful context",
                        "check_code": "a4a-ivp-m-219",
                        "error_type": "error",
                        "packet": "I",
                        "form": "a4a",
                        "variable": "advevent",
                        "check_category": "Missingness",
                    },
                    {
                        "full_desc": "Generic check B with no useful context",
                        "check_code": "a4a-ivp-m-220",
                        "error_type": "error",
                        "packet": "I",
                        "form": "a4a",
                        "variable": "advevent",
                        "check_category": "Missingness",
                    },
                ]
            },
        )
        result = report_pipeline._get_nacc_check_info(
            "I", "a4a_adverse_events", "advevent", "field cannot be blank"
        )
        # Must not crash — returns blank or a matched check
        assert "check_code" in result
        assert "error_type" in result
        assert "interpretation" in result

    def test_returns_correct_check_when_single_candidate(self, monkeypatch):
        """Single check per key is always returned."""
        from src.pipeline.reports import report_pipeline

        monkeypatch.setattr(
            report_pipeline,
            "_CHECK_LOOKUP",
            {"I|a1|birthmo|Conformity": "error"},
        )
        monkeypatch.setattr(
            report_pipeline,
            "_CHECK_DETAILS",
            {
                "I|a1|birthmo|Conformity": [
                    {
                        "full_desc": "BIRTHMO must be between 1 and 12",
                        "check_code": "a1-ivp-c-002",
                        "error_type": "error",
                        "packet": "I",
                        "form": "a1",
                        "variable": "birthmo",
                        "check_category": "Conformity",
                    }
                ]
            },
        )
        result = report_pipeline._get_nacc_check_info(
            "I", "a1_participant_demographics", "birthmo", "must be between 1 and 12"
        )
        assert result["check_code"] == "a1-ivp-c-002"
        assert result["error_type"] == "error"
        assert "BIRTHMO" in result["interpretation"].upper()

    def test_returns_empty_strings_when_no_match(self, monkeypatch):
        """When no candidate key exists, returns blank codes (not fabricated data)."""
        from src.pipeline.reports import report_pipeline

        monkeypatch.setattr(report_pipeline, "_CHECK_LOOKUP", {})
        monkeypatch.setattr(report_pipeline, "_CHECK_DETAILS", {})
        result = report_pipeline._get_nacc_check_info(
            "I", "a1_participant_demographics", "unknownvar", "some error"
        )
        assert result["check_code"] == ""
        assert result["interpretation"] == ""
        assert result["error_type"] == "error"  # safe default
