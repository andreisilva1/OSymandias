import sys

from loguru import logger

from osymandias.runtime.config import settings


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.osy_log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>"
        ),
        colorize=True,
    )
    logger.add(
        "logs/osymandias.log",
        level=settings.osy_log_level,
        rotation="100 MB",
        retention="14 days",
        serialize=True,  # JSON in file
    )
    logger.info("Logging initialised at level {}", settings.osy_log_level)
