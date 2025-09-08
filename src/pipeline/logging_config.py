"""
Enhanced Logging Configuration for UDSv4 QC Validator.

This module provides comprehensive logging infrastructure with:
- Colored terminal output for better CLI experience
- Structured logging for production monitoring
- Performance tracking and metrics
- Context-aware logging with progress tracking
- Flexible configuration for different environments

Features:
- Terminal color support with auto-detection
- Multiple log levels and formatters
- File and console logging
- Progress tracking with context managers
- Performance metrics collection
- Thread-safe logging operations
"""

import json
import logging
import logging.config
import os
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Union


class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support for terminal output."""

    # ANSI color codes for different log levels
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }

    # Icons for different log levels - simplified and professional
    ICONS = {
        'DEBUG': '•',
        'INFO': '▶',
        'WARNING': '⚠',
        'ERROR': '✗',
        'CRITICAL': '✗✗'
    }

    def __init__(
            self,
            fmt=None,
            datefmt=None,
            use_colors: Optional[bool] = None,
            use_icons: bool = True):
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
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False

        # Check for common color-supporting terminals
        term = os.getenv('TERM', '').lower()
        if 'color' in term or 'xterm' in term or 'screen' in term:
            return True

        # Check for Windows terminal color support
        if os.name == 'nt':
            return os.getenv('ANSICON') is not None or 'ON' in os.getenv(
                'ConEmuANSI', 'OFF')

        return False

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
            level_name = record.levelname.split()[-1]  # Get level name without icon
            color = self.COLORS[level_name]
            reset = self.COLORS['RESET']
            record.levelname = f"{color}{record.levelname}{reset}"

        return super().format(record)


class ProductionCLIFormatter(logging.Formatter):
    """Streamlined formatter for production CLI operations with minimal visual clutter."""

    def __init__(self, fmt=None, datefmt=None):
        # Use a clean format for production CLI
        if fmt is None:
            fmt = '%(asctime)s | %(levelname)-7s | %(message)s'
        if datefmt is None:
            datefmt = '%H:%M:%S'
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record):
        """Format with minimal decoration and clean output."""
        # Clean up the message to remove redundant icons and formatting
        message = record.getMessage()

        # Remove excessive emojis and visual clutter
        # Remove common emoji patterns that are overused
        emoji_patterns = [
            '✅ ', '🔄 ', '📋 ', '📊 ', 'ℹ️  ', '⚠️  ',
            '===', '---', '***'
        ]

        for pattern in emoji_patterns:
            if message.startswith(pattern):
                message = message[len(pattern):]
                break

        # Clean up repeated information
        if 'complete' in message.lower() and 'completed' in message.lower():
            # Avoid saying "completed" twice
            message = message.replace('completed', 'done')

        # Create a new record with the cleaned message
        record = logging.makeLogRecord(record.__dict__)
        record.msg = message
        record.args = ()

        return super().format(record)


class PerformanceFilter(logging.Filter):
    """Filter to add performance metrics to log records."""

    def __init__(self):
        super().__init__()
        self.start_time = time.time()

    def filter(self, record):
        """Add performance metrics to the log record."""
        record.elapsed = time.time() - self.start_time
        record.timestamp = datetime.now().isoformat()
        return True


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Union[str, Path]] = None,
    console_output: bool = True,
    structured_logging: bool = False,
    performance_tracking: bool = True,
    max_file_size: str = "10MB",
    backup_count: int = 5
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
        handlers['console'] = {
            'class': 'logging.StreamHandler',
            'level': numeric_level,
            'formatter': 'colored_console',
            'stream': 'ext://sys.stdout'
        }
    else:
        # Add NullHandler when console output is disabled to prevent logs from
        # going to stderr
        handlers['null'] = {
            'class': 'logging.NullHandler',
        }

    # File handler with rotation if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        handlers['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': logging.DEBUG,  # Always debug level for file
            'formatter': 'detailed_file',
            'filename': str(log_path),
            'maxBytes': _parse_file_size(max_file_size),
            'backupCount': backup_count,
            'encoding': 'utf-8'
        }

    # Structured JSON file handler if requested
    if structured_logging and log_file:
        json_log_path = Path(str(log_file).replace('.log', '_structured.jsonl'))
        handlers['json_file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': logging.DEBUG,
            'formatter': 'json_structured',
            'filename': str(json_log_path),
            'maxBytes': _parse_file_size(max_file_size),
            'backupCount': backup_count,
            'encoding': 'utf-8'
        }

    # Configure formatters
    formatters = {
        'colored_console': {
            '()': ColoredFormatter,
            'format': '%(asctime)s | %(levelname)-7s | %(message)s',
            'datefmt': '%H:%M:%S',
            'use_colors': True,
            'use_icons': False  # Disable icons to reduce clutter
        },
        'detailed_file': {
            'format': '%(asctime)s | %(levelname)-8s | %(name)-20s | %(filename)s:%(lineno)d | %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'json_structured': {
            'format': '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '%(levelname)s: %(message)s'
        }
    }

    # Configure filters - simplified for compatibility
    filters = {}

    # Build logging configuration
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': formatters,
        'handlers': handlers,
        'root': {
            'level': logging.DEBUG,
            'handlers': list(handlers.keys())
        },
        'loggers': {
            '': {
                'handlers': list(handlers.keys()),
                'level': 'INFO',
                'propagate': True,
            },
            'pipeline': {
                'handlers': list(handlers.keys()),
                'level': 'INFO',
                'propagate': False,
            },
            # Suppress noisy third-party loggers
            'urllib3': {
                'level': logging.WARNING
            },
            'requests': {
                'level': logging.WARNING
            }
        }
    }

    # Add filters to handlers if configured
    if filters:
        for handler_name in handlers:
            if handler_name not in [
                    'console']:  # Don't add performance filter to console
                handlers[handler_name]['filters'] = list(filters.keys())
        logging_config['filters'] = filters

    # Apply configuration
    logging.config.dictConfig(logging_config)


class JSONFormatter(logging.Formatter):
    """Formatter for structured JSON logging."""

    def format(self, record):
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        # Add performance metrics if available
        if hasattr(record, 'elapsed'):
            log_entry['elapsed_time'] = getattr(record, 'elapsed')

        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                           'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                           'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                           'thread', 'threadName', 'processName', 'process', 'message']:
                log_entry[key] = value

        return json.dumps(log_entry)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger instance with the specified name, configured under the 'pipeline' namespace.
    """
    return logging.getLogger(f"pipeline.{name}")


