import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from src.config import Config


def setup_logger(name: str = 'company_info_bot') -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }
    logger.setLevel(level_map.get(Config.LOG_LEVEL.upper(), logging.INFO))

    Path(Config.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        Config.LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5,
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S',
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str = 'company_info_bot') -> logging.Logger:
    return logging.getLogger(name)