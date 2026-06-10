"""Database package: PostgreSQL connection, session management, ORM models."""

from backend.app.database.db import (
    engine,
    SessionLocal,
    get_session,
    get_db_session,
    init_db,
    drop_db,
    health_check,
)

# Only import Base to avoid circular import issues

# Import all ORM models for explicit export
from backend.app.database.models import (
    Base,
    Car,
    MarketPrice,
    CarfaxRecord,
    Customer,
    Vehicle,
    ServiceJob,
    JobUpdate,
    ServiceEvent,
    NurtureLog,
    FollowupLog,
    CustomerChannelPref,
    LeadContact,
    DailyGoal,
    TriageSession,
    SessionSnapshot,
    ServiceVideo,
    ResumeDealSession,
    SalesStageEvent,
)

__all__ = [
    "engine",
    "SessionLocal",
    "get_session",
    "get_db_session",
    "init_db",
    "drop_db",
    "health_check",
    "Base",
    "Car",
    "MarketPrice",
    "CarfaxRecord",
    "Customer",
    "Vehicle",
    "ServiceJob",
    "JobUpdate",
    "ServiceEvent",
    "NurtureLog",
    "FollowupLog",
    "CustomerChannelPref",
    "LeadContact",
    "DailyGoal",
    "TriageSession",
    "SessionSnapshot",
    "ServiceVideo",
    "ResumeDealSession",
    "SalesStageEvent",
    "ResumeDealSession",
    "SalesStageEvent",
]
