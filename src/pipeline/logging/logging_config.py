"""
Enhanced Logging Configuration for UDSv4 QC Validator.

This module provides comprehensive logging infrastructure including:
- Colored terminal output for improved CLI experience
- Structured JSON logging for production monitoring
- Performance tracking and metrics
- Context-aware progress tracking utilities
- Flexible configuration for different environments

The implementations are intentionally lightweight and compatible with the
project's logging configuration used across the pipeline.
"""

import logging
import logging.config
import os
import sys
from pathlib import Path
from typing import ClassVar


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for terminal output."""

    # ANSI color codes mapped to UNM brand palette
    # Reference: https://brand.unm.edu/brand-style/color-palette/index.html
    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[38;2;99;102;106m",      # UNM Lobo Gray
        "INFO": "\033[38;2;0;122;134m",        # UNM Turquoise
        "WARNING": "\033[38;2;255;198;0m",     # UNM High Noon
        "ERROR": "\033[38;2;186;12;47m",       # UNM Cherry
        "CRITICAL": "\033[1;38;2;186;12;47m",  # Bold UNM Cherry
        "RESET": "\033[0m",
    }

    # Icons for different log levels - simplified and professional
    ICONS: ClassVar[dict[str, str]] = {
        "DEBUG": "•",
        "INFO": "▶",
        "WARNING": "⚠",
        "ERROR": "✗",
        "CRITICAL": "✗✗",
    }

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        *,
        use_colors: bool | None = None,
        use_icons: bool = True,
    ) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)
        # Auto-detect color support if not specified
        if use_colors is None:
            self.use_colors = self._supports_color()
        else:
            self.use_colors = use_colors
        self.use_icons = use_icons

    def _supports_color(self) -> bool:
        """Check if the terminal supports color output."""
        # Check if we're in a terminal and not redirected
        if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
            return False

        # Check for common color-supporting terminals
        term = os.getenv("TERM", "").lower()
        if "color" in term or "xterm" in term or "screen" in term:
            return True

        # Check for Windows terminal color support
        if os.name == "nt":
            # Windows 10+ terminals (Windows Terminal, VS Code, PowerShell 7+)
            # support ANSI colors when running in a TTY
            return True

        return True  # Assume color support for TTY sessions

    def format(self, record):
        """Format log record with colors and icons."""
        # Create a copy of the record to avoid modifying the original
        record = logging.makeLogRecord(record.__dict__)

        # Add icon if enabled
        if self.use_icons and record.levelname in self.ICONS:
            icon = self.ICONS[record.levelname]
            record.levelname = f"{icon} {record.levelname}"

        # Add color if enabled
        if self.use_colors and record.levelname.split()[-1] in self.COLORS:
            # Get level name without icon
            level_name = record.levelname.split()[-1]
            color = self.COLORS[level_name]
            reset = self.COLORS["RESET"]
            record.levelname = f"{color}{record.levelname}{reset}"

        return super().format(record)


def setup_logging(
    log_level: str = "INFO",
    log_file: str | Path | None = None,
    *,
    console_output: bool = True,
    structured_logging: bool = False,
    performance_tracking: bool = True,
    max_file_size: str = "10MB",
    backup_count: int = 5,
) -> None:
    """
    Configure comprehensive logging for the QC pipeline.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file to write logs to
        console_output: Enable console logging
        structured_logging: Enable structured JSON logging
        performance_tracking: Enable performance metrics
        max_file_size: Maximum size for log files before rotation
        backup_count: Number of backup log files to keep
    """

    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure handlers
    handlers = {}

    # Console handler with colored output
    if console_output:
        handlers["console"] = {
            "class": "logging.StreamHandler",
            "level": numeric_level,
            "formatter": "colored_console",
            "stream": "ext://sys.stdout",
        }
    else:
        # Add NullHandler when console output is disabled to prevent logs from
        # going to stderr
        handlers["null"] = {
            "class": "logging.NullHandler",
        }

    # File handler with rotation if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": logging.DEBUG,  # Always debug level for file
            "formatter": "detailed_file",
            "filename": str(log_path),
            "maxBytes": _parse_file_size(max_file_size),
            "backupCount": backup_count,
            "encoding": "utf-8",
        }

    # Structured JSON file handler if requested
    if structured_logging and log_file:
        json_log_path = Path(str(log_file).replace(".log", "_structured.jsonl"))
        handlers["json_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": logging.DEBUG,
            "formatter": "json_structured",
            "filename": str(json_log_path),
            "maxBytes": _parse_file_size(max_file_size),
            "backupCount": backup_count,
            "encoding": "utf-8",
        }

    # Configure formatters
    formatters = {
        "colored_console": {
            "()": ColoredFormatter,
            "format": "%(asctime)s | %(levelname)-7s | %(message)s",
            "datefmt": "%H:%M:%S",
            "use_colors": True,
            "use_icons": False,  # Disable icons to reduce clutter
        },
        "detailed_file": {
            "format": (
                "%(asctime)s | %(levelname)-8s | %(name)-20s | "
                "%(filename)s:%(lineno)d | %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "json_structured": {
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {"format": "%(levelname)s: %(message)s"},
    }

    # Configure filters - simplified for compatibility
    filters: dict[str, dict] = {}

    # Build logging configuration
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "root": {"level": logging.DEBUG, "handlers": list(handlers.keys())},
        "loggers": {
            "": {
                "handlers": list(handlers.keys()),
                "level": "INFO",
                "propagate": True,
            },
            "pipeline": {
                "handlers": list(handlers.keys()),
                "level": "INFO",
                "propagate": False,
            },
            # Suppress noisy third-party loggers
            "urllib3": {"level": logging.WARNING},
            "requests": {"level": logging.WARNING},
        },
    }

    # Add filters to handlers if configured
    if filters:
        for handler_name in handlers:
            if handler_name not in ["console"]:  # Don't add performance filter to console
                handlers[handler_name]["filters"] = list(filters.keys())
        logging_config["filters"] = filters

    # Apply configuration
    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance with the specified name, configured under the 'pipeline' namespace.
    """
    return logging.getLogger(f"pipeline.{name}")


def _parse_file_size(size_str: str) -> int:
    """Parse file size string like '10MB' to bytes."""
    size_str = size_str.upper()

    if size_str.endswith("KB"):
        return int(size_str[:-2]) * 1024
    if size_str.endswith("MB"):
        return int(size_str[:-2]) * 1024 * 1024
    if size_str.endswith("GB"):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    return int(size_str)


def configure_third_party_logging():
    """Configure logging for third-party libraries to reduce noise."""
    # Reduce logging level for common noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)


# Initialize basic logging on import
if not logging.getLogger("pipeline").handlers:
    setup_logging()

# Configure third-party logging
configure_third_party_logging()
