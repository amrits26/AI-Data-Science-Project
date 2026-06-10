#!/usr/bin/env python
"""Add lead_contacts table and indexes for Phase 3 Task 3.1.

Usage:
  c:/Users/amrit/OneDrive/Documents/AI Data Science Project/.venv/Scripts/python.exe scripts/migrate_add_lead_contacts.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

# Ensure project root imports work when script is executed directly.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(os.path.join(project_root, ".env"))

from backend.app.database import Base, engine  # noqa: E402
from backend.app.database.models import LeadContact  # noqa: E402


def _table_exists(conn, table_name: str) -> bool:
    if str(engine.url).startswith("sqlite"):
        row = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).fetchone()
        return row is not None

    row = conn.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :name
            """
        ),
        {"name": table_name},
    ).fetchone()
    return row is not None


def run() -> int:
    print("=" * 72)
    print("PHASE 3 MIGRATION: add lead_contacts table")
    print("=" * 72)

    with engine.begin() as conn:
        exists_before = _table_exists(conn, "lead_contacts")
        print(f"[1/3] lead_contacts exists before migration: {exists_before}")

        # Create only the new table if missing.
        LeadContact.__table__.create(bind=conn, checkfirst=True)

        # Idempotent index creation for both SQLite and PostgreSQL.
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_lead_contacts_customer_id ON lead_contacts(customer_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_lead_contacts_contact_type ON lead_contacts(contact_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_lead_contacts_outcome ON lead_contacts(outcome)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_lead_contacts_contacted_at ON lead_contacts(contacted_at)"))

        exists_after = _table_exists(conn, "lead_contacts")
        print(f"[2/3] lead_contacts exists after migration: {exists_after}")

    with engine.connect() as conn:
        if str(engine.url).startswith("sqlite"):
            indexes = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='lead_contacts' ORDER BY name")
            ).fetchall()
            index_names = [row[0] for row in indexes]
        else:
            indexes = conn.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public' AND tablename = 'lead_contacts'
                    ORDER BY indexname
                    """
                )
            ).fetchall()
            index_names = [row[0] for row in indexes]

    print("[3/3] lead_contacts indexes:")
    for name in index_names:
        print(f"  - {name}")

    if not exists_after:
        print("Migration failed: lead_contacts table was not created.")
        return 1

    print("Migration completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
