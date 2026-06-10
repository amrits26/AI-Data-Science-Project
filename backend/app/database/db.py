"""
Database connection and session management for PostgreSQL + pgvector.

Handles:
- Connection pooling
- Session lifecycle management
- Engine initialization
"""

import os
import time
import logging
from typing import Any, Generator

from backend.app.core.platform_compat import patch_platform_machine_for_windows

patch_platform_machine_for_windows()

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./imperial_cars.db")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))
DB_HEALTH_RETRIES = int(os.getenv("DB_HEALTH_RETRIES", "3"))
logger = logging.getLogger(__name__)

# Create engine with connection pooling
# pool_size=10: number of connections to keep in pool
# max_overflow=20: additional connections allowed beyond pool_size
# pool_pre_ping=True: verify connections before using them (handles stale connections)
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_pre_ping=True,
        echo=False,
        pool_recycle=1800,
        connect_args={"connect_timeout": DB_CONNECT_TIMEOUT},
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Generator[Session, None, None]:
    """
    Dependency injection for FastAPI routes.
    
    Usage in FastAPI:
        @app.get("/items")
        def get_items(db: Session = Depends(get_session)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Direct session creation for non-async contexts (scripts, agents).
    
    Usage:
        from backend.app.database.db import get_db_session
        db = get_db_session()
        cars = db.query(Car).all()
        db.close()
    """
    return SessionLocal()


def init_db():
    """
    Initialize database tables.
    
    Must be called before first use:
        from backend.app.database.db import init_db
        from backend.app.database.models import Base
        init_db()
    """
    from backend.app.database.models import Base
    Base.metadata.create_all(bind=engine)
    ensure_inventory_schema()
    print("✓ Database tables initialized successfully.")


def drop_db():
    """
    Drop all database tables (for testing/reset only).
    
    WARNING: This deletes all data!
    """
    from backend.app.database.models import Base
    Base.metadata.drop_all(bind=engine)
    print("✓ All tables dropped (data deleted).")


