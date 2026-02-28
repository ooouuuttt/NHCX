"""
Centralized logging configuration for the NHCX pipeline.

Import and call setup_logging() once at application startup (main.py / server.py).
All other modules use:  logger = logging.getLogger(__name__)
"""

import os
import logging


def setup_logging(log_file="logs/pipeline.log", level=logging.INFO):
    """Configure root logger with file + console handlers."""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )