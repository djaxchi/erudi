"""Structured logging configuration with console and file output.

This module provides a centralized logging system with:
- Color-coded console output for development.
- Rotating file handlers to prevent log bloat.
- Customizable formatters with pathname shortening.
- Singleton logger instance for application-wide use.

Log Levels:
    - DEBUG: Internal diagnostics (token generation, model loading steps).
    - INFO: Lifecycle transitions (startup, shutdown, model switched).
    - WARNING: Recoverable issues (fallback to CPU, missing KB).
    - ERROR: Operation failures (model not found, CUDA OOM).
    - CRITICAL: System failures (database corruption, engine crash).

Log Format:
    Console::

        [INFO]  2025-10-24 14:32:10 - erudi - backend/src/main.py:app:l42 - Server started

    File::

        [INFO] 2025-10-24 14:32:10 - erudi - main.py:42 - Server started

File Management:
    - Logs written to the runtime log directory configured by
      ``src.launcher.runtime_paths`` (typically ``backend/logs`` in dev).
    - Rotation: 10 MB max file size.
    - Retention: 10 backup files (logs.1, logs.2, ...).
    - Encoding: UTF-8 for multilingual support.

Example:
    Use the global logger instance::

        from src.core.logging import logger

        logger.debug("Loading model weights...")
        logger.info("Model successfully loaded")
        logger.warning("GPU memory low, reducing batch size")
        logger.error("Failed to load model", exc_info=True)

    Create a custom logger for a specific module::

        from src.core.logging import get_logger

        module_logger = get_logger("erudi.domains.llms")
        module_logger.info("LLM service initialized")

Note:
    The logger is configured as a singleton. Repeated calls to get_logger()
    with the same name will return the existing logger instance.

Warning:
    Never log sensitive data (HF tokens, user prompts, file paths with PII).
    Use structured logging: logger.info("Model loaded", extra={"model_id": 123})
"""

import logging, sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

from src.launcher import ensure_runtime_paths_initialized

# ----------------------------
# Formatter
# ----------------------------
class CustomFormatter(logging.Formatter):
    """Custom formatter to add colors for console output and shorten pathname."""

    grey = "\x1b[38;21m"
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    blue = "\x1b[34;21m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: blue + "[DEBUG] %(asctime)s - %(name)s - %(pathname)s:%(funcName)s:l%(lineno)d - %(message)s" + reset,
        logging.INFO: grey + "[INFO]  %(asctime)s - %(name)s - %(pathname)s:%(funcName)s:l%(lineno)d - %(message)s" + reset,
        logging.WARNING: yellow + "[WARN]  %(asctime)s - %(name)s - %(pathname)s:%(funcName)s:l%(lineno)d - %(message)s" + reset,
        logging.ERROR: red + "[ERROR] %(asctime)s - %(name)s - %(pathname)s:%(funcName)s:l%(lineno)d - %(message)s" + reset,
        logging.CRITICAL: bold_red + "[CRIT] %(asctime)s - %(name)s - %(pathname)s:%(funcName)s:l%(lineno)d - %(message)s" + reset,
    }

    def format(self, record):
        """Format log record with color codes and shortened paths.

        Args:
            record: LogRecord instance containing log event information.

        Returns:
            str: Formatted log message with ANSI color codes.

        Note:
            Pathnames are shortened to start from "backend/" for readability.
        """
        backend_idx = record.pathname.find("backend/")
        if backend_idx != -1:
            record.pathname = record.pathname[backend_idx:]
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


# ----------------------------
# Logger setup
# ----------------------------
def get_logger(name: str = "erudi") -> logging.Logger:
    """Create or retrieve a configured logger instance.

    Configures a logger with both console (colored) and file (rotating) handlers.
    If a logger with the given name already exists, returns the existing instance
    to prevent duplicate handler registration. The log directory is resolved via
    ``src.launcher.runtime_paths`` so bundles and development runs share the
    same location computation.

    Args:
        name: Logger name, typically "erudi" or "erudi.<module>".
            Defaults to "erudi".

    Returns:
        logging.Logger: Configured logger instance with console and file handlers.

    Example:
        ::

            from src.core.logging import get_logger

            # Default logger
            logger = get_logger()
            logger.info("Application started")

            # Module-specific logger
            llm_logger = get_logger("erudi.domains.llms")
            llm_logger.debug("Model loaded successfully")

    Note:
        Loggers are singletons. Repeated calls with the same name return the
        same instance. Handlers are only attached on first call.
    """
    runtime_paths = ensure_runtime_paths_initialized()
    log_dir = runtime_paths.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"backend_{datetime.now().strftime('%Y-%m-%d')}.log"
    max_file_size = 10 * 1024 * 1024  # 10 MB
    backup_count = 10  # Keep 10 rotated files

    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger  # Avoid duplicate handlers

    logger.setLevel(logging.DEBUG)  # Capture all levels; handlers filter individually

    # Console handler (for development)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)  # Change to DEBUG for verbose local logging
    ch.setFormatter(CustomFormatter())
    logger.addHandler(ch)

    # File handler (rotating)
    fh = RotatingFileHandler(
        filename=log_file,
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_formatter = logging.Formatter(
        "[%(levelname)s] %(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_formatter)
    logger.addHandler(fh)

    return logger


# ----------------------------
# Silence noisy third-party loggers
# ----------------------------
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

# ----------------------------
# Global logger instance
# ----------------------------
logger = get_logger()
