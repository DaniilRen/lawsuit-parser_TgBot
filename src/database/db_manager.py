from datetime import datetime
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import Config
from src.database.models import Base, User, Watch, NotificationLog


ALLOWED_SCHEDULES = ('every_2_min', 'hourly', 'daily', 'weekly', 'monthly')


class BotDatabase:
    def __init__(self, url: Optional[str] = None):
        url = url or Config.BOT_DB_URL
        connect_args = {'check_same_thread': False} if url.startswith('sqlite') else {}
        self.engine = create_engine(url, connect_args=connect_args, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(self.engine)

    def get_session(self):
        return self.SessionLocal()

    def get_or_create_user(self, telegram_id: int, username: str, full_name: str) -> User:
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user is None:
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    full_name=full_name,
                    is_allowed=(telegram_id == Config.ADMIN_TELEGRAM_ID),
                    notify_on_no_change=False,
                )
                session.add(user)
            else:
                user.username = username
                user.full_name = full_name
            session.commit()
            session.refresh(user)
            return user
        finally:
            session.close()

    def is_allowed(self, telegram_id: int) -> bool:
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            return bool(user and user.is_allowed)
        finally:
            session.close()

    def list_allowed_users(self) -> List[User]:
        session = self.get_session()
        try:
            return session.query(User).filter(User.is_allowed == True).all()
        finally:
            session.close()

    def allow_user(self, telegram_id: int) -> Optional[User]:
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.is_allowed = True
                session.commit()
                session.refresh(user)
            return user
        finally:
            session.close()

    def revoke_user(self, telegram_id: int) -> bool:
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user.is_allowed = False
                session.commit()
                return True
            return False
        finally:
            session.close()

    def add_watch(self, telegram_id: int, inn: str, label: str = None) -> Optional[Watch]:
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return None

            existing = session.query(Watch).filter(
                Watch.user_id == user.id, Watch.inn == inn
            ).first()
            if existing:
                if label:
                    existing.label = label
                    session.commit()
                return existing

            watch = Watch(user_id=user.id, inn=inn, label=label)
            session.add(watch)
            session.commit()
            session.refresh(watch)
            return watch
        finally:
            session.close()

    def remove_watch(self, telegram_id: int, inn: str) -> bool:
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return False
            watch = session.query(Watch).filter(
                Watch.user_id == user.id, Watch.inn == inn
            ).first()
            if not watch:
                return False
            session.delete(watch)
            session.commit()
            return True
        finally:
            session.close()

    def get_user_watches(self, telegram_id: int) -> List[Watch]:
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return []
            return session.query(Watch).filter(Watch.user_id == user.id).all()
        finally:
            session.close()

    def get_all_watches(self) -> List[Watch]:
        session = self.get_session()
        try:
            return session.query(Watch).all()
        finally:
            session.close()

    def set_user_schedule(self, telegram_id: int, schedule: str) -> bool:
        if schedule not in ALLOWED_SCHEDULES:
            return False
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return False
            user.schedule = schedule
            session.commit()
            return True
        finally:
            session.close()

    def set_notify_on_no_change(self, telegram_id: int, enabled: bool) -> bool:
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return False
            user.notify_on_no_change = bool(enabled)
            session.commit()
            return True
        finally:
            session.close()

    def get_notify_on_no_change(self, telegram_id: int) -> bool:
        session = self.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            return bool(user and user.notify_on_no_change)
        finally:
            session.close()

    def log_notification(self, user_id: int, inn: str, session_id: int,
                         changed: bool, payload: str) -> None:
        session = self.get_session()
        try:
            entry = NotificationLog(
                user_id=user_id, inn=inn, session_id=session_id,
                changed=changed, payload=payload,
            )
            session.add(entry)
            session.commit()
        finally:
            session.close()

    def update_watch_checked(self, watch_id: int, diff_hash: str) -> None:
        session = self.get_session()
        try:
            watch = session.query(Watch).filter(Watch.id == watch_id).first()
            if watch:
                watch.last_checked_at = datetime.utcnow()
                watch.last_diff_hash = diff_hash
                session.commit()
        finally:
            session.close()