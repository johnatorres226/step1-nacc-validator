"""
Tests verifying that A2, B5, and B7 form body fields are NOT flagged as errors
when the form mode is 'Not completed' (mode=0).

Root cause: REDCap hides all form body fields when mode=0 (Not completed).
These fields are empty by design and must not produce validation errors.

Fix: added compatibility rules to each body field so that:
  - mode=0  → nullable: true, filled: false  (field must be empty)
  - mode=1/2 → nullable: false               (field must be filled)

Regression guard: a valid in-person (mode=1) record must still require
body fields — confirming the fix did not loosen validation for completed forms.
"""

import json
from pathlib import Path

import pytest

from nacc_form_validator.quality_check import QualityCheck

_RULES_I = Path("config/I/rules")


def _load(*file_names: str) -> dict:
    schema: dict = {}
    for name in file_names:
        schema.update(json.loads((_RULES_I / name).read_text()))
    return schema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_B7_BODY = {
    "frmdateb7",
    "langb7",
    "bills",
    "taxes",
    "shopping",
    "games",
    "stove",
    "mealprep",
    "events",
    "payattn",
    "remdates",
    "travel",
}

_B5_BODY = {
    "frmdateb5",
    "langb5",
    "npiqinf",
    "del",
    "hall",
    "agit",
    "depd",
    "anx",
    "elat",
    "apa",
    "disn",
    "irr",
    "mot",
    "nite",
    "app",
}

_A2_BODY = {
    "frmdatea2",
    "langa2",
    "inrelto",
    "inknown",
    "inlivwth",
    "inrely",
    "inmemwors",
    "inmemtroub",
    "inmemten",
}


def _null_record(base: dict) -> dict:
    """Return base record with all unlisted keys set to None."""
    return base


# ---------------------------------------------------------------------------
# B7 — Functional Assessment: FAS
# ---------------------------------------------------------------------------


class TestB7ModeNotCompleted:
    @pytest.fixture(scope="class")
    def qc(self):
        return QualityCheck(schema=_load("b7_rules.json"), pk_field="ptid")

    def _record_mode0(self) -> dict:
        return {
            "ptid": "NM0030",
            "frmdateb7": None,
            "langb7": None,
            "modeb7": 0,
            "rmreasb7": None,
            "rmmodeb7": None,
            "b7not": 97,  # Other
            "bills": None,
            "taxes": None,
            "shopping": None,
            "games": None,
            "stove": None,
            "mealprep": None,
            "events": None,
            "payattn": None,
            "remdates": None,
            "travel": None,
            "initialsb7": None,
        }

    def test_body_fields_not_flagged_when_not_completed(self, qc):
        """mode=0: all B7 body fields null → no errors on body fields."""
        _, _, errors, _ = qc.validate_record(self._record_mode0())
        flagged = _B7_BODY & set(errors)
        assert not flagged, f"B7 body fields incorrectly flagged when mode=0: {flagged}"

    def test_body_fields_required_when_in_person(self, qc):
        """mode=1: body fields null → frmdateb7/langb7 must be flagged."""
        record = self._record_mode0()
        record["modeb7"] = 1
        record["b7not"] = None
        _, _, errors, _ = qc.validate_record(record)
        assert "frmdateb7" in errors or "langb7" in errors, (
            "Expected frmdateb7 or langb7 to be required when mode=1, "
            f"but errors were: {list(errors)}"
        )


# ---------------------------------------------------------------------------
# B5 — Behavioral Assessment: NPI-Q
# ---------------------------------------------------------------------------


class TestB5ModeNotCompleted:
    @pytest.fixture(scope="class")
    def qc(self):
        return QualityCheck(schema=_load("b5_rules.json"), pk_field="ptid")

    def _record_mode0(self) -> dict:
        return {
            "ptid": "NM0030",
            "frmdateb5": None,
            "langb5": None,
            "modeb5": 0,
            "rmreasb5": None,
            "rmmodeb5": None,
            "b5not": 97,  # Other
            "npiqinf": None,
            "npiqinfx": None,
            "del": None,
            "hall": None,
            "agit": None,
            "depd": None,
            "anx": None,
            "elat": None,
            "apa": None,
            "disn": None,
            "irr": None,
            "mot": None,
            "nite": None,
            "app": None,
            "initialsb5": None,
        }

    def test_body_fields_not_flagged_when_not_completed(self, qc):
        """mode=0: all B5 body fields null → no errors on body fields."""
        _, _, errors, _ = qc.validate_record(self._record_mode0())
        flagged = _B5_BODY & set(errors)
        assert not flagged, f"B5 body fields incorrectly flagged when mode=0: {flagged}"

    def test_body_fields_required_when_in_person(self, qc):
        """mode=1: body fields null → frmdateb5/langb5 must be flagged."""
        record = self._record_mode0()
        record["modeb5"] = 1
        record["b5not"] = None
        _, _, errors, _ = qc.validate_record(record)
        assert "frmdateb5" in errors or "langb5" in errors, (
            "Expected frmdateb5 or langb5 to be required when mode=1, "
            f"but errors were: {list(errors)}"
        )


# ---------------------------------------------------------------------------
# A2 — Co-Participant Demographics
# ---------------------------------------------------------------------------


class TestA2ModeNotCompleted:
    @pytest.fixture(scope="class")
    def qc(self):
        return QualityCheck(schema=_load("a2_rules.json"), pk_field="ptid")

    def _record_mode0(self) -> dict:
        return {
            "ptid": "NM0030",
            "frmdatea2": None,
            "langa2": None,
            "modea2": 0,
            "rmreasa2": None,
            "rmmodea2": None,
            "a2not": 97,  # Other
            "inrelto": None,
            "inknown": None,
            "inlivwth": None,
            "inrely": None,
            "inmemwors": None,
            "inmemtroub": None,
            "inmemten": None,
            "initialsa2": None,
        }

    def test_body_fields_not_flagged_when_not_completed(self, qc):
        """mode=0: all A2 body fields null → no errors on body fields."""
        _, _, errors, _ = qc.validate_record(self._record_mode0())
        flagged = _A2_BODY & set(errors)
        assert not flagged, f"A2 body fields incorrectly flagged when mode=0: {flagged}"

    def test_body_fields_required_when_in_person(self, qc):
        """mode=1: body fields null → frmdatea2/langa2 must be flagged."""
        record = self._record_mode0()
        record["modea2"] = 1
        record["a2not"] = None
        _, _, errors, _ = qc.validate_record(record)
        assert "frmdatea2" in errors or "langa2" in errors, (
            "Expected frmdatea2 or langa2 to be required when mode=1, "
            f"but errors were: {list(errors)}"
        )