def health_check() -> bool:
    """
    Check database connection health.
    
    Returns True if connection successful, False otherwise.
    """
    for attempt in range(1, DB_HEALTH_RETRIES + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            if attempt < DB_HEALTH_RETRIES:
                time.sleep(min(2 ** (attempt - 1), 4))
            logger.warning("db_health_check_failed", extra={"attempt": attempt, "error": str(e)})
    return False


def ensure_inventory_schema() -> None:
    """Backfill inventory availability columns/indexes for existing deployments."""
    is_sqlite = DATABASE_URL.startswith("sqlite")
    statements: list[str] = []

    if is_sqlite:
        statements = [
            "ALTER TABLE cars ADD COLUMN available BOOLEAN DEFAULT 1",
            "ALTER TABLE cars ADD COLUMN availability_status VARCHAR(20) DEFAULT 'available'",
            "ALTER TABLE cars ADD COLUMN last_seen DATETIME",
            "ALTER TABLE cars ADD COLUMN last_updated DATETIME",
            "ALTER TABLE cars ADD COLUMN vin VARCHAR(32)",
            "ALTER TABLE cars ADD COLUMN stock_number VARCHAR(64)",
            "ALTER TABLE cars ADD COLUMN color VARCHAR(50)",
            "ALTER TABLE cars ADD COLUMN mileage INTEGER",
            "ALTER TABLE cars ADD COLUMN detail_url VARCHAR(500)",
            "ALTER TABLE cars ADD COLUMN fuel_type VARCHAR(50)",
            "ALTER TABLE cars ADD COLUMN spec_source VARCHAR(100)",
        ]
    else:
        statements = [
            "ALTER TABLE cars ADD COLUMN IF NOT EXISTS available BOOLEAN DEFAULT TRUE",
            "ALTER TABLE cars ADD COLUMN IF NOT EXISTS availability_status VARCHAR(20) DEFAULT 'available'",
            "ALTER TABLE cars ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP",
            "ALTER TABLE cars ADD COLUMN IF NOT EXISTS last_updated TIMESTAMP",
            "ALTER TABLE cars ADD COLUMN IF NOT EXISTS vin VARCHAR(32)",
            "ALTER TABLE cars ADD COLUMN IF NOT EXISTS stock_number VARCHAR(64)",
            "ALTER TABLE cars ADD COLUMN IF NOT EXISTS color VARCHAR(50)",
            "ALTER TABLE cars ADD COLUMN IF NOT EXISTS mileage INTEGER",
            "ALTER TABLE cars ADD COLUMN IF NOT EXISTS detail_url VARCHAR(500)",
            "ALTER TABLE cars ADD COLUMN IF NOT EXISTS fuel_type VARCHAR(50)",
            "ALTER TABLE cars ADD COLUMN IF NOT EXISTS spec_source VARCHAR(100)",
        ]

    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception as exc:
                # SQLite raises duplicate-column errors without IF NOT EXISTS support.
                logger.debug("inventory_schema_alter_skipped", extra={"statement": stmt, "error": str(exc)})

        index_statements = [
            "CREATE INDEX IF NOT EXISTS ix_cars_available ON cars (available)",
            "CREATE INDEX IF NOT EXISTS ix_cars_availability_status ON cars (availability_status)",
            "CREATE INDEX IF NOT EXISTS ix_cars_vin ON cars (vin)",
            "CREATE INDEX IF NOT EXISTS ix_cars_stock_number ON cars (stock_number)",
            "CREATE INDEX IF NOT EXISTS ix_cars_last_updated ON cars (last_updated)",
        ]
        for stmt in index_statements:
            try:
                conn.execute(text(stmt))
            except Exception as exc:
                logger.debug("inventory_schema_index_skipped", extra={"statement": stmt, "error": str(exc)})


def get_inventory_by_query(
    year: int | None = None,
    make: str | None = None,
    model: str | None = None,
    trim: str | None = None,
    color: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Query inventory from cars table and return normalized rows for chat and UI use."""
    from sqlalchemy import func, tuple_

    from backend.app.database.models import Car

    ensure_inventory_schema()
    db = get_db_session()
    try:
        safe_limit = max(1, min(int(limit or 3), 25))
        query = db.query(Car).filter(Car.available.is_(True), Car.availability_status == "available")

        if year:
            query = query.filter(Car.year == int(year))
        if make:
            query = query.filter(Car.make.ilike(f"%{str(make).strip()}%"))
        if model:
            query = query.filter(Car.model.ilike(f"%{str(model).strip()}%"))
        if trim:
            query = query.filter(Car.trim.ilike(f"%{str(trim).strip()}%"))
        if color:
            query = query.filter(Car.color.ilike(f"%{str(color).strip()}%"))

        rows = (
            query.order_by(Car.year.desc(), Car.make.asc(), Car.model.asc(), Car.trim.asc())
            .limit(safe_limit)
            .all()
        )

        if not rows and trim:
            relaxed = db.query(Car).filter(Car.available.is_(True), Car.availability_status == "available")
            if year:
                relaxed = relaxed.filter(Car.year == int(year))
            if make:
                relaxed = relaxed.filter(Car.make.ilike(f"%{str(make).strip()}%"))
            if model:
                relaxed = relaxed.filter(Car.model.ilike(f"%{str(model).strip()}%"))
            if color:
                relaxed = relaxed.filter(Car.color.ilike(f"%{str(color).strip()}%"))
            rows = (
                relaxed.order_by(Car.year.desc(), Car.make.asc(), Car.model.asc())
                .limit(safe_limit)
                .all()
            )

        pairs = {(row.make, row.model) for row in rows if row.make and row.model}
        stock_counts: dict[tuple[str, str], int] = {}
        if pairs:
            grouped = (
                db.query(Car.make, Car.model, func.count(Car.id))
                .filter(tuple_(Car.make, Car.model).in_(list(pairs)))
                .group_by(Car.make, Car.model)
                .all()
            )
            stock_counts = {(make_val, model_val): int(count or 0) for make_val, model_val, count in grouped}

        normalized: list[dict[str, Any]] = []
        for row in rows:
            stock_count = int(stock_counts.get((row.make, row.model), 1) or 1)
            normalized.append(
                {
                    "id": int(row.id),
                    "year": int(row.year) if row.year is not None else None,
                    "make": row.make,
                    "model": row.model,
                    "trim": row.trim,
                    "price": float(row.msrp) if row.msrp is not None else (float(row.used_avg_price) if row.used_avg_price is not None else None),
                    "msrp": float(row.msrp) if row.msrp is not None else None,
                    "used_avg_price": float(row.used_avg_price) if row.used_avg_price is not None else None,
                    "mileage": int(row.mileage) if row.mileage is not None else None,
                    "color": row.color,
                    "image_url": "/placeholder-car.jpg",
                    "vin": row.vin,
                    "stock_number": row.stock_number,
                    "detail_url": row.detail_url,
                    "available": bool(row.available),
                    "availability_status": row.availability_status,
                    "last_seen": row.last_seen.isoformat() if row.last_seen else None,
                    "last_updated": row.last_updated.isoformat() if row.last_updated else None,
                    "stock_count": stock_count,
                    "horsepower": int(row.horsepower) if row.horsepower is not None else None,
                    "torque": int(row.torque) if row.torque is not None else None,
                    "mpg_highway": float(row.mpg_highway) if row.mpg_highway is not None else None,
                    "towing_capacity": int(row.towing_capacity) if row.towing_capacity is not None else None,
                    "safety_rating": float(row.safety_rating) if row.safety_rating is not None else None,
                    "reliability_score": float(row.reliability_score) if row.reliability_score is not None else None,
                }
            )

        return normalized
    finally:
        db.close()


def inventory_status_summary() -> dict[str, Any]:
    """Return inventory freshness and availability aggregates for admin dashboards."""
    from datetime import datetime, timedelta

    from sqlalchemy import func

    from backend.app.database.models import Car

    ensure_inventory_schema()
    db = get_db_session()
    try:
        now = datetime.utcnow()
        day_ago = now - timedelta(hours=24)
        last_scrape = db.query(func.max(Car.last_updated)).scalar()
        available_count = int(db.query(func.count(Car.id)).filter(Car.available.is_(True)).scalar() or 0)
        sold_24h = int(
            db.query(func.count(Car.id))
            .filter(Car.available.is_(False), Car.last_updated.isnot(None), Car.last_updated >= day_ago)
            .scalar()
            or 0
        )
        return {
            "last_scrape": last_scrape.isoformat() if last_scrape else None,
            "available_count": available_count,
            "sold_last_24h": sold_24h,
            "generated_at": now.isoformat() + "Z",
        }
    finally:
        db.close()
