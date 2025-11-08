"""Logging configuration utilities."""

import logging


def configure_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Configure application logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_format: Format type ('json' or 'text')
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    if log_format == "json":
        # JSON format for production
        logging.basicConfig(
            level=level,
            format="%(message)s",
            handlers=[logging.StreamHandler()],
        )
    else:
        # Human-readable format for development
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured: level={log_level}, format={log_format}")
