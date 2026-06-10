#!/usr/bin/env python
"""
Scrape Imperial Cars inventory and import into local database.

Required packages:
    pip install requests beautifulsoup4 sqlalchemy python-dotenv

Usage:
    python scripts/import_imperial_inventory.py
    python scripts/import_imperial_inventory.py --max-pages 3 --max-vehicles 100
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urljoin, urlparse, urlencode

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from backend.app.database.db import get_db_session
from backend.app.database.models import Car, MarketPrice

BASE_URL = "https://www.imperialcars.com/all-inventory/index.htm"
SITE_ROOT = "https://www.imperialcars.com"
BACKUP_CSV = os.path.join(PROJECT_ROOT, "data", "inventory_backup.csv")

logger = logging.getLogger("imperial_inventory_scraper")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


@dataclass
class ScrapeStats:
    pages_scraped: int = 0
    links_found: int = 0
    detail_scraped: int = 0
    inserted: int = 0
    updated: int = 0
    market_prices_created: int = 0
    errors: int = 0


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value)
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", "").replace("$", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value)
    match = re.search(r"-?\d+", text.replace(",", ""))
    if not match:
        return None
    try:
        return int(match.group(0))
    except Exception:
        return None


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _sleep(min_s: float, max_s: float) -> None:
    time.sleep(random.uniform(min_s, max_s))


def _request(session: requests.Session, url: str, retries: int = 3, timeout: int = 25,
             sleep_min: float = 1.0, sleep_max: float = 2.0) -> Optional[requests.Response]:
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            # Akamai sometimes serves an Access Denied HTML with HTTP 200.
            if "Access Denied" in response.text and "errors.edgesuite.net" in response.text:
                logger.warning("Blocked by upstream access protection for %s", url)
            _sleep(sleep_min, sleep_max)
            return response
        except Exception as exc:
            logger.warning("Request failed (%s/%s): %s | %s", attempt, retries, url, exc)
            _sleep(sleep_min, sleep_max)
    return None


def _request_post_json(
    session: requests.Session,
    url: str,
    payload: dict[str, Any],
    retries: int = 3,
    timeout: int = 25,
    sleep_min: float = 1.0,
    sleep_max: float = 2.0,
) -> Optional[requests.Response]:
    for attempt in range(1, retries + 1):
        try:
            response = session.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            _sleep(sleep_min, sleep_max)
            return response
        except Exception as exc:
            logger.warning("POST failed (%s/%s): %s | %s", attempt, retries, url, exc)
            _sleep(sleep_min, sleep_max)
    return None


def _parse_title(title: str) -> dict[str, Any]:
    # Example: 2018 Nissan Kicks S SUV
    text = _clean_text(title)
    out: dict[str, Any] = {"year": None, "make": None, "model": None, "trim": None}
    match = re.match(r"^(19|20)\d{2}\s+", text)
    if not match:
        return out

    parts = text.split()
    out["year"] = _safe_int(parts[0])
    if len(parts) >= 3:
        out["make"] = parts[1]
        out["model"] = parts[2]
    if len(parts) > 3:
        out["trim"] = " ".join(parts[3:])
    return out


def _extract_label_value(text_blob: str, label: str) -> Optional[str]:
    pattern = rf"{re.escape(label)}\s*[:\-]?\s*([^|\n\r]+)"
    match = re.search(pattern, text_blob, re.IGNORECASE)
    if match:
        return _clean_text(match.group(1))
    return None


def _extract_vehicle_links(soup: BeautifulSoup) -> list[str]:
    links: list[str] = []
    seen = set()

    # Primary selector candidates
    for selector in [
        "h2 a[href]",
        ".vehicle-card a[href]",
        ".inventory-listing a[href]",
        "a[href]",
    ]:
        for anchor in soup.select(selector):
            href = anchor.get("href")
            if not href:
                continue
            full = urljoin(SITE_ROOT, href)
            path = urlparse(full).path.lower()

            if not path.endswith(".htm"):
                continue
            if "/all-inventory/" in path or "/new-inventory/" in path or "/used-inventory/" in path:
                continue
            if "/used/" not in path and "/new/" not in path:
                continue
            if full in seen:
                continue

            seen.add(full)
            links.append(full)

        if links:
            break

    return links


def _extract_inventory_api_config(soup: BeautifulSoup) -> tuple[Optional[str], Optional[dict[str, Any]]]:
    html = str(soup)
    match = re.search(
        r'fetch\("(/api/widget/ws-inv-data/getInventory)".*?decodeURI\("([^"]+)"\)',
        html,
        re.DOTALL,
    )
    if not match:
        return None, None

    endpoint = urljoin(SITE_ROOT, match.group(1))
    try:
        payload = json.loads(unquote(match.group(2)))
        return endpoint, payload
    except Exception:
        return endpoint, None


def _api_attr(item: dict[str, Any], name: str) -> Optional[str]:
    for src_key in ["attributes", "highlightedAttributes"]:
        for entry in item.get(src_key, []) or []:
            if str(entry.get("name", "")).lower() == name.lower():
                return _clean_text(entry.get("value"))
    return None


def _api_price(item: dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    pricing = item.get("pricing") or {}
    dprice = pricing.get("dprice") or []

    buy_for = None
    total = None
    sticker = _safe_float(pricing.get("retailPrice"))

    for row in dprice:
        label = _clean_text(row.get("label")).lower()
        value = _safe_float(row.get("value"))
        if value is None:
            continue
        if "buy for" in label:
            buy_for = value
        elif "total price" in label:
            total = value
        elif "sticker" in label and sticker is None:
            sticker = value

    return buy_for or total or sticker, sticker


def _rows_from_inventory_api(
    session: requests.Session,
    soup: BeautifulSoup,
    current_url: str,
    sleep_min: float,
    sleep_max: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    endpoint, payload = _extract_inventory_api_config(soup)
    if not endpoint or payload is None:
        return [], {}

    query = parse_qs(urlparse(current_url).query)
    start = query.get("start", ["0"])[0]

    payload.setdefault("inventoryParameters", {})
    payload["inventoryParameters"]["start"] = str(start)

    response = _request_post_json(
        session,
        endpoint,
        payload=payload,
        sleep_min=sleep_min,
        sleep_max=sleep_max,
    )
    if not response:
        return [], {}

    try:
        data = response.json()
    except Exception:
        return [], {}

    inventory = data.get("inventory") or []
    page_info = data.get("pageInfo") or {}

    rows: list[dict[str, Any]] = []
    for item in inventory:
        price, msrp = _api_price(item)
        link = item.get("link")
        source_url = urljoin(SITE_ROOT, link) if link else None

        row = {
            "source_url": source_url,
            "vin": _clean_text(item.get("vin")) or None,
            "year": _safe_int(item.get("year")),
            "make": _clean_text(item.get("make")) or None,
            "model": _clean_text(item.get("model")) or None,
            "trim": _clean_text(item.get("trim")) or None,
            "price": price,
            "msrp": msrp,
            "mileage": _safe_int(_api_attr(item, "odometer")),
            "stock_number": _clean_text(item.get("stockNumber")) or _api_attr(item, "stockNumber"),
            "exterior_color": _api_attr(item, "exteriorColor"),
            "interior_color": _api_attr(item, "interiorColor"),
            "engine": _api_attr(item, "engine"),
            "transmission": _api_attr(item, "transmission"),
            "drivetrain": _api_attr(item, "normalDriveLine"),
            "mpg_city": None,
            "mpg_highway": None,
            "horsepower": None,
            "torque": None,
            "towing_capacity": None,
        }

        mpg = _api_attr(item, "fuelEconomy")
        if mpg:
            mpg_match = re.search(r"(\d+)\s*/\s*(\d+)", mpg)
            if mpg_match:
                row["mpg_city"] = _safe_float(mpg_match.group(1))
                row["mpg_highway"] = _safe_float(mpg_match.group(2))

        rows.append(row)

    return rows, page_info


def _extract_next_page(current_url: str, soup: BeautifulSoup) -> Optional[str]:
    # 1) explicit "Go to next page"
    next_link = soup.find("a", string=re.compile(r"Go to next page", re.IGNORECASE))
    if next_link and next_link.get("href"):
        return urljoin(SITE_ROOT, next_link.get("href"))

    # 2) text-based fallback
    for anchor in soup.select("a[href]"):
        text = _clean_text(anchor.get_text(" ", strip=True)).lower()
        if text == "next" or "next page" in text:
            return urljoin(SITE_ROOT, anchor.get("href", ""))

    # 3) infer via ?start offset
    parsed = urlparse(current_url)
    query = parse_qs(parsed.query)
    start = int(query.get("start", [0])[0])
    next_start = start + 18

    query["start"] = [str(next_start)]
    next_query = urlencode({k: v[0] for k, v in query.items()})
    return f"{BASE_URL}?{next_query}" if next_query else None


def _parse_detail_page(detail_url: str, soup: BeautifulSoup) -> dict[str, Any]:
    text_blob = _clean_text(soup.get_text(" ", strip=True))

    title = ""
    header = soup.find(["h1", "h2"])
    if header:
        title = _clean_text(header.get_text(" ", strip=True))
    elif soup.title:
        title = _clean_text(soup.title.get_text(" ", strip=True))

    parsed_title = _parse_title(title)

    vin_match = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", text_blob)
    vin = vin_match.group(1) if vin_match else None

    mileage = None
    miles_match = re.search(r"(\d{1,3}(?:,\d{3})+|\d+)\s*miles", text_blob, re.IGNORECASE)
    if miles_match:
        mileage = _safe_int(miles_match.group(1))

    drivetrain = None
    for token in ["AWD", "4WD", "FWD", "RWD"]:
        if re.search(rf"\b{token}\b", text_blob):
            drivetrain = token
            break

    city = None
    highway = None
    mpg_match = re.search(r"(\d+)\s*city\s*/\s*(\d+)\s*hwy", text_blob, re.IGNORECASE)
    if mpg_match:
        city = _safe_float(mpg_match.group(1))
        highway = _safe_float(mpg_match.group(2))

    sticker = _safe_float(_extract_label_value(text_blob, "Sticker"))
    msrp = _safe_float(_extract_label_value(text_blob, "MSRP"))
    buy_for = _safe_float(_extract_label_value(text_blob, "Buy For"))
    total_price = _safe_float(_extract_label_value(text_blob, "Total Price"))

    return {
        "source_url": detail_url,
        "vin": vin,
        "year": parsed_title.get("year"),
        "make": parsed_title.get("make"),
        "model": parsed_title.get("model"),
        "trim": parsed_title.get("trim"),
        "price": buy_for or total_price or msrp or sticker,
        "msrp": msrp or sticker,
        "mileage": mileage,
        "stock_number": _extract_label_value(text_blob, "Stock") or _extract_label_value(text_blob, "Stock Number"),
        "exterior_color": _extract_label_value(text_blob, "Exterior Color"),
        "interior_color": _extract_label_value(text_blob, "Interior Color"),
        "engine": _extract_label_value(text_blob, "Engine"),
        "transmission": _extract_label_value(text_blob, "Transmission"),
        "drivetrain": drivetrain or _extract_label_value(text_blob, "Drivetrain"),
        "mpg_city": city,
        "mpg_highway": highway,
        "horsepower": _safe_int(_extract_label_value(text_blob, "Horsepower")),
        "torque": _safe_int(_extract_label_value(text_blob, "Torque")),
        "towing_capacity": _safe_int(_extract_label_value(text_blob, "Towing Capacity")),
    }


def _car_columns() -> set[str]:
    return {column.name for column in Car.__table__.columns}


def _to_car_kwargs(vehicle: dict[str, Any], columns: set[str]) -> dict[str, Any]:
    mapping = {
        "make": vehicle.get("make"),
        "model": vehicle.get("model"),
        "year": vehicle.get("year"),
        "trim": vehicle.get("trim"),
        "engine": vehicle.get("engine"),
        "horsepower": vehicle.get("horsepower"),
        "torque": vehicle.get("torque"),
        "mpg_city": vehicle.get("mpg_city"),
        "mpg_highway": vehicle.get("mpg_highway"),
        "transmission": vehicle.get("transmission"),
        "drivetrain": vehicle.get("drivetrain"),
        "msrp": vehicle.get("msrp") or vehicle.get("price"),
        "used_avg_price": vehicle.get("price"),
        "towing_capacity": vehicle.get("towing_capacity"),
        # optional columns only if present in schema
        "vin": vehicle.get("vin"),
        "mileage": vehicle.get("mileage"),
        "price": vehicle.get("price"),
        "stock_number": vehicle.get("stock_number"),
        "exterior_color": vehicle.get("exterior_color"),
        "interior_color": vehicle.get("interior_color"),
    }

    return {k: v for k, v in mapping.items() if k in columns and v is not None}


def _find_existing_car(db, vehicle: dict[str, Any], columns: set[str]) -> Optional[Car]:
    if "vin" in columns and vehicle.get("vin"):
        return db.query(Car).filter(getattr(Car, "vin") == vehicle["vin"]).first()

    filters = []
    if vehicle.get("year") is not None:
        filters.append(Car.year == vehicle["year"])
    if vehicle.get("make"):
        filters.append(Car.make == vehicle["make"])
    if vehicle.get("model"):
        filters.append(Car.model == vehicle["model"])
    if vehicle.get("trim"):
        filters.append(Car.trim == vehicle["trim"])

    if not filters:
        return None

    return db.query(Car).filter(and_(*filters)).first()


def _upsert_by_vin(db, vehicle: dict[str, Any], columns: set[str]) -> tuple[bool, Optional[int]]:
    """Dialect-aware upsert by VIN for PostgreSQL/SQLite.

    Returns:
        (was_update, car_id)
    """
    if "vin" not in columns or not vehicle.get("vin"):
        return False, None

    existing = db.query(Car).filter(getattr(Car, "vin") == vehicle["vin"]).first()
    was_update = existing is not None

    payload = _to_car_kwargs(vehicle, columns)
    if "vin" not in payload:
        payload["vin"] = vehicle.get("vin")

    update_fields = {
        field: payload[field]
        for field in ["price", "msrp", "used_avg_price", "mileage", "stock_number"]
        if field in payload and field in columns
    }

    if not payload.get("make") or not payload.get("model") or not payload.get("year"):
        if existing:
            # For updates, allow sparse payload as long as VIN exists.
            stmt_update_only = (
                pg_insert(Car.__table__) if db.bind.dialect.name == "postgresql" else sqlite_insert(Car.__table__)
            ).values(**payload)
            stmt_update_only = stmt_update_only.on_conflict_do_update(
                index_elements=["vin"],
                set_=update_fields,
            )
            db.execute(stmt_update_only)
            db.flush()
            return True, existing.id
        return False, None

    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        stmt = pg_insert(Car.__table__).values(**payload)
    else:
        stmt = sqlite_insert(Car.__table__).values(**payload)

    stmt = stmt.on_conflict_do_update(
        index_elements=["vin"],
        set_=update_fields,
    )
    db.execute(stmt)
    db.flush()

    car = db.query(Car).filter(getattr(Car, "vin") == vehicle["vin"]).first()
    return was_update, car.id if car else None


def _update_existing(existing: Car, vehicle: dict[str, Any], columns: set[str]) -> None:
    # Requirement: duplicate updates should target price/mileage/stock
    for field in ["price", "msrp", "used_avg_price", "mileage", "stock_number"]:
        if field in columns and vehicle.get(field) is not None:
            setattr(existing, field, vehicle[field])


def _write_market_price(db, car_id: int, price: Optional[float]) -> bool:
    if price is None:
        return False
    db.add(
        MarketPrice(
            car_id=car_id,
            date=date.today(),
            price=float(price),
            source="imperial_inventory_scrape",
        )
    )
    return True


def _write_csv_backup(rows: list[dict[str, Any]], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    columns = [
        "source_url", "vin", "year", "make", "model", "trim", "price", "msrp", "mileage",
        "stock_number", "exterior_color", "interior_color", "engine", "transmission", "drivetrain",
        "mpg_city", "mpg_highway", "horsepower", "torque", "towing_capacity",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in columns})


def scrape_imperial_inventory(
    start_url: str = BASE_URL,
    sleep_min: float = 1.0,
    sleep_max: float = 2.0,
    max_pages: Optional[int] = None,
    max_vehicles: Optional[int] = None,
) -> ScrapeStats:
    stats = ScrapeStats()

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; ImperialInventoryScraper/1.0)",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    visited_pages = set()
    seen_details = set()
    all_rows: list[dict[str, Any]] = []

    current_url = start_url
    while current_url and current_url not in visited_pages:
        if max_pages is not None and stats.pages_scraped >= max_pages:
            break

        visited_pages.add(current_url)
        response = _request(session, current_url, sleep_min=sleep_min, sleep_max=sleep_max)
        if not response:
            stats.errors += 1
            break

        if "Access Denied" in response.text and "errors.edgesuite.net" in response.text:
            logger.error(
                "Scraping blocked by site protection on %s. Try running from a trusted network or with approved access.",
                current_url,
            )
            stats.errors += 1
            break

        soup = BeautifulSoup(response.text, "html.parser")
        detail_links = _extract_vehicle_links(soup)
        api_rows: list[dict[str, Any]] = []
        page_info: dict[str, Any] = {}

        if not detail_links:
            api_rows, page_info = _rows_from_inventory_api(
                session=session,
                soup=soup,
                current_url=current_url,
                sleep_min=sleep_min,
                sleep_max=sleep_max,
            )

        page_new = 0
        stats.pages_scraped += 1

        if api_rows:
            for row in api_rows:
                if row.get("source_url") and row["source_url"] in seen_details:
                    continue
                if row.get("source_url"):
                    seen_details.add(row["source_url"])
                all_rows.append(row)
                page_new += 1
                stats.links_found += 1
                if max_vehicles is not None and len(all_rows) >= max_vehicles:
                    break
        else:
            for link in detail_links:
                if link in seen_details:
                    continue
                seen_details.add(link)
                stats.links_found += 1

                detail_response = _request(session, link, sleep_min=sleep_min, sleep_max=sleep_max)
                if not detail_response:
                    stats.errors += 1
                    continue

                detail_soup = BeautifulSoup(detail_response.text, "html.parser")
                row = _parse_detail_page(link, detail_soup)

                missing = [k for k in ["year", "make", "model", "price"] if not row.get(k)]
                if missing:
                    logger.warning("Missing fields %s for %s", ",".join(missing), link)

                all_rows.append(row)
                stats.detail_scraped += 1
                page_new += 1

                if max_vehicles is not None and len(all_rows) >= max_vehicles:
                    break

        logger.info("Scraped page %s, found %s new cars", stats.pages_scraped, page_new)

        if max_vehicles is not None and len(all_rows) >= max_vehicles:
            break

        if page_info:
            total_count = _safe_int(page_info.get("totalCount")) or 0
            page_size = _safe_int(page_info.get("pageSize")) or 18
            page_start = _safe_int(page_info.get("pageStart")) or 0
            next_start = page_start + page_size
            if next_start >= total_count:
                current_url = None
            else:
                current_url = f"{BASE_URL}?start={next_start}"
        else:
            current_url = _extract_next_page(current_url, soup)

    _write_csv_backup(all_rows, BACKUP_CSV)
    logger.info("Saved backup CSV: %s (%s rows)", BACKUP_CSV, len(all_rows))

    db = get_db_session()
    columns = _car_columns()

    try:
        for row in all_rows:
            used_upsert = False
            upsert_id = None

            if "vin" in columns and row.get("vin"):
                try:
                    was_update, upsert_id = _upsert_by_vin(db, row, columns)
                    used_upsert = upsert_id is not None
                    if used_upsert:
                        if was_update:
                            stats.updated += 1
                        else:
                            stats.inserted += 1
                        if _write_market_price(db, upsert_id, row.get("price") or row.get("msrp")):
                            stats.market_prices_created += 1
                        continue
                except Exception as exc:
                    logger.warning("VIN upsert failed, falling back to ORM update/insert: %s", exc)

            existing = _find_existing_car(db, row, columns)

            if existing:
                _update_existing(existing, row, columns)
                db.flush()
                stats.updated += 1

                if _write_market_price(db, existing.id, row.get("price") or row.get("msrp")):
                    stats.market_prices_created += 1
                continue

            kwargs = _to_car_kwargs(row, columns)
            if not kwargs.get("make") or not kwargs.get("model") or not kwargs.get("year"):
                stats.errors += 1
                logger.warning("Skipping row without core identity fields: %s", row.get("source_url"))
                continue

            car = Car(**kwargs)
            db.add(car)
            db.flush()
            stats.inserted += 1

            if _write_market_price(db, car.id, row.get("price") or row.get("msrp")):
                stats.market_prices_created += 1

        db.commit()
    except Exception as exc:
        db.rollback()
        stats.errors += 1
        logger.exception("Import failed: %s", exc)
    finally:
        db.close()

    logger.info(
        "Complete. pages=%s links=%s details=%s inserted=%s updated=%s market_prices=%s errors=%s",
        stats.pages_scraped,
        stats.links_found,
        stats.detail_scraped,
        stats.inserted,
        stats.updated,
        stats.market_prices_created,
        stats.errors,
    )

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Imperial Cars inventory and import to database")
    parser.add_argument("--url", default=BASE_URL, help="Inventory listing URL")
    parser.add_argument("--sleep-min", type=float, default=1.0, help="Minimum delay between requests")
    parser.add_argument("--sleep-max", type=float, default=2.0, help="Maximum delay between requests")
    parser.add_argument("--max-pages", type=int, default=None, help="Max listing pages to scrape")
    parser.add_argument("--max-vehicles", type=int, default=None, help="Max vehicle detail pages to scrape")
    args = parser.parse_args()

    scrape_imperial_inventory(
        start_url=args.url,
        sleep_min=args.sleep_min,
        sleep_max=args.sleep_max,
        max_pages=args.max_pages,
        max_vehicles=args.max_vehicles,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
