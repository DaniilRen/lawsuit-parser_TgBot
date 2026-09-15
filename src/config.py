import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '').strip()
    ADMIN_TELEGRAM_ID: int = int(os.getenv('ADMIN_TELEGRAM_ID', '0') or 0)

    PARSER_API_URL: str = os.getenv('PARSER_API_URL', 'http://127.0.0.1:8000').rstrip('/')
    PARSER_API_KEY: str = os.getenv('PARSER_API_KEY', '').strip()

    BOT_DB_URL: str = os.getenv('BOT_DB_URL', 'sqlite:///./bot_data.db')

    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE: str = os.getenv('LOG_FILE', 'logs/bot.log')

    DEFAULT_SCHEDULE: str = os.getenv('DEFAULT_SCHEDULE', 'weekly').lower()

    @classmethod
    def validate(cls) -> None:
        if not cls.BOT_TOKEN:
            raise RuntimeError("BOT_TOKEN is not set")
        if not cls.ADMIN_TELEGRAM_ID:
            raise RuntimeError("ADMIN_TELEGRAM_ID is not set")


Path('logs').mkdir(exist_ok=True)