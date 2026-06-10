#!/usr/bin/env python3
"""Wrapper script to run Imperial inventory scraper once."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.agents.inventory_scraper import run_inventory_scrape


if __name__ == "__main__":
    result = run_inventory_scrape()
    print(result)
