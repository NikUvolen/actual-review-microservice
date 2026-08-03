import os
from pathlib import Path

from loguru import logger


_CONFIGURED = False


def configure_logging() -> None:
    """
    Configure loguru once for the whole Django/Celery process.

    - stderr: INFO (human readable)
    - debug.log: DEBUG (persistent)
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    file_level = os.getenv("LOG_FILE_LEVEL", "DEBUG").upper()
    log_dir = Path(os.getenv("LOG_DIR", "."))
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=log_level,
        format="{time} {level} {message}",
        enqueue=True,
    )

    logger.add(
        log_dir / "debug.log",
        level=file_level,
        format="{time} {level} {message}",
        enqueue=True,
        rotation="10 MB",
        retention="10 days",
    )

    _CONFIGURED = True
