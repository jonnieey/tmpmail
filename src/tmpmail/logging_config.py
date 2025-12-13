#!/usr/bin/env python
# logging_config.py - Centralized logging configuration

import logging
import sys
import os
from pathlib import Path
from typing import Optional

# Define log format with function name
LOG_FORMAT = "%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: Optional[str] = None, log_file: Optional[str] = None, console: bool = False
) -> None:
    """
    Setup centralized logging for the entire project.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        console: Whether to log to console
    """
    # Get log level from environment or parameter
    if level is None:
        level = os.getenv("TMPMAIL_LOG_LEVEL", "WARNING").upper()

    log_level = getattr(logging, level, logging.WARNING)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Prevent lastResort (stderr) if no handlers
    if not root_logger.handlers:
        root_logger.addHandler(logging.NullHandler())

    # Set logging level for third-party libraries
    logging.getLogger("xtempmail").setLevel(logging.WARNING)
    logging.getLogger("mailtm").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)

    # Log startup message
    logger = logging.getLogger(__name__)
    if log_level <= logging.INFO:
        logger.info(f"Logging initialized at level: {level}")
    if log_file and log_level <= logging.INFO:
        logger.info(f"Log file: {log_file}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
