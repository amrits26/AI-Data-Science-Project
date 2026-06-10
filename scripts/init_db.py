#!/usr/bin/env python
"""
Initialize PostgreSQL database for Imperial Cars AI system.

Creates all tables defined in backend.app.database.models

Usage:
    python scripts/init_db.py

Requires:
    - DATABASE_URL environment variable or .env file
    - PostgreSQL running and accessible
    - pgvector extension installed: CREATE EXTENSION pgvector;
"""

import sys
import os
from pathlib import Path

# Add parent directory to path so imports work
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.app.core.platform_compat import patch_platform_machine_for_windows

patch_platform_machine_for_windows()

# Load environment variables from .env if it exists
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))
from sqlalchemy import text

from backend.app.database.db import init_db, health_check, engine
from backend.app.database.models import Base


def main():
    """Main initialization routine."""
    print("=" * 70)
    print("IMPERIAL CARS AI SYSTEM - DATABASE INITIALIZATION")
    print("=" * 70)

    # Check database connection
    print("\n[1/3] Checking database connection...")
    if not health_check():
        print("❌ Database connection failed!")
        print("   Ensure DATABASE_URL is set and PostgreSQL is running.")
        print("   Example: postgresql://user:password@localhost:5432/imperial_dealership")
        sys.exit(1)
    print("✓ Database connection successful")

    # Initialize database (create tables)
    print("\n[2/3] Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Tables created successfully")
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        sys.exit(1)

    # Verify tables
    print("\n[3/3] Verifying tables...")
    try:
        with engine.connect() as conn:
            if str(engine.url).startswith("sqlite"):
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
                tables = [row[0] for row in result.fetchall()]
            else:
                result = conn.execute(text("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """))
                tables = [row[0] for row in result.fetchall()]

        expected_tables = {
            "cars", "market_prices", "carfax_records",
            "customers", "vehicles",
            "service_jobs", "job_updates", "service_events",
            "nurture_log", "followup_log", "customer_channel_prefs", "resume_deal_sessions", "lead_contacts", "daily_goals", "triage_sessions", "session_snapshots", "service_videos"
            , "sales_stage_events"
        }

        created_tables = set(tables)
        all_exist = expected_tables.issubset(created_tables)

        print(f"\nTables created ({len(created_tables)}):")
        for table in sorted(tables):
            status = "✓" if table in expected_tables else "◇"
            print(f"  {status} {table}")

        if all_exist:
            print("\n✓ All required tables initialized successfully!")
            print("\nNext steps:")
            print("  1. Download Kaggle dataset: data/raw/large_cars_dataset.csv")
            print("  2. Run: python scripts/import_car_data.py")
            print("  3. Run: python backend/app/main.py  (FastAPI)")
            print("  4. Run: streamlit run frontend/app.py")
            print("  5. Run: python sales_bot.py")
            return 0
        else:
            missing = expected_tables - created_tables
            print(f"\n❌ Missing tables: {missing}")
            return 1

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
