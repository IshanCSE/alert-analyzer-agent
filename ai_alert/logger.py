"""Logging setup for AI Alert Agent."""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger as loguru_logger

from ai_alert.config import Config


def setup_logger(config: Optional[Config] = None, level: str = "INFO") -> None:
    """Setup logging with loguru."""
    if config is None:
        from ai_alert.config import load_config
        config = load_config()

    # Use config level if not specified
    if level == "INFO":
        level = config.logging.level.upper()

    # Create log directory
    log_dir = Path(config.logging.dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Remove default handler
    loguru_logger.remove()

    # Add console handler
    loguru_logger.add(
        sys.stdout,
        format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
    )

    # Add file handler with daily rotation
    log_file = log_dir / "ai-alert-{time:YYYY-MM-DD}.log"
    loguru_logger.add(
        str(log_file),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=level,
        rotation="00:00",  # Daily rotation at midnight
        retention="7 days",  # Keep last 7 days of logs
    )


def get_logger(name: str):
    """Get logger instance."""
    return loguru_logger.bind(name=name)
