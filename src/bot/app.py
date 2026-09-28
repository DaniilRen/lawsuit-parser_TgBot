from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from src.config import Config
from src.bot.handlers import router

_bot: Bot = None
_dp: Dispatcher = None

def get_bot() -> Bot:
    if _bot is None:
        raise RuntimeError('Bot is not initialized')
    return _bot

def create_bot() -> Bot:
    global _bot, _dp

    if Config.PROXY_URL:
        # Create a session that routes traffic through the proxy
        session = AiohttpSession(proxy=Config.PROXY_URL)
    else:
        # Default session without a proxy
        session = AiohttpSession()

    _bot = Bot(token=Config.BOT_TOKEN, session=session)
    _dp = Dispatcher()
    _dp.include_router(router)
    return _bot

def get_dispatcher() -> Dispatcher:
    if _dp is None:
        raise RuntimeError('Dispatcher is not initialized')
    return _dp