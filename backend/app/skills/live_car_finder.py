from __future__ import annotations

import logging
import re
import time
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SKILL_NAME = "live_car_finder"
SKILL_DESCRIPTION = "Find live 2500-class trucks with heated seats on ImperialCars.com."
SKILL_PRIORITY = 85
SKILL_TRIGGERS = ["2500", "heated seats", "find a car", "imperialcars.com", "f-250", "ram 2500", "2500hd"]
SKILL_EMBEDDING = None

logger = logging.getLogger(__name__)


class LiveCarFinder:
    """Scrapes ImperialCars.com for 2500-class trucks with heated seats."""

    TARGET_URL = "https://www.imperialcars.com/chevrolet-ford-ram-trucks-mendon-ma.htm"
    BASE_URL = "https://www.imperialcars.com"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
    }
    REQUEST_TIMEOUT = 10
    MAX_RESULTS = 3
    CACHE_TTL_SECONDS = 300

    _cache_data: List[Dict[str, str]] = []
    _cache_timestamp: float = 0.0

    CAPABILITY_KEYWORDS = ("2500", "2500hd", "f-250", "ram 2500", "silverado 2500", "sierra 2500")
    HEATED_KEYWORDS = ("heated seat", "heated seats", "heated front seat", "heated steering wheel")

    @staticmethod
    def _normalize_detail_url(raw_url: str) -> str:
        url = (raw_url or "").strip()
        if not url:
            return ""
        if url.startswith("//"):
            url = f"https:{url}"
        elif not url.startswith("http"):
            url = urljoin(LiveCarFinder.BASE_URL + "/", url)
        return url

    @staticmethod
    def _is_imperial_detail_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.netloc or "").lower()
        if "imperialcars.com" not in host:
            return False
        path = (parsed.path or "").lower()
        return path.endswith(".htm") or "/used/" in path or "/new/" in path or "inventory" in path

    @staticmethod
    def _validate_url_live(url: str) -> bool:
        if not LiveCarFinder._is_imperial_detail_url(url):
            return False
        try:
            resp = requests.head(
                url,
                headers=LiveCarFinder.HEADERS,
                timeout=LiveCarFinder.REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            if resp.status_code >= 400 or resp.status_code == 405:
                resp = requests.get(
                    url,
                    headers=LiveCarFinder.HEADERS,
                    timeout=LiveCarFinder.REQUEST_TIMEOUT,
                    allow_redirects=True,
                )
            return resp.status_code < 400 and "imperialcars.com" in str(resp.url).lower()
        except Exception:
            return False

    @staticmethod
    def _extract_price(card: BeautifulSoup) -> str:
        price_selectors = [
            ".price",
            ".final-price",
            ".offer-price",
            ".vehicle-price",
            ".srp-vehicle__price",
            "[class*='price']",
        ]
        for selector in price_selectors:
            node = card.select_one(selector)
            if node:
                text = node.get_text(" ", strip=True)
                if text:
                    return text

        raw_text = card.get_text(" ", strip=True)
        price_match = re.search(r"\$\s?\d[\d,]*(?:\.\d{2})?", raw_text)
        if price_match:
            return price_match.group(0)
        return "Price not listed"

    @staticmethod
    def _extract_title(card: BeautifulSoup) -> str:
        for selector in (".title", ".vehicle-title", ".srp-vehicle__title", "h2", "h3", "h4"):
            node = card.select_one(selector)
            if node:
                text = node.get_text(" ", strip=True)
                if text:
                    return text
        link_node = card.select_one("a[href]")
        if link_node:
            text = link_node.get_text(" ", strip=True)
            if text:
                return text
        return ""

    @staticmethod
    def _extract_url(card: BeautifulSoup) -> str:
        for selector in ("a[href*='-'][href$='.htm']", "a[href*='/new/']", "a[href*='/used/']", "a[href]"):
            link = card.select_one(selector)
            if link and link.get("href"):
                return LiveCarFinder._normalize_detail_url(str(link.get("href")))
        return ""

    @staticmethod
    def _matches_requirement(title: str, body_text: str) -> bool:
        haystack_title = (title or "").lower()
        haystack_body = (body_text or "").lower()

        has_capability = any(k in haystack_title or k in haystack_body for k in LiveCarFinder.CAPABILITY_KEYWORDS)
        has_heated = any(k in haystack_body for k in LiveCarFinder.HEATED_KEYWORDS)
        return has_capability and has_heated

    @staticmethod
    def _candidate_cards(soup: BeautifulSoup) -> List[BeautifulSoup]:
        selectors = (
            ".vehicle-card",
            ".inventory-listing",
            ".car-card",
            ".srpVehicle",
            "article",
            ".vehicle",
            ".inventory-item",
            "[data-vehicle-id]",
        )
        cards: List[BeautifulSoup] = []
        for selector in selectors:
            cards.extend(soup.select(selector))

        if cards:
            return cards

        # Fallback: build pseudo-cards from anchors if no structured cards are found.
        fallback_cards: List[BeautifulSoup] = []
        for link in soup.select("a[href]"):
            href = str(link.get("href") or "")
            if ".htm" in href or "/new/" in href or "/used/" in href:
                parent = link.parent if link.parent else link
                fallback_cards.append(parent)
        return fallback_cards

    @staticmethod
    def find_heated_2500_trucks() -> List[Dict[str, str]]:
        """Return up to MAX_RESULTS matching vehicles or empty list when unavailable."""
        now = time.time()
        if LiveCarFinder._cache_data and (now - LiveCarFinder._cache_timestamp) < LiveCarFinder.CACHE_TTL_SECONDS:
            return list(LiveCarFinder._cache_data)

        try:
            resp = requests.get(
                LiveCarFinder.TARGET_URL,
                headers=LiveCarFinder.HEADERS,
                timeout=LiveCarFinder.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Live car finder scrape failed: %s", exc)
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        cards = LiveCarFinder._candidate_cards(soup)
        matches: List[Dict[str, str]] = []
        seen_urls: set[str] = set()

        for card in cards:
            title = LiveCarFinder._extract_title(card)
            body_text = card.get_text(" ", strip=True)
            if not title and not body_text:
                continue

            if not LiveCarFinder._matches_requirement(title, body_text):
                continue

            detail_url = LiveCarFinder._extract_url(card)
            if not detail_url or detail_url in seen_urls:
                continue
            if not LiveCarFinder._validate_url_live(detail_url):
                continue

            seen_urls.add(detail_url)
            matches.append(
                {
                    "title": title.strip() or "2500-Class Truck",
                    "price": LiveCarFinder._extract_price(card),
                    "url": detail_url,
                }
            )
            if len(matches) >= LiveCarFinder.MAX_RESULTS:
                break

        LiveCarFinder._cache_data = list(matches)
        LiveCarFinder._cache_timestamp = now

        return matches

    @staticmethod
    def fallback_message() -> str:
        return (
            "I cannot scrape ImperialCars.com due to access restrictions. "
            "Please use this direct link to browse their truck inventory and manually search each page "
            "for 'heated seats': https://www.imperialcars.com/chevrolet-ford-ram-trucks-mendon-ma.htm"
        )

    @staticmethod
    def format_customer_response(matches: List[Dict[str, str]]) -> str:
        if not matches:
            return LiveCarFinder.fallback_message()

        lines = ["I found these 2500-class trucks with heated seats on ImperialCars.com:", ""]
        for item in matches[: LiveCarFinder.MAX_RESULTS]:
            title = item.get("title") or "2500-Class Truck"
            price = item.get("price") or "Price not listed"
            url = item.get("url") or ""
            lines.append(f"- {title} - {price}")
            lines.append(f"  View: {url}")
            lines.append("")
        return "\n".join(lines).strip()


def execute(query: str, context: dict, session_id: str) -> dict:
    matches = LiveCarFinder.find_heated_2500_trucks()
    return {
        "answer": LiveCarFinder.format_customer_response(matches),
        "source": "live_car_finder",
        "question_type": "car_finder",
        "data": {"matches": matches, "count": len(matches)},
    }
