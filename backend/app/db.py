"""Database models. SQLite locally, Postgres in production (set PUNDIT_DATABASE_URL)."""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CacheEntry(Base):
    __tablename__ = "cache_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    normalized: Mapped[str] = mapped_column(Text)
    embedding: Mapped[bytes] = mapped_column(LargeBinary)
    answer: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    entities: Mapped[dict] = mapped_column(JSON, default=dict)
    volatile: Mapped[bool] = mapped_column(Boolean, default=True)
    data_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)


class RequestLog(Base):
    __tablename__ = "request_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    mode: Mapped[str] = mapped_column(String(16))  # ask | debate | challenge
    question: Mapped[str] = mapped_column(Text)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    guard_skip: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    flagged_docs: Mapped[int] = mapped_column(Integer, default=0)
    output_blocked: Mapped[str | None] = mapped_column(String(32), nullable=True)
    judge_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cached_after: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_hash: Mapped[str] = mapped_column(String(64), default="")


class DebateRecord(Base):
    __tablename__ = "debates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    question: Mapped[str] = mapped_column(Text)
    model_a: Mapped[str] = mapped_column(String(64))
    model_b: Mapped[str] = mapped_column(String(64))
    answer_a: Mapped[str] = mapped_column(Text)
    answer_b: Mapped[str] = mapped_column(Text)
    judge_ab: Mapped[str | None] = mapped_column(String(8), nullable=True)
    judge_ba: Mapped[str | None] = mapped_column(String(8), nullable=True)
    judge_final: Mapped[str | None] = mapped_column(String(8), nullable=True)
    judge_reason: Mapped[str] = mapped_column(Text, default="")
    human_vote: Mapped[str | None] = mapped_column(String(8), nullable=True)


class ChallengeAttempt(Base):
    __tablename__ = "challenge_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    nickname: Mapped[str] = mapped_column(String(24), default="anonymous")
    goal: Mapped[str] = mapped_column(String(24))
    post: Mapped[str] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text)
    reply: Mapped[str] = mapped_column(Text)
    guardrails_on: Mapped[bool] = mapped_column(Boolean)
    success: Mapped[bool] = mapped_column(Boolean)
    blocked_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


def make_session_factory(url: str):
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
