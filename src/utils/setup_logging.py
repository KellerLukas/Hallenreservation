import os
import logging
from logging.handlers import WatchedFileHandler

from src.utils.config import LOG_FILE


class SafeWatchedFileHandler(WatchedFileHandler):
    """
    Ensure a new file is created if the log file gets deleted.
    """

    def emit(self, record: logging.LogRecord) -> None:
        if not os.path.exists(self.baseFilename):
            open(self.baseFilename, "a").close()
        super().emit(record)


def setup_logging_to_file() -> None:
    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create a formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Create and add the SafeWatchedFileHandler
    handler = SafeWatchedFileHandler(LOG_FILE)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
