"""
Test suite for A1A SDOH rules to ensure a1anot=93 compatibility rules are present.

This test ensures that all data fields in a1a_rules.json have the proper
compatibility rule to allow null values when a1anot=93.
"""

import json
from pathlib import Path

import pytest


class TestA1ARulesA1AnotCompatibility:
    """Test that a1anot=93 compatibility rules are present in all a1a_rules.json files."""

    # System fields that should NOT have the a1anot=93 rule
    SYSTEM_FIELDS = {
        'frmdatea1a',
        'langa1a',
        'modea1a',
        'rmreasa1a',
        'rmmodea1a',
        'a1anot',
        'initialsa1a'
    }

    # Packets to test
    PACKETS = ['I', 'I4', 'F']

    @pytest.fixture
    def config_base_path(self):
        """Get the base path to config directory."""
        return Path(__file__).parent.parent / 'config'

    def load_a1a_rules(self, config_base_path: Path, packet: str) -> dict:
        """Load a1a_rules.json for a specific packet."""
        rules_path = config_base_path / packet / 'rules' / 'a1a_rules.json'
        assert rules_path.exists(), f"Rules file not found: {rules_path}"
        
        with open(rules_path, 'r') as f:
            return json.load(f)

    def has_a1anot_forbidden_rule(self, field_rules: dict, field_name: str) -> bool:
        """
        Check if a field has the correct a1anot compatibility rule.
        
        The rule should:
        1. Be in the compatibility array
        2. Have 'if' condition with 'a1anot': {'forbidden': [93]}
        3. Have 'then' condition making the field nullable: false
        """
        if not isinstance(field_rules, dict):
            return False
            
        compatibility = field_rules.get('compatibility', [])
        
        for rule in compatibility:
            if not isinstance(rule, dict):
                continue
                
            # Check if this is an a1anot forbidden rule
            if_clause = rule.get('if', {})
            if 'a1anot' not in if_clause:
                continue
                
            a1anot_condition = if_clause['a1anot']
            if 'forbidden' in a1anot_condition and 93 in a1anot_condition['forbidden']:
                # Verify the then clause
                then_clause = rule.get('then', {})
                field_constraint = then_clause.get(field_name, {})
                if field_constraint.get('nullable') is False:
                    return True
                    
        return False

    @pytest.mark.parametrize('packet', PACKETS)
    def test_data_fields_have_a1anot_rule(self, config_base_path, packet):
        """Test that all data fields (non-system fields) have a1anot=93 compatibility rule."""
        rules = self.load_a1a_rules(config_base_path, packet)
        
        missing_rule_fields = []
        
        for field_name, field_rules in rules.items():
            # Skip system fields
            if field_name in self.SYSTEM_FIELDS:
                continue
                
            # Skip if not a dict (shouldn't happen, but be safe)
            if not isinstance(field_rules, dict):
                continue
            
            # Check if field has the a1anot forbidden rule
            if not self.has_a1anot_forbidden_rule(field_rules, field_name):
                missing_rule_fields.append(field_name)
        
        assert not missing_rule_fields, (
            f"Packet {packet}: The following fields are missing the a1anot=93 compatibility rule: "
            f"{', '.join(missing_rule_fields)}"
        )

    @pytest.mark.parametrize('packet', PACKETS)
    def test_data_fields_are_nullable_by_default(self, config_base_path, packet):
        """Test that all data fields are nullable by default (to allow null when a1anot=93)."""
        rules = self.load_a1a_rules(config_base_path, packet)
        
        non_nullable_fields = []
        
        for field_name, field_rules in rules.items():
            # Skip system fields
            if field_name in self.SYSTEM_FIELDS:
                continue
                
            # Skip if not a dict
            if not isinstance(field_rules, dict):
                continue
            
            # Check if field is nullable at base level
            if field_rules.get('nullable') is not True:
                non_nullable_fields.append(field_name)
        
        assert not non_nullable_fields, (
            f"Packet {packet}: The following fields should be nullable by default: "
            f"{', '.join(non_nullable_fields)}"
        )

    @pytest.mark.parametrize('packet', PACKETS)
    def test_system_fields_remain_required(self, config_base_path, packet):
        """Test that system fields remain required regardless of a1anot value."""
        rules = self.load_a1a_rules(config_base_path, packet)
        
        for field_name in self.SYSTEM_FIELDS:
            if field_name not in rules:
                continue  # Some system fields may not exist in all packets
                
            field_rules = rules[field_name]
            if not isinstance(field_rules, dict):
                continue
            
            # System fields should either:
            # 1. Have required: true, OR
            # 2. Have their own specific compatibility rules (like rmreasa1a, rmmodea1a)
            # They should NOT have the a1anot=93 rule
            
            has_a1anot_rule = self.has_a1anot_forbidden_rule(field_rules, field_name)
            
            assert not has_a1anot_rule, (
                f"Packet {packet}: System field '{field_name}' should NOT have "
                f"a1anot=93 compatibility rule as it must always be filled"
            )

    @pytest.mark.parametrize('packet', PACKETS)
    def test_admina1a_has_a1anot_rule(self, config_base_path, packet):
        """
        Test that admina1a specifically has the a1anot=93 rule.
        
        This is a special case as admina1a was initially excluded but should
        actually allow null when a1anot=93.
        """
        rules = self.load_a1a_rules(config_base_path, packet)
        
        assert 'admina1a' in rules, f"Packet {packet}: admina1a field not found"
        
        admina1a_rules = rules['admina1a']
        has_rule = self.has_a1anot_forbidden_rule(admina1a_rules, 'admina1a')
        
        assert has_rule, (
            f"Packet {packet}: admina1a must have a1anot=93 compatibility rule "
            f"to allow null when form is not completed"
        )
        
        # Also verify it's nullable by default (should be True to allow null when a1anot=93)
        assert admina1a_rules.get('nullable') is True, (
            f"Packet {packet}: admina1a should be nullable=true by default to allow null when a1anot=93"
        )


