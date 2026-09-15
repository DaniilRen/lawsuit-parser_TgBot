import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.database.db_manager import BotDatabase
from src.api_client.parser_client import ParserClient, ParserApiError
from src.bot import formatting
from src.bot.app import get_bot
from src.utils.logger import setup_logger


logger = setup_logger()


class WatchScheduler:
    def __init__(self, db: BotDatabase, parser: ParserClient):
        self.db = db
        self.parser = parser
        self.scheduler = AsyncIOScheduler()
        self._job_map = {}  # watch_id -> job

    def start(self):
        self.scheduler.start()
        self._sync_jobs()

    def shutdown(self):
        try:
            self.scheduler.shutdown(wait=False)
        except Exception:
            pass

    def _sync_jobs(self):
        for job in list(self._job_map.values()):
            try:
                job.remove()
            except Exception:
                pass
        self._job_map.clear()

        watches = self.db.get_all_watches()
        for watch in watches:
            self._schedule_watch(watch)

    def _interval_for_schedule(self, schedule: str) -> dict:
        if schedule == 'daily':
            return {'hours': 24}
        if schedule == 'monthly':
            return {'days': 30}
        return {'days': 7}  # weekly default

    def _schedule_watch(self, watch):
        user_schedule = 'weekly'
        try:
            session = self.db.get_session()
            user = session.query(__import__('src.database.models', fromlist=['User']).User).filter_by(id=watch.user_id).first()
            if user:
                user_schedule = user.schedule or 'weekly'
            session.close()
        except Exception:
            pass

        interval = self._interval_for_schedule(user_schedule)

        job = self.scheduler.add_job(
            self._check_watch,
            trigger=IntervalTrigger(**interval),
            args=[watch.id],
            id=f'watch_{watch.id}',
            replace_existing=True,
            next_run_time=datetime.utcnow(),
        )
        self._job_map[watch.id] = job

    async def _check_watch(self, watch_id: int):
        session = self.db.get_session()
        try:
            from src.database.models import Watch, User
            watch = session.query(Watch).filter_by(id=watch_id).first()
            if not watch:
                return
            user = session.query(User).filter_by(id=watch.user_id).first()
            if not user or not user.is_allowed:
                return
            telegram_id = user.telegram_id
            inn = watch.inn
        finally:
            session.close()

        logger.info(f'Scheduled check for INN {inn} (user {telegram_id})')

        try:
            await self.parser.parse_inn(inn)
            diff = await self.parser.get_diff_latest(inn)
        except ParserApiError as e:
            logger.error(f'Parser API error for {inn}: {e.code} - {e.message}')
            return
        except Exception as e:
            logger.exception(f'Unexpected error checking {inn}')
            return

        if not diff.get('changed'):
            logger.info(f'No changes for {inn}')
            return

        try:
            latest = await self.parser.get_latest(inn)
            company_name = None
            for source_data in latest.get('sources', {}).values():
                if isinstance(source_data, dict):
                    company_name = source_data.get('company_name') or source_data.get('short_name')
                    if company_name:
                        break
        except Exception:
            company_name = None

        text = formatting.format_diff_message(inn, diff, company_name)

        try:
            bot = get_bot()
            await bot.send_message(chat_id=telegram_id, text=text)
            logger.info(f'Notified user {telegram_id} about changes in {inn}')
        except Exception as e:
            logger.exception(f'Failed to send notification for {inn}')


def get_scheduler() -> WatchScheduler:
    raise RuntimeError('Use create_scheduler instead')


def create_scheduler(db: BotDatabase, parser: ParserClient) -> WatchScheduler:
    return WatchScheduler(db, parser)