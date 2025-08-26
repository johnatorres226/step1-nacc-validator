#!/usr/bin/env python3
"""Test for compatibility rule fix to handle null/missing fields"""

import pytest
from nacc_form_validator.nacc_validator import NACCValidator
from nacc_form_validator.errors import CustomErrorHandler


class TestCompatibilityRuleNullFields:
    """Test compatibility rules with null/missing fields"""
    
    def test_compatibility_rule_with_null_reference_field(self):
        """Test that compatibility rules don't trigger when referenced field is null"""
        
        schema = {
            'seizures': {
                'required': True,
                'type': 'integer',
                'allowed': [0, 1, 2, 9],
                'compatibility': [
                    {
                        'index': 0,
                        'if': {
                            'epilep': {
                                'allowed': [1]
                            }
                        },
                        'then': {
                            'seizures': {
                                'allowed': [1]
                            }
                        }
                    }
                ]
            },
            'epilep': {
                'nullable': True,
                'type': 'integer',
                'allowed': [0, 1]
            }
        }
        
        # Test with epilep = None (null)
        record = {
            'seizures': 0,
            'epilep': None
        }
        
        validator = NACCValidator(schema, error_handler=CustomErrorHandler(schema))
        result = validator.validate(record)
        
        # Should pass because epilep is null, so the if condition is not met
        assert result, f"Validation should pass when epilep is null, but got errors: {validator.errors}"
    
    def test_compatibility_rule_with_missing_reference_field(self):
        """Test that compatibility rules don't trigger when referenced field is missing"""
        
        schema = {
            'seizures': {
                'required': True,
                'type': 'integer',
                'allowed': [0, 1, 2, 9],
                'compatibility': [
                    {
                        'index': 0,
                        'if': {
                            'epilep': {
                                'allowed': [1]
                            }
                        },
                        'then': {
                            'seizures': {
                                'allowed': [1]
                            }
                        }
                    }
                ]
            },
            'epilep': {
                'nullable': True,
                'type': 'integer',
                'allowed': [0, 1]
            }
        }
        
        # Test with epilep missing completely
        record = {
            'seizures': 0
        }
        
        validator = NACCValidator(schema, error_handler=CustomErrorHandler(schema))
        result = validator.validate(record)
        
        # Should pass because epilep is missing, so the if condition is not met
        assert result, f"Validation should pass when epilep is missing, but got errors: {validator.errors}"
    
    def test_compatibility_rule_triggers_when_condition_met(self):
        """Test that compatibility rules still trigger when condition is met"""
        
        schema = {
            'seizures': {
                'required': True,
                'type': 'integer',
                'allowed': [0, 1, 2, 9],
                'compatibility': [
                    {
                        'index': 0,
                        'if': {
                            'epilep': {
                                'allowed': [1]
                            }
                        },
                        'then': {
                            'seizures': {
                                'allowed': [1]
                            }
                        }
                    }
                ]
            },
            'epilep': {
                'nullable': True,
                'type': 'integer',
                'allowed': [0, 1]
            }
        }
        
        # Test with epilep = 1 but seizures = 0 (should fail)
        record = {
            'seizures': 0,
            'epilep': 1
        }
        
        validator = NACCValidator(schema, error_handler=CustomErrorHandler(schema))
        result = validator.validate(record)
        
        # Should fail because epilep = 1 and seizures = 0 (should be 1)
        assert not result, "Validation should fail when epilep=1 and seizures=0"
        assert 'seizures' in validator.errors, "Should have seizures error"
    
    def test_compatibility_rule_passes_when_condition_and_result_match(self):
        """Test that compatibility rules pass when both condition and result are correct"""
        
        schema = {
            'seizures': {
                'required': True,
                'type': 'integer',
                'allowed': [0, 1, 2, 9],
                'compatibility': [
                    {
                        'index': 0,
                        'if': {
                            'epilep': {
                                'allowed': [1]
                            }
                        },
                        'then': {
                            'seizures': {
                                'allowed': [1]
                            }
                        }
                    }
                ]
            },
            'epilep': {
                'nullable': True,
                'type': 'integer',
                'allowed': [0, 1]
            }
        }
        
        # Test with epilep = 1 and seizures = 1 (should pass)
        record = {
            'seizures': 1,
            'epilep': 1
        }
        
        validator = NACCValidator(schema, error_handler=CustomErrorHandler(schema))
        result = validator.validate(record)
        
        # Should pass because epilep = 1 and seizures = 1 (matches the then condition)
        assert result, f"Validation should pass when epilep=1 and seizures=1, but got errors: {validator.errors}"
    
    def test_a5d2_specific_compatibility_issues(self):
        """Test the specific a5d2 compatibility issues mentioned in the bug report"""
        
        schema = {
            'seizures': {
                'required': True,
                'type': 'integer',
                'allowed': [0, 1, 2, 9],
                'compatibility': [
                    {
                        'index': 0,
                        'if': {
                            'epilep': {
                                'allowed': [1]
                            }
                        },
                        'then': {
                            'seizures': {
                                'allowed': [1]
                            }
                        }
                    }
                ]
            },
            'hydroceph': {
                'required': True,
                'type': 'integer',
                'allowed': [0, 1, 2, 9],
                'compatibility': [
                    {
                        'index': 0,
                        'if': {
                            'hyceph': {
                                'allowed': [1]
                            }
                        },
                        'then': {
                            'hydroceph': {
                                'allowed': [1]
                            }
                        }
                    }
                ]
            },
            'epilep': {
                'nullable': True,
                'type': 'integer',
                'allowed': [0, 1]
            },
            'hyceph': {
                'nullable': True,
                'type': 'integer',
                'allowed': [0, 1]
            }
        }
        
        # Test the exact scenario from the bug report: epilep and hyceph are null
        record = {
            'seizures': 0,
            'hydroceph': 0,
            'epilep': None,
            'hyceph': None
        }
        
        validator = NACCValidator(schema, error_handler=CustomErrorHandler(schema))
        result = validator.validate(record)
        
        # Should pass because epilep and hyceph are null, so the if conditions are not met
        assert result, f"Validation should pass when epilep and hyceph are null, but got errors: {validator.errors}"
        
        # Verify no errors are reported
        assert not validator.errors, f"Expected no errors but got: {validator.errors}"