class TestA1ARulesStructure:
    """Test the overall structure of a1a_rules.json files."""

    @pytest.mark.parametrize('packet', ['I', 'I4', 'F'])
    def test_a1a_rules_file_exists(self, packet):
        """Test that a1a_rules.json exists for each packet."""
        config_path = Path(__file__).parent.parent / 'config' / packet / 'rules' / 'a1a_rules.json'
        assert config_path.exists(), f"a1a_rules.json not found for packet {packet}"

    @pytest.mark.parametrize('packet', ['I', 'I4', 'F'])
    def test_a1a_rules_valid_json(self, packet):
        """Test that a1a_rules.json contains valid JSON."""
        config_path = Path(__file__).parent.parent / 'config' / packet / 'rules' / 'a1a_rules.json'
        
        with open(config_path, 'r') as f:
            try:
                rules = json.load(f)
                assert isinstance(rules, dict), "Rules should be a dictionary"
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {packet}/a1a_rules.json: {e}")

    @pytest.mark.parametrize('packet', ['I', 'I4', 'F'])
    def test_compatibility_rules_have_indices(self, packet):
        """Test that all compatibility rules have proper index values."""
        config_path = Path(__file__).parent.parent / 'config' / packet / 'rules' / 'a1a_rules.json'
        
        with open(config_path, 'r') as f:
            rules = json.load(f)
        
        for field_name, field_rules in rules.items():
            if not isinstance(field_rules, dict):
                continue
                
            compatibility = field_rules.get('compatibility', [])
            if not compatibility:
                continue
            
            # Check that indices are sequential starting from 0
            for idx, rule in enumerate(compatibility):
                if not isinstance(rule, dict):
                    continue
                    
                assert 'index' in rule, (
                    f"Packet {packet}, field {field_name}: "
                    f"Compatibility rule at position {idx} missing 'index' key"
                )
                
                assert rule['index'] == idx, (
                    f"Packet {packet}, field {field_name}: "
                    f"Compatibility rule has index {rule['index']} but should be {idx}"
                )
