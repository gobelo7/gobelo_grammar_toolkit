"""
Logging configuration for GGTK.
"""

import logging
import sys
from typing import Optional

# Module-level logger
logger = logging.getLogger("ggtk")


def setup_logging(
    level: int = logging.WARNING,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> None:
    """
    Configure GGTK logging.
    
    Parameters
    ----------
    level : int
        Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    log_file : str, optional
        Path to log file. If None, logs to stderr only.
    format_string : str, optional
        Custom log format string.
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    formatter = logging.Formatter(format_string)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    logger.setLevel(level)


def get_logger(name: str = None) -> logging.Logger:
    """Get a logger instance."""
    if name:
        return logging.getLogger(f"ggtk.{name}")
    return logger
