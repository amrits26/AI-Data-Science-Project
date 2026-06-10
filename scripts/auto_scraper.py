import time
import subprocess
from datetime import datetime
from pathlib import Path

LOG_PATH = Path("data/logs/auto_scraper.log")
SCRAPER = "scripts/inventory_scraper_v2.py"
INTERVAL = 600  # seconds (10 minutes)

def log(msg):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} {msg}\n")

def main():
    log("=== Auto Scraper Started ===")
    while True:
        try:
            log("Starting inventory scrape...")
            result = subprocess.run(
                ["python", SCRAPER],
                capture_output=True,
                text=True,
                timeout=600
            )
            log(f"Scrape finished. Return code: {result.returncode}")
            if result.stdout:
                log(f"STDOUT: {result.stdout.strip()}")
            if result.stderr:
                log(f"STDERR: {result.stderr.strip()}")
        except Exception as e:
            log(f"ERROR: {e}")
        log(f"Sleeping for {INTERVAL} seconds...")
        try:
            time.sleep(INTERVAL)
        except KeyboardInterrupt:
            log("=== Auto Scraper Stopped by user ===")
            break

if __name__ == "__main__":
    main()
