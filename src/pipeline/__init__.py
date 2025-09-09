"""
This __init__.py file makes the `src/pipeline` directory a Python package.

It also initializes the logging configuration for the entire pipeline.
"""

from . import logging_config


logging_config.setup_logging()
