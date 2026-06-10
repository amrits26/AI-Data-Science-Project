"""Daily health digest script for Imperial Cars AI."""
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from backend.app.utils.alerting import send_alert_email
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WATCHDOG_DB = PROJECT_ROOT / "data" / "logs" / "watchdog.db"
LOG_FILE = PROJECT_ROOT / "data" / "logs" / "watchdog.log"


def get_events_since(hours=24):
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    conn = sqlite3.connect(str(WATCHDOG_DB))
    rows = conn.execute(
        "SELECT timestamp, event_type, heartbeat_age_sec, http_ok, action_taken FROM watchdog_events WHERE timestamp >= ? ORDER BY timestamp DESC",
        (since,)
    ).fetchall()
    conn.close()
    return rows

def get_log_tail(lines=40):
    if not LOG_FILE.exists():
        return "(No log file)"
    with open(LOG_FILE, "r") as f:
        return "".join(f.readlines()[-lines:])

def main():
    events = get_events_since(24)
    log_tail = get_log_tail(40)
    body = f"""
Imperial Cars AI — Daily Health Digest ({datetime.now(timezone.utc).isoformat()})

Recent Watchdog Events (last 24h):\n"""
    for ts, et, age, http, action in events:
        body += f"- {ts}: {et} (age={age:.0f}s, http_ok={http}, action={action})\n"
    body += f"\nRecent Watchdog Log (last 40 lines):\n{log_tail}\n"
    send_alert_email("Imperial AI Daily Health Digest", body)

if __name__ == "__main__":
    main()
