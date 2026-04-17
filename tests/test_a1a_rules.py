"""
Test suite for A1A SDOH rules — validates required:true + nullable:true pattern.

The a1a rules use required:true + nullable:true on all survey fields.
modea1a is the only field intentionally kept without nullable (always required).
Cross-form compatibility rules (e.g. childcomm) are validated separately.
"""

import json
from pathlib import Path

import pytest


class TestA1ARulesNullabilityPattern:
    """
    Test that a1a survey fields use the required:true + nullable:true pattern.

    The refactored rules replaced the old conditional a1anot-based nullability
    (nullable:true + compatibility rule forcing nullable:false when a1anot!=93)
    with a simpler required:true + nullable:true on every survey field.
    modea1a is intentionally excluded from nullable since it must always be filled.
    """

    # Fields intentionally excluded from nullable:true
    # modea1a must always be present and non-null (form mode indicator)
    NON_NULLABLE_FIELDS = {"modea1a"}

    # Fields with their own nullability logic — not plain survey fields
    # exp* fields are optional indicator checkboxes (allowed: [1] | null) and are
    # intentionally not required; respondents may leave all blank.
    SKIP_FIELDS = {
        "rmreasa1a",
        "rmmodea1a",
        "a1anot",
        "initialsa1a",
        "expancest",
        "expgender",
        "exprace",
        "expage",
        "exprelig",
        "expheight",
        "expweight",
        "expappear",
        "expsexorn",
        "expeducinc",
        "expdisab",
        "expskin",
        "expother",
        "expnotapp",
        "expnoans",
        "expstrs",
    }

    PACKETS = ["I", "I4", "F"]

    @pytest.fixture
    def config_base_path(self):
        return Path(__file__).parent.parent / "config"

    def load_a1a_rules(self, config_base_path: Path, packet: str) -> dict:
        rules_path = config_base_path / packet / "rules" / "a1a_rules.json"
        assert rules_path.exists(), f"Rules file not found: {rules_path}"
        with open(rules_path, "r") as f:
            return json.load(f)

    @pytest.mark.parametrize("packet", PACKETS)
    def test_survey_fields_are_required(self, config_base_path, packet):
        """All survey fields must have required:true."""
        rules = self.load_a1a_rules(config_base_path, packet)
        missing = [
            name
            for name, defn in rules.items()
            if name not in self.SKIP_FIELDS
            and isinstance(defn, dict)
            and defn.get("required") is not True
        ]
        assert not missing, f"Packet {packet}: survey fields missing required:true: {missing}"

    @pytest.mark.parametrize("packet", PACKETS)
    def test_survey_fields_are_nullable(self, config_base_path, packet):
        """All survey fields except modea1a must have nullable:true."""
        rules = self.load_a1a_rules(config_base_path, packet)
        missing = [
            name
            for name, defn in rules.items()
            if name not in self.NON_NULLABLE_FIELDS
            and name not in self.SKIP_FIELDS
            and isinstance(defn, dict)
            and defn.get("nullable") is not True
        ]
        assert not missing, f"Packet {packet}: survey fields missing nullable:true: {missing}"

    @pytest.mark.parametrize("packet", PACKETS)
    def test_modea1a_is_not_nullable(self, config_base_path, packet):
        """modea1a must NOT have nullable:true — it is always required."""
        rules = self.load_a1a_rules(config_base_path, packet)
        assert "modea1a" in rules, f"Packet {packet}: modea1a not found"
        assert rules["modea1a"].get("nullable") is not True, (
            f"Packet {packet}: modea1a should not be nullable"
        )

    @pytest.mark.parametrize("packet", PACKETS)
    def test_admina1a_is_required_and_nullable(self, config_base_path, packet):
        """admina1a must have both required:true and nullable:true."""
        rules = self.load_a1a_rules(config_base_path, packet)
        assert "admina1a" in rules, f"Packet {packet}: admina1a not found"
        defn = rules["admina1a"]
        assert defn.get("required") is True, f"Packet {packet}: admina1a missing required:true"
        assert defn.get("nullable") is True, f"Packet {packet}: admina1a missing nullable:true"

    @pytest.mark.parametrize("packet", PACKETS)
    def test_childcomm_has_cross_form_compatibility(self, config_base_path, packet):
        """childcomm must have the cross-form compatibility rule (a1a-p-1002)."""
        rules = self.load_a1a_rules(config_base_path, packet)
        assert "childcomm" in rules, f"Packet {packet}: childcomm not found"
        compat = rules["childcomm"].get("compatibility", [])
        cross_form_rules = [
            r for r in compat if isinstance(r, dict) and "modea2" in r.get("if", {})
        ]
        assert cross_form_rules, (
            f"Packet {packet}: childcomm missing cross-form compatibility rule "
            f"(modea2/inrelto/incntfrq conditions for a1a-p-1002)"
        )


class TestA1ARulesStructure:
    """Test the overall structure of a1a_rules.json files."""

    @pytest.mark.parametrize("packet", ["I", "I4", "F"])
    def test_a1a_rules_file_exists(self, packet):
        """Test that a1a_rules.json exists for each packet."""
        config_path = Path(__file__).parent.parent / "config" / packet / "rules" / "a1a_rules.json"
        assert config_path.exists(), f"a1a_rules.json not found for packet {packet}"

    @pytest.mark.parametrize("packet", ["I", "I4", "F"])
    def test_a1a_rules_valid_json(self, packet):
        """Test that a1a_rules.json contains valid JSON."""
        config_path = Path(__file__).parent.parent / "config" / packet / "rules" / "a1a_rules.json"

        with open(config_path, "r") as f:
            try:
                rules = json.load(f)
                assert isinstance(rules, dict), "Rules should be a dictionary"
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {packet}/a1a_rules.json: {e}")

    @pytest.mark.parametrize("packet", ["I", "I4", "F"])
    def test_compatibility_rules_have_indices(self, packet):
        """Test that all compatibility rules have proper index values."""
        config_path = Path(__file__).parent.parent / "config" / packet / "rules" / "a1a_rules.json"

        with open(config_path, "r") as f:
            rules = json.load(f)

        for field_name, field_rules in rules.items():
            if not isinstance(field_rules, dict):
                continue

            compatibility = field_rules.get("compatibility", [])
            if not compatibility:
                continue

            # Check that indices are sequential starting from 0
            for idx, rule in enumerate(compatibility):
                if not isinstance(rule, dict):
                    continue

                assert "index" in rule, (
                    f"Packet {packet}, field {field_name}: "
                    f"Compatibility rule at position {idx} missing 'index' key"
                )

                assert rule["index"] == idx, (
                    f"Packet {packet}, field {field_name}: "
                    f"Compatibility rule has index {rule['index']} but should be {idx}"
                )
