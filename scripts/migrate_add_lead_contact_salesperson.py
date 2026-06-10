#!/usr/bin/env python
"""Add salesperson_id column to lead_contacts with index for salesperson activity metrics.

Usage:
  ./.venv/Scripts/python.exe scripts/migrate_add_lead_contact_salesperson.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(os.path.join(project_root, ".env"))

from backend.app.database import engine  # noqa: E402


def _is_sqlite() -> bool:
    return str(engine.url).startswith("sqlite")


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    if _is_sqlite():
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return any(str(r[1]) == column_name for r in rows)

    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table_name AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).fetchone()
    return row is not None


def run() -> int:
    print("=" * 72)
    print("MIGRATION: add lead_contacts.salesperson_id")
    print("=" * 72)

    with engine.begin() as conn:
        if not _column_exists(conn, "lead_contacts", "salesperson_id"):
            conn.execute(text("ALTER TABLE lead_contacts ADD COLUMN salesperson_id INTEGER"))

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_lead_contacts_salesperson_id ON lead_contacts(salesperson_id)"))

    print("Migration completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
