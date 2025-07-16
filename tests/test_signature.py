#!/usr/bin/env python3
"""Test script to verify the function signature."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pipeline.report_pipeline import run_report_pipeline
import inspect

# Get the function signature
sig = inspect.signature(run_report_pipeline)
print(f"Function signature: {sig}")

# Check parameters
for param_name, param in sig.parameters.items():
    print(f"Parameter: {param_name}, Type: {param.annotation}, Default: {param.default}")
