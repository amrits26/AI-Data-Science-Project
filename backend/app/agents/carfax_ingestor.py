"""
Carfax-like Vehicle History Ingestion.

Integrates:
- PDF parsing (extract VIN, owner history, service records)
- NHTSA VIN lookup (for spec verification)
- CSV bulk import (dealer-exported Carfax/history data)
- Local database storage (carfax_records table)
"""

import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any

from backend.app.database import get_db_session, CarfaxRecord
from backend.app.agents.nhtsa_api import decode_vin

_VIN_CACHE: dict[str, dict[str, Any]] = {}
_VIN_CACHE_TTL = timedelta(hours=12)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _cache_get(vin: str) -> dict[str, Any] | None:
    key = vin.strip().upper()
    item = _VIN_CACHE.get(key)
    if not item:
        return None
    if _now_utc() - item["cached_at"] > _VIN_CACHE_TTL:
        _VIN_CACHE.pop(key, None)
        return None
    return dict(item["payload"])


def _cache_set(vin: str, payload: dict[str, Any]) -> None:
    _VIN_CACHE[vin.strip().upper()] = {"cached_at": _now_utc(), "payload": dict(payload)}


def _extract_carfax_fields(text: str) -> dict[str, Any]:
    vin_match = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", text, re.I)
    vin = vin_match.group(1).upper() if vin_match else ""

    accident_match = re.search(r"(\d+)\s*(?:reported\s+)?accident", text, re.I)
    accident_count = int(accident_match.group(1)) if accident_match else 0

    owner_match = re.search(r"(\d+)\s*(?:owner|owners|previous\s+owner)", text, re.I)
    owner_count = int(owner_match.group(1)) if owner_match else 0

    service_records = []
    for date_text, service_type in re.findall(r"(\d{1,2}/\d{1,2}/\d{2,4}).{0,120}?(service|maintenance|repair|inspection)", text, re.I):
        service_records.append({"date": date_text, "type": service_type.lower()})

    odo_match = re.search(r"(?:odometer|mileage)\s*[:#-]?\s*([0-9,]{3,7})", text, re.I)
    last_odometer = int(odo_match.group(1).replace(",", "")) if odo_match else None

    service_date_match = re.search(r"(?:last\s+service|service\s+date)\s*[:#-]?\s*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
    if not service_date_match and service_records:
        service_date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", service_records[-1]["date"])
    last_service_date = service_date_match.group(1) if service_date_match else None

    title_hits = []
    title_terms = ["salvage", "rebuilt", "flood", "lemon", "junk", "not actual mileage", "total loss"]
    lower = text.lower()
    for term in title_terms:
        if term in lower:
            title_hits.append(term)

    return {
        "vin": vin,
        "accident_count": accident_count,
        "owner_count": owner_count,
        "last_service_date": last_service_date,
        "service_records": service_records,
        "last_odometer_reading": last_odometer,
        "title_issues": title_hits,
    }


def parse_carfax_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Extract vehicle history from Carfax PDF.

    Uses pypdf to extract text, then regex to find VIN and parse history.

    Args:
        pdf_path: Path to Carfax PDF file

    Returns:
        {
            "status": "ok" | "error",
            "vin": str,
            "accident_count": int,
            "owner_count": int,
            "service_records": list,
            "error": str (if applicable),
        }
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return {"status": "error", "error": f"PDF not found: {pdf_path}"}

    try:
        from pypdf import PdfReader
    except ImportError:
        return {"status": "error", "error": "pypdf not installed. Run: pip install pypdf"}

    try:
        reader = PdfReader(pdf_path)
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        if not text.strip():
            return {"status": "error", "error": "Unable to extract text from PDF"}

        extracted = _extract_carfax_fields(text)
        vin = extracted.get("vin", "")
        if not vin:
            return {"status": "error", "error": "VIN not found in PDF"}

        vin_data = decode_vin(vin)
        return {
            "status": "ok",
            "vin": vin,
            "year": vin_data.get("year"),
            "make": vin_data.get("make"),
            "model": vin_data.get("model"),
            "accident_count": extracted.get("accident_count", 0),
            "owner_count": extracted.get("owner_count", 0),
            "last_service_date": extracted.get("last_service_date"),
            "service_records": extracted.get("service_records", []),
            "last_odometer_reading": extracted.get("last_odometer_reading"),
            "title_issues": extracted.get("title_issues", []),
            "raw_text": text[:2000],
        }

    except Exception as e:
        return {"status": "error", "error": f"PDF parsing failed: {str(e)}"}


def parse_carfax_pdf_bytes(content: bytes, filename: str = "carfax.pdf") -> Dict[str, Any]:
    if not content:
        return {"status": "error", "error": "Uploaded PDF is empty"}

    suffix = Path(filename).suffix.lower() or ".pdf"
    if suffix != ".pdf":
        return {"status": "error", "error": "Only PDF files are supported"}

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        return parse_carfax_pdf(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def import_carfax_csv(csv_path: str) -> Dict[str, Any]:
    """
    Bulk import vehicle history from dealer-exported CSV.

    CSV should have columns: VIN, AccidentCount, OwnerCount, LastServiceDate, Odometer, etc.

    Args:
        csv_path: Path to CSV file

    Returns:
        {
            "status": "ok" | "error",
            "imported": int,
            "failed": int,
            "error": str (if applicable),
        }
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return {"status": "error", "error": f"CSV not found: {csv_path}"}

    try:
        import pandas as pd
    except ImportError:
        return {"status": "error", "error": "pandas not installed"}

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return {"status": "error", "error": f"Failed to read CSV: {str(e)}"}

    db = get_db_session()
    imported = 0
    failed = 0

    try:
        for idx, row in df.iterrows():
            try:
                vin = str(row.get("VIN", "")).strip().upper()
                if not vin or len(vin) != 17:
                    failed += 1
                    continue

                # Check if already exists
                existing = db.query(CarfaxRecord).filter(CarfaxRecord.vin == vin).first()
                if existing:
                    failed += 1
                    continue

                # Create record
                record = CarfaxRecord(
                    vin=vin,
                    year=int(row.get("Year", 0)) or None,
                    make=str(row.get("Make", "")).strip() or None,
                    model=str(row.get("Model", "")).strip() or None,
                    accident_count=int(row.get("AccidentCount", 0)) or 0,
                    owner_count=int(row.get("OwnerCount", 0)) or 1,
                    last_service_date=pd.to_datetime(row.get("LastServiceDate"), errors="coerce") if row.get("LastServiceDate") else None,
                    odometer_miles=int(row.get("Odometer", 0)) or None,
                    title_status=str(row.get("TitleStatus", "")).strip() or None,
                    source="csv_import",
                    raw_data=row.to_dict(),
                )
                db.add(record)
                imported += 1

            except Exception as e:
                failed += 1
                continue

        db.commit()
        return {
            "status": "ok",
            "imported": imported,
            "failed": failed,
            "total": imported + failed,
        }

    except Exception as e:
        db.rollback()
        return {"status": "error", "error": f"Import failed: {str(e)}"}
    finally:
        db.close()


def lookup_vin_public(vin: str) -> Dict[str, Any]:
    """
    Look up VIN in local database first, then NHTSA if not found.

    Args:
        vin: 17-character VIN

    Returns:
        {
            "status": "ok" | "error",
            "vin": str,
            "year": int,
            "make": str,
            "model": str,
            "accident_count": int,
            "owner_count": int,
            "source": "local" | "nhtsa",
            ...
        }
    """
    vin = vin.upper().strip()
    if len(vin) != 17:
        return {"status": "error", "error": "VIN must be 17 characters"}

    cached = _cache_get(vin)
    if cached:
        cached["cache"] = "hit"
        return cached

    db = get_db_session()
    try:
        # Check local database
        record = db.query(CarfaxRecord).filter(CarfaxRecord.vin == vin).first()
        if record:
            payload = {
                "status": "ok",
                "vin": record.vin,
                "year": record.year,
                "make": record.make,
                "model": record.model,
                "accident_count": record.accident_count,
                "owner_count": record.owner_count,
                "last_service_date": record.last_service_date,
                "odometer_miles": record.odometer_miles,
                "title_status": record.title_status,
                "source": "local",
            }
            _cache_set(vin, payload)
            return payload

        # Not in local DB, try NHTSA
        vin_data = decode_vin(vin)
        if vin_data.get("status") == "ok":
            # Create a new record from NHTSA data
            new_record = CarfaxRecord(
                vin=vin,
                year=vin_data.get("year"),
                make=vin_data.get("make"),
                model=vin_data.get("model"),
                source="nhtsa",
                raw_data=vin_data.get("raw_data"),
            )
            db.add(new_record)
            db.commit()

            payload = {
                "status": "ok",
                "vin": vin,
                "year": vin_data.get("year"),
                "make": vin_data.get("make"),
                "model": vin_data.get("model"),
                "accident_count": 0,  # NHTSA doesn't provide this
                "owner_count": 0,
                "source": "nhtsa",
                "note": "Decoded from NHTSA; local history not available",
            }
            _cache_set(vin, payload)
            return payload

        return {"status": "error", "error": f"VIN {vin} not found"}

    finally:
        db.close()


def store_carfax_record(vin: str, data: Dict[str, Any]) -> bool:
    """Store or update carfax record in database."""
    db = get_db_session()
    try:
        existing = db.query(CarfaxRecord).filter(CarfaxRecord.vin == vin).first()

        if existing:
            # Update
            for key, value in data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
        else:
            # Create new
            record = CarfaxRecord(vin=vin, **data)
            db.add(record)

        db.commit()
        return True
    except Exception as e:
        print(f"Failed to store carfax record: {e}")
        db.rollback()
        return False
    finally:
        db.close()
