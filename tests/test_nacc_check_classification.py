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
