import asyncio
import sys

from src.config import Config
from src.database.db_manager import BotDatabase
from src.api_client.parser_client import ParserClient
from src.bot.app import create_bot, get_bot, get_dispatcher
from src.bot.handlers import init_handlers
from src.scheduler.scheduler import create_scheduler
from src.utils.logger import setup_logger


def _seed_whitelist(db: BotDatabase, logger) -> None:
    ids = Config.all_allowed_ids()
    if not ids:
        logger.info('No whitelist IDs configured')
        return

    added = 0
    flipped = 0

    for telegram_id in ids:
        try:
            existed_before = False
            session = db.get_session()
            try:
                from src.database.models import User
                existed_before = (
                    session.query(User)
                    .filter(User.telegram_id == telegram_id)
                    .first()
                    is not None
                )
            finally:
                session.close()

            if existed_before:
                if db.allow_user_if_missing(telegram_id):
                    flipped += 1
            else:
                db.create_allowed_placeholder(telegram_id)
                added += 1
        except Exception as e:
            logger.error(f'Failed to seed whitelist for {telegram_id}: {e}')

    logger.info(
        f'Whitelist seeded: {added} new, {flipped} re-allowed, '
        f'{len(ids)} total configured'
    )
    logger.info(f'Whitelist source: {Config.WHITELIST_FILE}')


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

    _seed_whitelist(db, logger)

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