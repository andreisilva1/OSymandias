import sys

from loguru import logger

from aios.config import settings


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>"
        ),
        colorize=True,
    )
    logger.add(
        "logs/aios.log",
        level=settings.log_level,
        rotation="100 MB",
        retention="14 days",
        serialize=True,  # JSON in file
    )
    logger.info("Logging initialised at level {}", settings.log_level)
