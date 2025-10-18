import logging
import sys
from logging.handlers import RotatingFileHandler
from backend.src.core.vars import LOG_FILE, MAX_FILE_SIZE, BACKUP_COUNT

# ----------------------------
# Formatter
# ----------------------------
class CustomFormatter(logging.Formatter):
    """Custom formatter to add colors for console output."""

    grey = "\x1b[38;21m"
    yellow = "\x1b[33;21m"
    red = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    blue = "\x1b[34;21m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: blue + "[DEBUG] %(asctime)s - %(name)s - %(message)s" + reset,
        logging.INFO: grey + "[INFO]  %(asctime)s - %(name)s - %(message)s" + reset,
        logging.WARNING: yellow + "[WARN]  %(asctime)s - %(name)s - %(message)s" + reset,
        logging.ERROR: red + "[ERROR] %(asctime)s - %(name)s - %(message)s" + reset,
        logging.CRITICAL: bold_red + "[CRIT] %(asctime)s - %(name)s - %(message)s" + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

# ----------------------------
# Logger setup
# ----------------------------
def get_logger(name: str = "erudi-backend") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger  # Avoid duplicate handlers

    logger.setLevel(logging.DEBUG)  # Capture all levels; handlers filter individually

    # Console handler (for development)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)  # Change to DEBUG for verbose local logging
    ch.setFormatter(CustomFormatter())
    logger.addHandler(ch)

    # File handler (rotating)
    fh = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=MAX_FILE_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    file_formatter = logging.Formatter(
        "[%(levelname)s] %(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_formatter)
    logger.addHandler(fh)

    # Optionally, add integration with Sentry or other monitoring tools here

    return logger

# ----------------------------
# Global logger instance
# ----------------------------
logger = get_logger()