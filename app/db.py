import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, Text, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import TypeDecorator

from .config import database_url

JSONType = JSON().with_variant(JSONB(), "postgresql")


class UTCDateTime(TypeDecorator):
    """Always timezone-aware UTC in Python, regardless of backend."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class RawEvent(Base):
    __tablename__ = "raw_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[str] = mapped_column(String(32))          # shadowbroker, adsb, gdelt, market_feed, aisstream
    event_type: Mapped[str] = mapped_column(String(32))
    region: Mapped[str] = mapped_column(String(16))
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[float] = mapped_column(Float, default=0.0)
    raw_payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    meta: Mapped[dict] = mapped_column("metadata", JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    __table_args__ = (
        Index("idx_raw_events_region_time", "region", "timestamp"),
        Index("idx_raw_events_type_time", "event_type", "timestamp"),
        Index("idx_raw_events_source_time", "source", "timestamp"),
    )


class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    signal_type: Mapped[str] = mapped_column(String(32))
    region: Mapped[str] = mapped_column(String(16))
    window_start: Mapped[datetime] = mapped_column(UTCDateTime)
    window_end: Mapped[datetime] = mapped_column(UTCDateTime)
    score: Mapped[int] = mapped_column(Integer)
    evidence: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    __table_args__ = (Index("idx_signals_region_type_time", "region", "signal_type", "window_end"),)


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    region: Mapped[str] = mapped_column(String(16))
    score: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(16))
    active_signals: Mapped[list] = mapped_column(JSONType, default=list)
    details: Mapped[dict] = mapped_column(JSONType, default=dict)   # raw score, multiplier, quality
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    __table_args__ = (Index("idx_snapshots_region_time", "region", "created_at"),)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    region: Mapped[str] = mapped_column(String(16))
    score: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    sent_to: Mapped[str] = mapped_column(String(64), default="")
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    status: Mapped[str] = mapped_column(String(16), default="logged")   # sent | logged | failed
    meta: Mapped[dict] = mapped_column("metadata", JSONType, default=dict)
    __table_args__ = (Index("idx_alerts_region_time", "region", "sent_at"),)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    alert_id: Mapped[str] = mapped_column(String(36))
    user_feedback: Mapped[str] = mapped_column(String(32))   # useful, false_positive, too_late, missed_event
    market_reaction: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class SettingOverride(Base):
    """Admin-edited value that overrides config.yaml. One row per setting key."""
    __tablename__ = "setting_overrides"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONType)          # {"v": <value>}
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    updated_by: Mapped[str] = mapped_column(String(64), default="admin")


class SettingChange(Base):
    """Audit log: who changed what, when, old and new value."""
    __tablename__ = "setting_changes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, default=now, index=True)
    actor: Mapped[str] = mapped_column(String(64), default="admin")
    key: Mapped[str] = mapped_column(String(64))
    old: Mapped[dict] = mapped_column(JSONType)
    new: Mapped[dict] = mapped_column(JSONType)
    note: Mapped[str] = mapped_column(String(64), default="")


class FeedRun(Base):
    """Observability: one row per collector run."""
    __tablename__ = "feed_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    feed: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0)
    ok: Mapped[bool] = mapped_column(default=True)
    events: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (Index("idx_feed_runs_feed_time", "feed", "started_at"),)


class MarketCache(Base):
    """Last good market-data payload per key (Yahoo quotes / history).

    Yahoo rate-limits some shared hosting IPs. The last successful real response is
    stored here and served, labelled with its real fetch time, when live fetches fail.
    Nothing synthetic is ever stored: only data Yahoo actually returned."""
    __tablename__ = "market_cache"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONType)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class Vessel(Base):
    """Latest AIS state per vessel (fed by the aisstream listener)."""
    __tablename__ = "vessels"
    mmsi: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    ship_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    sog: Mapped[float | None] = mapped_column(Float, nullable=True)
    nav_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    first_seen: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    positions: Mapped[int] = mapped_column(Integer, default=0)
    last_underway: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    stationary_since: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_underway_zone: Mapped[str] = mapped_column(String(48), default="")


engine = create_engine(
    database_url(),
    pool_pre_ping=True,
    connect_args={"check_same_thread": False, "timeout": 30} if database_url().startswith("sqlite") else {},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db():
    if database_url().startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _wal(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
    from .config import reload_cfg
    reload_cfg()
