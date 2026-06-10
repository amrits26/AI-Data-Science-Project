"""
Inventory Scraper v2 for Imperial Cars
- Uses Playwright (headless Chromium)
- Extracts all vehicle data and Carfax links from imperialcars.com
- Syncs to SQLite database, marks sold vehicles
"""
import asyncio
from playwright.async_api import async_playwright
import sqlite3
import re
from datetime import datetime

DB_PATH = "./data/imperial_cars.db"
BASE_URL = "https://www.imperialcars.com/inventory"

async def scrape_inventory():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(BASE_URL)
        await page.wait_for_selector(".vehicle-card")
        vehicles = []
        cards = await page.query_selector_all(".vehicle-card")
        for card in cards:
            title = await card.query_selector_eval(".vehicle-title", "el => el.textContent")
            price = await card.query_selector_eval(".vehicle-price", "el => el.textContent")
            stock = await card.query_selector_eval(".stock-number", "el => el.textContent")
            carfax_link = await card.query_selector_eval("a[href*='carfax']", "el => el.href")
            status = await card.query_selector_eval(".status", "el => el.textContent") if await card.query_selector(".status") else "Available"
            vehicles.append({
                "title": title.strip() if title else None,
                "price": price.strip() if price else None,
                "stock": re.sub(r"[^A-Z0-9]", "", stock or "").strip(),
                "carfax": carfax_link,
                "status": status.strip() if status else "Available"
            })
        await browser.close()
        return vehicles

def sync_to_db(vehicles):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            stock TEXT PRIMARY KEY,
            title TEXT,
            price TEXT,
            carfax TEXT,
            status TEXT,
            last_seen TIMESTAMP
        )
    """)
    seen_stocks = set()
    for v in vehicles:
        seen_stocks.add(v["stock"])
        c.execute("""
            INSERT OR REPLACE INTO vehicles (stock, title, price, carfax, status, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (v["stock"], v["title"], v["price"], v["carfax"], v["status"], datetime.utcnow()))
    # Mark vehicles not seen as sold
    c.execute("SELECT stock FROM vehicles")
    for (stock,) in c.fetchall():
        if stock not in seen_stocks:
            c.execute("UPDATE vehicles SET status='Sold', last_seen=? WHERE stock=?", (datetime.utcnow(), stock))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    vehicles = asyncio.run(scrape_inventory())
    sync_to_db(vehicles)
    print(f"Synced {len(vehicles)} vehicles.")
