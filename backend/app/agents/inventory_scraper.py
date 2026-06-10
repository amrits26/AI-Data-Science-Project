"""Imperial Cars inventory scraper with near-live DB synchronization."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
from bs4 import BeautifulSoup

from backend.app.database.db import ensure_inventory_schema, get_db_session
from backend.app.database.models import Car

DEFAULT_BASE_URL = os.getenv("IMPERIAL_CARS_WEBSITE", "https://www.imperialcars.com").rstrip("/")
DEFAULT_USER_AGENT = "ImperialCarsInventoryBot/2.0 (+inventory-sync)"
REQUEST_TIMEOUT = int(os.getenv("SCRAPER_REQUEST_TIMEOUT", "20"))
REQUEST_DELAY_SECONDS = float(os.getenv("SCRAPER_REQUEST_DELAY_SECONDS", "1.0"))
MAX_PAGES = int(os.getenv("SCRAPER_MAX_PAGES", "20"))

INVENTORY_COLUMNS = [
    "stock_number",
    "make",
    "model",
    "year",
    "trim",
    "vin",
    "mileage",
    "price",
    "color",
    "transmission",
    "drivetrain",
    "engine",
    "photos",
    "carfax_link",
    "days_on_lot",
    "detail_url",
    "scraped_at",
]


@dataclass
class ScraperResult:
    status: str
    message: str
    csv_path: str
    rows: int
    pages_crawled: int
    inserted: int
    updated: int
    sold_marked: int


def _data_dir() -> str:
    data_dir = os.getenv("DATA_DIR", "./data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _inventory_csv_path() -> str:
    return os.path.join(_data_dir(), "inventory.csv")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": DEFAULT_USER_AGENT})
    return s


def _can_fetch(base_url: str, user_agent: str = DEFAULT_USER_AGENT) -> bool:
    robots_url = urljoin(base_url + "/", "robots.txt")
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch(user_agent, base_url + "/")
    except Exception:
        return True


def _get_html(session: requests.Session, url: str) -> str:
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return resp.text


def _extract_text(node, selector: str) -> str:
    found = node.select_one(selector)
    return found.get_text(" ", strip=True) if found else ""


def _extract_price(text: str) -> float | None:
    clean = re.sub(r"[^0-9.]", "", text or "")
    if not clean:
        return None
    try:
        return float(clean)
    except Exception:
        return None


def _extract_int(text: str) -> int | None:
    clean = re.sub(r"[^0-9]", "", text or "")
    if not clean:
        return None
    try:
        return int(clean)
    except Exception:
        return None


def _derive_make_model_year(title: str) -> tuple[int | None, str, str, str]:
    parts = (title or "").split()
    year = None
    make = ""
    model = ""
    trim = ""
    if parts and re.fullmatch(r"\d{4}", parts[0]):
        year = int(parts[0])
        if len(parts) > 1:
            make = parts[1]
        if len(parts) > 2:
            model = parts[2]
        if len(parts) > 3:
            trim = " ".join(parts[3:])
    return year, make, model, trim


def _parse_listing_cards(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("article, .vehicle, .inventory-item, .srpVehicle")
    rows: list[dict] = []
    for card in cards:
        title = _extract_text(card, "h2, h3, .vehicle-title, .srp-vehicle__title")
        year, make, model, trim = _derive_make_model_year(title)

        link_node = card.select_one("a[href]")
        detail_url = urljoin(base_url, link_node["href"]) if link_node and link_node.get("href") else ""

        price_text = _extract_text(card, ".price, .vehicle-price, .srp-vehicle__price")
        mileage_text = _extract_text(card, ".mileage, .vehicle-mileage, .srp-vehicle__mileage")
        stock_text = _extract_text(card, ".stock, .stock-number, .srp-vehicle__stock")
        vin_text = _extract_text(card, ".vin, .srp-vehicle__vin")

        row = {
            "stock_number": re.sub(r"(?i)^stock\s*#?:?\s*", "", stock_text).strip() or "",
            "make": make,
            "model": model,
            "year": year,
            "trim": trim,
            "vin": re.sub(r"(?i)^vin:?\s*", "", vin_text).strip() or "",
            "mileage": _extract_int(mileage_text),
            "price": _extract_price(price_text),
            "color": "",
            "transmission": "",
            "drivetrain": "",
            "engine": "",
            "photos": [],
            "carfax_link": "",
            "days_on_lot": None,
            "detail_url": detail_url,
            "scraped_at": datetime.utcnow().isoformat() + "Z",
        }
        if row["detail_url"]:
            rows.append(row)
    return rows


def _parse_detail_page(html: str, row: dict, base_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    spec_candidates = soup.select("li, .spec-item, .vehicle-spec")
    for item in spec_candidates:
        text = item.get_text(" ", strip=True)
        low = text.lower()
        if "transmission" in low and not row["transmission"]:
            row["transmission"] = text.split(":")[-1].strip()
        elif "drivetrain" in low and not row["drivetrain"]:
            row["drivetrain"] = text.split(":")[-1].strip()
        elif "engine" in low and not row["engine"]:
            row["engine"] = text.split(":")[-1].strip()
        elif "color" in low and not row["color"]:
            row["color"] = text.split(":")[-1].strip()

    full_text = soup.get_text(" ", strip=True)
    if not row["vin"]:
        m = re.search(r"\bVIN\s*:?\s*([A-HJ-NPR-Z0-9]{11,17})\b", full_text, flags=re.IGNORECASE)
        if m:
            row["vin"] = m.group(1)
    if not row["stock_number"]:
        m = re.search(r"\bStock\s*#?\s*:?\s*([A-Za-z0-9\-]+)\b", full_text, flags=re.IGNORECASE)
        if m:
            row["stock_number"] = m.group(1)

    photo_urls: list[str] = []
    for img in soup.select("img[src]"):
        src = (img.get("src") or "").strip()
        if not src:
            continue
        if any(x in src.lower() for x in ["vehicle", "inventory", "cdn", "photos"]):
            photo_urls.append(urljoin(base_url, src))
    if photo_urls:
        row["photos"] = sorted(list(dict.fromkeys(photo_urls)))[:50]

    carfax_node = soup.select_one('a[href*="carfax" i], a[href*="car-fax" i]')
    if carfax_node and carfax_node.get("href"):
        row["carfax_link"] = urljoin(base_url, carfax_node["href"])

    return row


def _discover_inventory_urls(base_url: str) -> list[str]:
    return [
        f"{base_url}/inventory",
        f"{base_url}/used-vehicles",
        f"{base_url}/new-vehicles",
    ]


def _scrape_website_rows(base_url: str) -> tuple[list[dict], int]:
    website = base_url.rstrip("/")
    if not _can_fetch(website):
        return [], 0

    session = _session()
    seed_urls = _discover_inventory_urls(website)
    rows: list[dict] = []
    pages_crawled = 0

    for seed in seed_urls:
        try:
            for page in range(MAX_PAGES):
                page_url = seed if page == 0 else f"{seed}?start={page * 18}"
                html = _get_html(session, page_url)
                listing_rows = _parse_listing_cards(html, website)
                if not listing_rows:
                    if page > 0:
                        break
                    continue
                rows.extend(listing_rows)
                pages_crawled += 1
        except Exception:
            continue

    dedup_map: dict[str, dict] = {}
    for row in rows:
        key = (row.get("vin") or "").strip().upper()
        if not key:
            key = (row.get("stock_number") or "").strip().upper()
        if not key:
            key = row.get("detail_url") or ""
        if key:
            dedup_map[key] = row

    final_rows = list(dedup_map.values())

    for row in final_rows:
        detail_url = row.get("detail_url")
        if not detail_url:
            continue
        try:
            detail_html = _get_html(session, detail_url)
            _parse_detail_page(detail_html, row, website)
        except Exception:
            continue

    return final_rows, pages_crawled


def _save_inventory_csv(rows: list[dict]) -> str:
    normalized: list[dict] = []
    for row in rows:
        out = {k: row.get(k) for k in INVENTORY_COLUMNS}
        out["photos"] = json.dumps(out.get("photos") or [], ensure_ascii=True)
        normalized.append(out)

    df = pd.DataFrame(normalized, columns=INVENTORY_COLUMNS)
    csv_path = _inventory_csv_path()
    df.to_csv(csv_path, index=False)
    return csv_path


def _match_key(vin: str | None, stock_number: str | None, detail_url: str | None) -> str:
    vin_key = (vin or "").strip().upper()
    if vin_key:
        return f"vin:{vin_key}"
    stock_key = (stock_number or "").strip().upper()
    if stock_key:
        return f"stock:{stock_key}"
    return f"url:{(detail_url or '').strip()}"


def _sync_rows_to_database(rows: list[dict]) -> tuple[int, int, int]:
    ensure_inventory_schema()
    db = get_db_session()
    now = datetime.utcnow()

    try:
        existing_rows = db.query(Car).all()
        existing_by_key: dict[str, Car] = {}
        for car in existing_rows:
            key = _match_key(car.vin, car.stock_number, car.detail_url)
            if key and key not in existing_by_key:
                existing_by_key[key] = car

        seen_keys: set[str] = set()
        inserted = 0
        updated = 0

        for row in rows:
            key = _match_key(row.get("vin"), row.get("stock_number"), row.get("detail_url"))
            if not key or key == "url:":
                continue
            seen_keys.add(key)

            car = existing_by_key.get(key)
            if car is None:
                car = Car(
                    make=row.get("make") or "",
                    model=row.get("model") or "",
                    year=row.get("year") or now.year,
                    trim=row.get("trim") or "",
                    vin=(row.get("vin") or "")[:32] or None,
                    stock_number=(row.get("stock_number") or "")[:64] or None,
                    detail_url=(row.get("detail_url") or "")[:500] or None,
                    color=(row.get("color") or "")[:50] or None,
                    mileage=row.get("mileage"),
                    msrp=row.get("price"),
                    carfax_url=(row.get("carfax_link") or "")[:500] or None,
                    available=True,
                    availability_status="available",
                    last_seen=now,
                    last_updated=now,
                )
                db.add(car)
                inserted += 1
            else:
                car.make = row.get("make") or car.make
                car.model = row.get("model") or car.model
                car.year = row.get("year") or car.year
                car.trim = row.get("trim") or car.trim
                car.vin = (row.get("vin") or car.vin or "")[:32] or None
                car.stock_number = (row.get("stock_number") or car.stock_number or "")[:64] or None
                car.detail_url = (row.get("detail_url") or car.detail_url or "")[:500] or None
                car.color = (row.get("color") or car.color or "")[:50] or None
                car.mileage = row.get("mileage") if row.get("mileage") is not None else car.mileage
                if row.get("price") is not None:
                    car.msrp = row.get("price")
                car.carfax_url = (row.get("carfax_link") or car.carfax_url or "")[:500] or None
                car.available = True
                car.availability_status = "available"
                car.last_seen = now
                car.last_updated = now
                updated += 1

        sold_marked = 0
        for car in existing_rows:
            key = _match_key(car.vin, car.stock_number, car.detail_url)
            if key and key not in seen_keys and car.available:
                car.available = False
                car.availability_status = "sold"
                car.last_updated = now
                sold_marked += 1

        db.commit()
        return inserted, updated, sold_marked
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_detail_url_live(detail_url: str | None, timeout: int = 10) -> dict:
    """Perform a lightweight live availability check against the detail page URL."""
    if not detail_url:
        return {"status": "unknown", "reason": "missing_detail_url", "http_status": None}

    try:
        session = _session()
        resp = session.head(detail_url, timeout=timeout, allow_redirects=True)
        if resp.status_code == 405:
            resp = session.get(detail_url, timeout=timeout, allow_redirects=True)
        if 200 <= resp.status_code < 400:
            return {"status": "available", "reason": "detail_page_live", "http_status": resp.status_code}
        if resp.status_code == 404:
            return {"status": "sold", "reason": "detail_page_missing", "http_status": resp.status_code}
        return {"status": "unknown", "reason": "unexpected_status", "http_status": resp.status_code}
    except Exception as exc:
        return {"status": "unknown", "reason": str(exc), "http_status": None}


def scrape_inventory(base_url: str | None = None) -> ScraperResult:
    website = (base_url or DEFAULT_BASE_URL).rstrip("/")
    if not _can_fetch(website):
        return ScraperResult(
            status="blocked",
            message="robots.txt policy disallows scraping this domain for configured user-agent",
            csv_path=_inventory_csv_path(),
            rows=0,
            pages_crawled=0,
            inserted=0,
            updated=0,
            sold_marked=0,
        )

    rows, pages_crawled = _scrape_website_rows(website)
    csv_path = _save_inventory_csv(rows)
    inserted, updated, sold_marked = _sync_rows_to_database(rows)

    return ScraperResult(
        status="ok",
        message=(
            f"Scraped {len(rows)} vehicles from {pages_crawled} pages. "
            f"Inserted={inserted}, Updated={updated}, SoldMarked={sold_marked}."
        ),
        csv_path=csv_path,
        rows=int(len(rows)),
        pages_crawled=pages_crawled,
        inserted=inserted,
        updated=updated,
        sold_marked=sold_marked,
    )


def run_inventory_scrape(base_url: str | None = None) -> dict:
    result = scrape_inventory(base_url=base_url)
    return {
        "status": result.status,
        "message": result.message,
        "csv_path": result.csv_path,
        "rows": result.rows,
        "pages_crawled": result.pages_crawled,
        "inserted": result.inserted,
        "updated": result.updated,
        "sold_marked": result.sold_marked,
        "base_url": (base_url or DEFAULT_BASE_URL),
        "scraped_at": datetime.utcnow().isoformat() + "Z",
    }
