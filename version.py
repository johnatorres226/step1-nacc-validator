"""
Centralized version management for UDSv4 REDCap QC Validator.

This module provides a single source of truth for the package version.
All version references should import from this module.

Usage:
    from version import __version__
    print(__version__)
"""

__version__ = "0.1.0"
__version_info__ = tuple(int(x) for x in __version__.split("."))

# Semantic versioning components
VERSION_MAJOR = __version_info__[0]
VERSION_MINOR = __version_info__[1]
VERSION_PATCH = __version_info__[2]
