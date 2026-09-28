import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _parse_id_list(raw: str) -> List[int]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(',')]
    result: List[int] = []
    for p in parts:
        if not p:
            continue
        try:
            result.append(int(p))
        except ValueError:
            continue
    return result


def _load_whitelist_file(path: Path) -> List[int]:
    if not path.exists():
        return []
    ids: List[int] = []
    try:
        for raw_line in path.read_text(encoding='utf-8').splitlines():
            line = raw_line.split('#', 1)[0].strip()
            if not line:
                continue
            for token in line.replace(',', ' ').split():
                try:
                    ids.append(int(token))
                except ValueError:
                    continue
    except Exception:
        return []
    return ids


class Config:
    PROXY_URL: str = os.getenv('PROXY_URL', '').strip()

    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '').strip()
    ADMIN_TELEGRAM_ID: int = int(os.getenv('ADMIN_TELEGRAM_ID', '0') or 0)

    WHITELIST_FILE: Path = Path(
        os.getenv('WHITELIST_FILE', 'whitelist.txt')
    )

    _ENV_ALLOWED: List[int] = _parse_id_list(
        os.getenv('ALLOWED_TELEGRAM_IDS', '')
    )

    PARSER_API_URL: str = os.getenv('PARSER_API_URL', 'http://127.0.0.1:5050').rstrip('/')
    PARSER_API_KEY: str = os.getenv('PARSER_API_KEY', '').strip()

    BOT_DB_URL: str = os.getenv('BOT_DB_URL', 'sqlite:///./bot_data.db')

    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE: str = os.getenv('LOG_FILE', 'logs/bot.log')

    DEFAULT_SCHEDULE: str = os.getenv('DEFAULT_SCHEDULE', 'weekly').lower()

    @classmethod
    def all_allowed_ids(cls) -> List[int]:
        ids = set(cls._ENV_ALLOWED)
        ids.update(_load_whitelist_file(cls.WHITELIST_FILE))
        if cls.ADMIN_TELEGRAM_ID:
            ids.add(cls.ADMIN_TELEGRAM_ID)
        return sorted(ids)

    @classmethod
    def validate(cls) -> None:
        if not cls.BOT_TOKEN:
            raise RuntimeError("BOT_TOKEN is not set")
        if not cls.ADMIN_TELEGRAM_ID:
            raise RuntimeError("ADMIN_TELEGRAM_ID is not set")


Path('logs').mkdir(exist_ok=True)