class QCLogger:
    """Context manager for QC operations with progress tracking."""

    def __init__(self, operation_name: str, logger: Optional[logging.Logger] = None):
        self.operation_name = operation_name
        self.logger = logger or get_logger('qc_operation')
        self.start_time = None
        self.steps_completed = 0
        self.total_steps = None
        self._lock = threading.Lock()

    def __enter__(self):
        """Start the operation logging."""
        self.start_time = time.time()
        if self.operation_name in [
            'Configuration Check',
            'Environment Setup',
                'QC Pipeline']:
            self.logger.info(f"Starting operation: {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Complete the operation logging."""
        if self.start_time is not None:
            duration = time.time() - self.start_time

            if exc_type is None:
                if self.operation_name in [
                    'Configuration Check',
                    'Environment Setup',
                        'QC Pipeline']:
                    self.logger.info(f"Completed operation: {self.operation_name} "
                                     f"(Duration: {duration:.2f}s)")
            else:
                self.logger.error(f"Failed operation: {self.operation_name} "
                                  f"(Duration: {duration:.2f}s) - {exc_val}")

        return False  # Don't suppress exceptions

    def log_progress(self, message: str, step: Optional[int] = None):
        """Log progress update with optional step tracking."""
        # Only log progress for high-level operations
        if self.operation_name in [
            'Configuration Check',
            'Environment Setup',
                'QC Pipeline']:
            with self._lock:
                if step is not None:
                    self.steps_completed = step
                else:
                    self.steps_completed += 1

                if self.total_steps:
                    progress = (self.steps_completed / self.total_steps) * 100
                    self.logger.info(f"{self.operation_name}: {message} "
                                     f"({self.steps_completed}/{self.total_steps} - {progress:.1f}%)")
                else:
                    self.logger.info(f"{self.operation_name}: {message}")

    def set_total_steps(self, total: int):
        """Set the total number of steps for progress tracking."""
        with self._lock:
            self.total_steps = total

    def log_error(self, message: str, exception: Optional[Exception] = None):
        """Log an error during the operation."""
        if exception:
            self.logger.error(f"{self.operation_name} Error: {message} - {exception}")
            self.logger.debug(
                f"Full traceback for {
                    self.operation_name}",
                exc_info=True)
        else:
            self.logger.error(f"{self.operation_name} Error: {message}")

    def log_warning(self, message: str):
        """Log a warning during the operation."""
        self.logger.warning(f"{self.operation_name} Warning: {message}")


def _parse_file_size(size_str: str) -> int:
    """Parse file size string like '10MB' to bytes."""
    size_str = size_str.upper()

    if size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    else:
        return int(size_str)


@contextmanager
def log_performance(operation_name: str, logger: Optional[logging.Logger] = None):
    """Context manager for logging operation performance."""
    if logger is None:
        logger = get_logger('performance')

    start_time = time.time()

    try:
        yield
        duration = time.time() - start_time
        if duration > 1.0:  # Only log operations that take longer than 1 second
            logger.info(f"Completed {operation_name} in {duration:.2f}s")
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Failed {operation_name} after {duration:.2f}s: {e}")
        raise


def log_dataframe_info(df, name: str, logger: Optional[logging.Logger] = None):
    """Log information about a pandas DataFrame."""
    if logger is None:
        logger = get_logger('data')

    # Only log if dataframe is large or in debug mode
    if len(df) > 1000 or logger.isEnabledFor(logging.DEBUG):
        logger.info(f"DataFrame '{name}': {len(df)} rows, {len(df.columns)} columns")

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"DataFrame '{name}' columns: {list(df.columns)}")
        logger.debug(
            f"DataFrame '{name}' memory usage: {
                df.memory_usage(
                    deep=True).sum() /
                1024 /
                1024:.2f} MB")


def configure_third_party_logging():
    """Configure logging for third-party libraries to reduce noise."""
    # Reduce logging level for common noisy libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)


# Initialize basic logging on import
if not logging.getLogger("pipeline").handlers:
    setup_logging()

# Configure third-party logging
configure_third_party_logging()
