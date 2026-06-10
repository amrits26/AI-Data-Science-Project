#!/usr/bin/env python3
"""Imperial Cars AI Watchdog — detects and recovers from backend failures."""
import os, sys, time, subprocess, sqlite3, json
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HEARTBEAT_FILE = PROJECT_ROOT / "data" / "logs" / "heartbeat.txt"
WATCHDOG_DB = PROJECT_ROOT / "data" / "logs" / "watchdog.db"
MAX_HEARTBEAT_AGE = 120        # seconds — backend must update every 30s
BACKEND_PORT = int(os.getenv("WATCHDOG_BACKEND_PORT", "8081"))
MAX_RESTART_ATTEMPTS = 3
RESTART_COOLDOWN = 300         # 5 minutes

LOG_FILE = PROJECT_ROOT / "data" / "logs" / "watchdog.log"

def log(msg: str):
    entry = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(entry)
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")

def get_heartbeat_age() -> float | None:
    if not HEARTBEAT_FILE.exists():
        return None
    try:
        last_beat = float(HEARTBEAT_FILE.read_text().strip())
        return time.time() - last_beat
    except (ValueError, OSError):
        return None

def http_health_check() -> bool:
    import urllib.request
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{BACKEND_PORT}/api/health",
            headers={"User-Agent": "Imperial-Watchdog/1.0"}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return data.get("status") in ("ok", "degraded")
    except Exception:
        return False

def restart_backend():
    log("Restarting backend...")
    venv_python = str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe")
    subprocess.Popen(
        [venv_python, "-m", "uvicorn", "backend.app.main:app",
         "--host", "0.0.0.0", "--port", str(BACKEND_PORT)],
        cwd=str(PROJECT_ROOT),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )

def record_event(event_type, heartbeat_age, http_ok, action_taken):
    WATCHDOG_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(WATCHDOG_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watchdog_events (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            event_type TEXT,
            heartbeat_age_sec REAL,
            http_ok INTEGER,
            action_taken TEXT
        );
    """)
    conn.execute(
        "INSERT INTO watchdog_events (timestamp, event_type, heartbeat_age_sec, http_ok, action_taken) VALUES (?, ?, ?, ?, ?)",
        (datetime.now(timezone.utc).isoformat(), event_type, heartbeat_age, int(http_ok), action_taken)
    )
    conn.commit()
    conn.close()

def check_and_recover():
    age = get_heartbeat_age()
    http_ok = http_health_check()
    action = "none"
    event_type = "all_ok"
    if age is None:
        log("No heartbeat file found. Backend may not have started yet.")
        event_type = "heartbeat_missing"
        action = "none"
    elif age > MAX_HEARTBEAT_AGE and not http_ok:
        log(f"CRITICAL: Heartbeat stale ({age:.0f}s) and HTTP health check failed. Restarting backend.")
        restart_backend()
        event_type = "restart"
        action = "restart"
    elif age > MAX_HEARTBEAT_AGE:
        log(f"WARNING: Heartbeat stale ({age:.0f}s) but HTTP health check passed. Backend may be slow.")
        event_type = "heartbeat_stale"
        action = "warn"
    elif not http_ok:
        log("WARNING: Heartbeat OK but HTTP health check failed. Possible port binding issue.")
        event_type = "http_fail"
        action = "warn"
    else:
        log("All good: heartbeat and HTTP health check passed.")
        event_type = "all_ok"
        action = "none"
    record_event(event_type, age if age is not None else -1, http_ok, action)

if __name__ == "__main__":
    log("Watchdog started.")
    check_and_recover()
