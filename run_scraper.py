from __future__ import annotations

import json

from backend.app.agents.inventory_scraper import run_inventory_scrape


if __name__ == "__main__":
    result = run_inventory_scrape()
    print(json.dumps(result, indent=2))
