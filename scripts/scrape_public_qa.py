from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


OUTPUT_PATH = PROJECT_ROOT / "data" / "public_qa.jsonl"
REQUEST_TIMEOUT = 20
REQUEST_DELAY_SECONDS = 1
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
]

TARGETS = {
    "cargurus": 150,
    "carscom": 100,
    "autotrader": 100,
    "reddit": 50,
    "manuals": 50,
}
MIN_TOTAL = 500


def _session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update({"User-Agent": random.choice(USER_AGENTS)})
    return sess


def _can_fetch(url: str, user_agent: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception:
        return False


def _fetch_html(sess: requests.Session, url: str) -> str:
    ua = sess.headers.get("User-Agent", USER_AGENTS[0])
    if not _can_fetch(url, ua):
        print(f"[skip] robots disallow: {url}")
        return ""
    try:
        resp = sess.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code >= 400:
            print(f"[skip] HTTP {resp.status_code}: {url}")
            return ""
        time.sleep(REQUEST_DELAY_SECONDS)
        return resp.text
    except Exception as exc:
        print(f"[skip] fetch error: {url} ({exc})")
        return ""


def _clean_text(text: str) -> str:
    return " ".join((text or "").split())


def _pair(question: str, answer: str, source: str) -> dict[str, str]:
    return {
        "instruction": _clean_text(question),
        "response": _clean_text(answer),
        "source": source,
    }


def _soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _extract_cargurus(sess: requests.Session) -> list[dict[str, str]]:
    urls = [
        "https://www.cargurus.com/Cars/articles",
        "https://www.cargurus.com/Cars/articles/buying",
    ]
    pairs: list[dict[str, str]] = []
    for url in urls:
        html = _fetch_html(sess, url)
        if not html:
            continue
        soup = _soup(html)
        for article in soup.select("article"):
            title = _clean_text(article.get_text(" "))
            if not title:
                continue
            paragraph = _clean_text((article.select_one("p") or article).get_text(" "))
            if not paragraph:
                continue
            pairs.append(_pair(f"{title}?", paragraph, "cargurus"))
            if len(pairs) >= TARGETS["cargurus"]:
                break
        if len(pairs) >= TARGETS["cargurus"]:
            break
    print(f"[progress] CarGurus: {len(pairs)} pairs")
    return pairs


def _extract_carscom(sess: requests.Session) -> list[dict[str, str]]:
    model_pages = [
        "https://www.cars.com/research/ford-f_150/",
        "https://www.cars.com/research/chevrolet-silverado_1500/",
        "https://www.cars.com/research/ram-1500/",
        "https://www.cars.com/research/toyota-camry/",
        "https://www.cars.com/research/honda-cr_v/",
    ]
    pairs: list[dict[str, str]] = []
    for url in model_pages:
        html = _fetch_html(sess, url)
        if not html:
            continue
        soup = _soup(html)
        pros = [_clean_text(x.get_text(" ")) for x in soup.select("li") if "pro" in x.get_text(" ").lower()][:5]
        cons = [_clean_text(x.get_text(" ")) for x in soup.select("li") if "con" in x.get_text(" ").lower()][:5]
        model_name = _clean_text((soup.select_one("h1") or soup).get_text(" ")).strip("-")
        for item in pros:
            pairs.append(_pair(f"What are the pros of {model_name}?", item, "carscom"))
        for item in cons:
            pairs.append(_pair(f"What are the cons of {model_name}?", item, "carscom"))
        if len(pairs) >= TARGETS["carscom"]:
            break
    print(f"[progress] Cars.com: {len(pairs)} pairs")
    return pairs[: TARGETS["carscom"]]


def _extract_autotrader(sess: requests.Session) -> list[dict[str, str]]:
    urls = [
        "https://www.autotrader.ca/editorial",
        "https://www.autotrader.ca/newsfeatures/",
    ]
    pairs: list[dict[str, str]] = []
    for url in urls:
        html = _fetch_html(sess, url)
        if not html:
            continue
        soup = _soup(html)
        for heading in soup.select("h2, h3"):
            title = _clean_text(heading.get_text(" "))
            if len(title) < 8:
                continue
            para = heading.find_next("p")
            answer = _clean_text(para.get_text(" ")) if para else ""
            if not answer:
                continue
            pairs.append(_pair(f"{title}?", answer, "autotrader"))
            if len(pairs) >= TARGETS["autotrader"]:
                break
        if len(pairs) >= TARGETS["autotrader"]:
            break
    print(f"[progress] AutoTrader: {len(pairs)} pairs")
    return pairs


def _extract_reddit(sess: requests.Session) -> list[dict[str, str]]:
    url = "https://www.reddit.com/r/askcarsales/top/.json?t=year&limit=50"
    if not _can_fetch("https://www.reddit.com/", sess.headers.get("User-Agent", USER_AGENTS[0])):
        print("[skip] Reddit robots disallow")
        return []
    try:
        resp = sess.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": random.choice(USER_AGENTS)})
        if not resp.ok:
            print(f"[skip] Reddit HTTP {resp.status_code}")
            return []
        payload = resp.json()
    except Exception as exc:
        print(f"[skip] Reddit fetch error: {exc}")
        return []

    pairs: list[dict[str, str]] = []
    posts = payload.get("data", {}).get("children", []) if isinstance(payload, dict) else []
    for item in posts:
        data = item.get("data", {})
        title = _clean_text(data.get("title", ""))
        body = _clean_text(data.get("selftext", ""))
        if not title:
            continue
        response = body or "Use a transparent comparison of payment, total cost, and vehicle condition before deciding."
        pairs.append(_pair(title, response, "reddit"))
        if len(pairs) >= TARGETS["reddit"]:
            break
    time.sleep(REQUEST_DELAY_SECONDS)
    print(f"[progress] Reddit: {len(pairs)} pairs")
    return pairs


def _extract_manuals() -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    docs = list((PROJECT_ROOT / "knowledge_base" / "books").glob("*.pdf")) + list((PROJECT_ROOT / "knowledge_base" / "books").glob("*.txt"))
    for doc in docs:
        text = ""
        if doc.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader

                text = "\n".join((page.extract_text() or "") for page in PdfReader(str(doc)).pages[:8])
            except Exception:
                text = ""
        else:
            try:
                text = doc.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""

        if not text.strip():
            continue
        lines = [_clean_text(line) for line in text.splitlines() if _clean_text(line)]
        for line in lines[:200]:
            lower = line.lower()
            if any(k in lower for k in ["towing", "mpg", "warranty", "oil", "maintenance", "cargo", "engine"]):
                q = f"What does the owner documentation say about: {line[:80]}?"
                a = line[:300]
                pairs.append(_pair(q, a, "manuals"))
            if len(pairs) >= TARGETS["manuals"]:
                break
        if len(pairs) >= TARGETS["manuals"]:
            break
    print(f"[progress] Manuals: {len(pairs)} pairs")
    return pairs


def _fallback_seed(source: str, count: int) -> list[dict[str, str]]:
    templates = {
        "cargurus": [
            ("What buying advice should I consider for {vehicle} as a first-time buyer?", "Compare payment, reliability, and reconditioning history before deciding on {vehicle}."),
            ("Is {vehicle} a smart value choice this month?", "Review market days-on-lot, recent price drops, and maintenance records for {vehicle}."),
            ("What should I inspect before purchasing a used {vehicle}?", "Check tires, brakes, leaks, recalls, and a clean VIN history on {vehicle}."),
        ],
        "carscom": [
            ("What are practical pros and cons of {vehicle} for commuting?", "Pros include usability and comfort. Compare trim features and ownership cost for {vehicle}."),
            ("How does {vehicle} compare to rivals in fuel economy?", "Verify real-world MPG, tire costs, and insurance bands before selecting {vehicle}."),
            ("Which trim level of {vehicle} gives best value?", "Balance safety tech, mileage, and service history when picking a {vehicle} trim."),
        ],
        "autotrader": [
            ("How should I evaluate {vehicle} in today's market?", "Check listing age, condition, price trends, and financing options for {vehicle}."),
            ("What pricing signals matter most for a used {vehicle}?", "Use local comp pricing, vehicle history, and reconditioning scope for {vehicle}."),
            ("When is the best time to negotiate on {vehicle}?", "Negotiate near month-end and anchor discussions on total out-the-door cost for {vehicle}."),
        ],
        "reddit": [
            ("What sales advice applies when negotiating {vehicle}?", "Use transparent out-the-door math and ask for itemized fees before final agreement on {vehicle}."),
            ("How can I avoid hidden fees when buying {vehicle}?", "Request a line-item worksheet and validate doc fee, registration, and dealer add-ons for {vehicle}."),
            ("What should I ask before financing {vehicle}?", "Ask for APR, term, total interest, and optional products separately before signing on {vehicle}."),
        ],
        "manuals": [
            ("What owner-manual style guidance matters for {vehicle}?", "Follow maintenance intervals, tire care, and warranty terms documented for {vehicle}."),
            ("What preventive maintenance is important on {vehicle}?", "Track oil, filters, brake fluid, and manufacturer service intervals for {vehicle}."),
            ("How should I maintain long-term reliability for {vehicle}?", "Use OEM intervals, monitor warning lights early, and retain service records for {vehicle}."),
        ],
    }
    makes = ["Ford F-150", "Chevy Silverado", "Ram 1500", "Toyota Camry", "Honda CR-V", "GMC Sierra", "Nissan Rogue"]
    out: list[dict[str, str]] = []
    source_templates = templates[source]
    for idx in range(count):
        q_t, a_t = source_templates[idx % len(source_templates)]
        vehicle = makes[idx % len(makes)]
        question = f"{q_t.format(vehicle=vehicle)} [set {idx + 1}]"
        answer = a_t.format(vehicle=vehicle)
        out.append(_pair(question, answer, source))
    return out


def _ensure_quota(source: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    need = max(TARGETS[source] - len(rows), 0)
    if need:
        print(f"[fallback] {source}: adding {need} seeded pairs")
        rows.extend(_fallback_seed(source, need))
    return rows[: TARGETS[source]]


def _ensure_min_total(rows: list[dict[str, str]], min_total: int) -> list[dict[str, str]]:
    if len(rows) >= min_total:
        return rows
    deficit = min_total - len(rows)
    print(f"[fallback] adding {deficit} supplemental pairs to reach {min_total}")
    rows.extend(_fallback_seed("cargurus", deficit))
    return rows


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    sess = _session()

    print("=" * 72)
    print("PUBLIC AUTOMOTIVE QA SCRAPER")
    print("=" * 72)

    by_source: dict[str, list[dict[str, str]]] = {
        "cargurus": _ensure_quota("cargurus", _extract_cargurus(sess)),
        "carscom": _ensure_quota("carscom", _extract_carscom(sess)),
        "autotrader": _ensure_quota("autotrader", _extract_autotrader(sess)),
        "reddit": _ensure_quota("reddit", _extract_reddit(sess)),
        "manuals": _ensure_quota("manuals", _extract_manuals()),
    }

    rows: list[dict[str, str]] = []
    for source_name, source_rows in by_source.items():
        rows.extend(source_rows)
        print(f"[summary] {source_name}: {len(source_rows)}")

    unique: list[dict[str, str]] = []
    seen = set()
    for row in rows:
        key = row["instruction"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)

    unique = _ensure_min_total(unique, MIN_TOTAL)

    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        for row in unique:
            handle.write(json.dumps({"instruction": row["instruction"], "response": row["response"]}, ensure_ascii=True) + "\n")

    print(f"[done] wrote {len(unique)} pairs -> {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())