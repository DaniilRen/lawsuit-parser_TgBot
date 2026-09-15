from datetime import datetime

from sqlalchemy import (
    Column, Integer, BigInteger, String, DateTime, Boolean, ForeignKey,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(64))
    full_name = Column(String(255))
    is_allowed = Column(Boolean, default=False)
    schedule = Column(String(16), default='weekly')
    notify_on_no_change = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)

    watches = relationship("Watch", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_users_telegram_id', 'telegram_id'),
    )


class Watch(Base):
    __tablename__ = 'watches'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    inn = Column(String(12), nullable=False)
    label = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_checked_at = Column(DateTime)
    last_diff_hash = Column(String(64))

    user = relationship("User", back_populates="watches")

    __table_args__ = (
        UniqueConstraint('user_id', 'inn', name='uq_watch_user_inn'),
        Index('idx_watches_inn', 'inn'),
    )


class NotificationLog(Base):
    __tablename__ = 'notification_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    inn = Column(String(12), nullable=False)
    session_id = Column(Integer)
    changed = Column(Boolean, default=False)
    payload = Column(String)
    sent_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_notifications_user', 'user_id'),
    )