import asyncio
import sys

from src.config import Config
from src.database.db_manager import BotDatabase
from src.api_client.parser_client import ParserClient
from src.bot.app import create_bot, get_bot, get_dispatcher
from src.bot.handlers import init_handlers
from src.scheduler.scheduler import create_scheduler
from src.utils.logger import setup_logger


async def main():
    Config.validate()
    logger = setup_logger()

    logger.info('Starting bot...')

    db = BotDatabase()
    parser = ParserClient()

    try:
        health = await parser.health()
        logger.info(f'Parser API health: {health}')
    except Exception as e:
        logger.error(f'Cannot reach parser API at {Config.PARSER_API_URL}: {e}')
        logger.error('Make sure the parser API is running.')
        await parser.close()
        return 1

    init_handlers(db, parser)

    bot = create_bot()
    dp = get_dispatcher()

    scheduler = create_scheduler(db, parser)
    scheduler.start()
    logger.info('Scheduler started')

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await parser.close()
        await bot.session.close()
        logger.info('Bot stopped')

    return 0


if __name__ == '__main__':
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(0)