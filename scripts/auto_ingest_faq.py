import os
import requests
import time
from pathlib import Path

DATA_DIR = Path("data")
LOG_PATH = DATA_DIR / "logs" / "auto_ingest.log"
BITEXT_PATH = DATA_DIR / "bitext_automotive.txt"
WIKI_PATH = DATA_DIR / "wikipedia_cars.txt"
EPA_PATH = DATA_DIR / "epa_fuel_economy.csv"
GLOBAL_KNOWLEDGE_PATH = DATA_DIR / "global_car_knowledge.txt"

BITEXT_URL = "https://raw.githubusercontent.com/bitextdata/bitext-automotive-qa/main/bitext_automotive.txt"
EPA_URL = "https://www.fueleconomy.gov/feg/epadata/vehicles.csv"

# Helper: log progress

def log(msg):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    print(msg)

def download_file(url, dest):
    if Path(dest).exists():
        log(f"Already present: {dest}")
        return
    log(f"Downloading {url} -> {dest}")
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        log(f"Downloaded: {dest}")
    except requests.HTTPError as e:
        log(f"[WARNING] Failed to download {url}: {e}. Skipping this source.")
    except Exception as e:
        log(f"[ERROR] Unexpected error downloading {url}: {e}. Skipping this source.")

def scrape_wikipedia_cars(dest):
    # Placeholder: just log, as scraping Wikipedia is complex
    # In production, use Wikipedia API or BeautifulSoup
    if Path(dest).exists():
        log(f"Already present: {dest}")
        return
    log(f"[SKIP] Wikipedia scraping not implemented. Please add {dest} manually if needed.")
    with open(dest, "w", encoding="utf-8") as f:
        f.write("Wikipedia car makes/models placeholder.\n")

def combine_sources():
    log("Combining sources into global_car_knowledge.txt")
    with open(GLOBAL_KNOWLEDGE_PATH, "w", encoding="utf-8") as out:
        for src in [BITEXT_PATH, WIKI_PATH, EPA_PATH]:
            if Path(src).exists():
                with open(src, "r", encoding="utf-8", errors="ignore") as f:
                    out.write(f"\n# Source: {src}\n")
                    out.write(f.read())
            else:
                out.write(f"\n# Source missing: {src}\n")
    log(f"Wrote: {GLOBAL_KNOWLEDGE_PATH}")

def ingest_documents():
    log("Calling scripts/ingest_documents.py ...")
    code = os.system(f".\\.venv\\Scripts\\python.exe scripts/ingest_documents.py {GLOBAL_KNOWLEDGE_PATH}")
    log(f"Ingest script exited with code {code}")

def main():
    log("--- Starting auto_ingest_faq.py ---")
    download_file(BITEXT_URL, BITEXT_PATH)
    scrape_wikipedia_cars(WIKI_PATH)
    download_file(EPA_URL, EPA_PATH)
    combine_sources()
    ingest_documents()
    log("--- Done auto_ingest_faq.py ---")

if __name__ == "__main__":
    main()
