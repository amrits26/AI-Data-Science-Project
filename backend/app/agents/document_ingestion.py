"""OCR + extraction pipeline for six dealership paper forms."""

from __future__ import annotations

import json
import os
import re
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import requests
from PIL import Image

from .image_utils import preprocess_image, validate_extracted_data

DOC_TYPES = ["lead", "insurance", "cleanup", "sold", "commission", "credit"]
logger = logging.getLogger(__name__)
_easyocr_reader = None


def _get_easyocr_reader():
    """Lazily initialize a shared EasyOCR reader instance."""
    global _easyocr_reader
    if _easyocr_reader is not None:
        return _easyocr_reader

    import easyocr

    _easyocr_reader = easyocr.Reader(["en"], verbose=False, gpu=False)
    return _easyocr_reader


def _get_data_dir() -> str:
    data_dir = os.getenv("DATA_DIR", "./data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _regex_match(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        cleaned = re.sub(r"[^0-9.\-]", "", str(value))
        return float(cleaned) if cleaned else None
    except Exception:
        return None


def extract_text_from_image(image_path: str) -> str:
    """
    Run Neural OCR (EasyOCR) for production-grade accuracy.
    
    EasyOCR provides superior accuracy vs Tesseract, especially for:
    - Handwritten forms
    - Poor quality scans
    - Multi-language documents
    
    Args:
        image_path: Path to image file
    
    Returns:
        Extracted text from image
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image path does not exist: {image_path}")

    try:
        reader = _get_easyocr_reader()
        results = reader.readtext(image_path, detail=0, paragraph=True)
        text = "\n".join(results) if results else ""
        
        logger.info("ocr_extract_success", extra={"image_path": image_path, "text_length": len(text)})
        return text
    
    except ImportError:
        logger.error("easyocr_not_installed", extra={"image_path": image_path})
        raise RuntimeError(
            "EasyOCR not installed. Install with: pip install easyocr"
        )
    except Exception as exc:
        logger.error("ocr_extract_failed", extra={"image_path": image_path, "error": str(exc)})
        raise RuntimeError(
            f"OCR failed with EasyOCR: {exc}"
        ) from exc


def call_ollama(prompt: str, text: str) -> dict[str, Any]:
    """Call local Ollama and parse JSON response. Returns {} on failure."""
    model = os.getenv("OLLAMA_MODEL", "llama3")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    endpoint = f"{base_url}/api/generate"

    combined_prompt = (
        "Return only valid JSON with no markdown, no explanation.\n\n"
        f"{prompt}\n\n"
        f"OCR TEXT:\n{text[:10000]}"
    )

    try:
        response = requests.post(
            endpoint,
            json={"model": model, "prompt": combined_prompt, "stream": False},
            timeout=90,
        )
        response.raise_for_status()
        payload = response.json()
        parsed = _extract_json_object(str(payload.get("response", "")))
        return parsed or {}
    except Exception as exc:
        logger.warning("ollama_document_parse_failed", extra={"error": str(exc)})
        return {}


def parse_with_llm(text: str, prompt: str) -> dict[str, Any]:
    """Backward-compatible alias for call_ollama."""
    return call_ollama(prompt=prompt, text=text)


def _append_row(csv_name: str, row: dict[str, Any]) -> str:
    data_dir = _get_data_dir()
    csv_path = os.path.join(data_dir, csv_name)

    serialized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (list, dict)):
            serialized[key] = json.dumps(value, ensure_ascii=True)
        else:
            serialized[key] = value

    new_df = pd.DataFrame([serialized])
    if os.path.exists(csv_path):
        old = pd.read_csv(csv_path)
        out = pd.concat([old, new_df], ignore_index=True)
    else:
        out = new_df
    out.to_csv(csv_path, index=False)
    return csv_path


def _lead_regex(text: str) -> dict[str, Any]:
    t = _normalize(text)
    return {
        "customer_name": _regex_match(t, r"(?:customer|name)\s*[:\-]?\s*([A-Za-z .'-]{2,80})"),
        "phone": _regex_match(t, r"(?:phone|home phone|cell phone)\s*[:\-]?\s*(\+?[0-9()\-\s]{7,})"),
        "email": _regex_match(t, r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"),
        "vehicle_interest": _regex_match(t, r"(?:vehicle interest|vehicle|car)\s*[:\-]?\s*([A-Za-z0-9 .\-]{2,80})"),
        "trade_in_make": _regex_match(t, r"(?:trade\s*in\s*make|trade make)\s*[:\-]?\s*([A-Za-z0-9 .\-]{2,40})"),
        "trade_in_model": _regex_match(t, r"(?:trade\s*in\s*model|trade model)\s*[:\-]?\s*([A-Za-z0-9 .\-]{2,40})"),
        "sale_price": _to_float(_regex_match(t, r"(?:sale price)\s*[:\-]?\s*\$?([0-9,]+(?:\.[0-9]+)?)")),
        "deposit": _to_float(_regex_match(t, r"(?:deposit)\s*[:\-]?\s*\$?([0-9,]+(?:\.[0-9]+)?)")),
        "trade_in_allowance": _to_float(_regex_match(t, r"(?:trade\s*in\s*allowance)\s*[:\-]?\s*\$?([0-9,]+(?:\.[0-9]+)?)")),
    }


def _insurance_regex(text: str) -> dict[str, Any]:
    t = _normalize(text)
    return {
        "policy_holder_name": _regex_match(t, r"(?:policy holder|insured name|name)\s*[:\-]?\s*([A-Za-z .'-]{2,80})"),
        "insurance_company": _regex_match(t, r"(?:insurance company|carrier)\s*[:\-]?\s*([A-Za-z0-9 .&'-]{2,80})"),
        "policy_number": _regex_match(t, r"(?:policy number|policy #)\s*[:\-]?\s*([A-Za-z0-9\-]{4,40})"),
        "effective_date": _regex_match(t, r"(?:effective date)\s*[:\-]?\s*([0-9/\-]{6,20})"),
        "expiration_date": _regex_match(t, r"(?:expiration date|expiry date)\s*[:\-]?\s*([0-9/\-]{6,20})"),
        "vin": _regex_match(t, r"(?:vin)\s*[:\-]?\s*([A-HJ-NPR-Z0-9]{11,17})"),
        "agent_name": _regex_match(t, r"(?:agent name|agent)\s*[:\-]?\s*([A-Za-z .'-]{2,80})"),
        "agent_phone": _regex_match(t, r"(?:agent phone|agent contact)\s*[:\-]?\s*(\+?[0-9()\-\s]{7,})"),
    }


def _cleanup_regex(text: str) -> dict[str, Any]:
    t = _normalize(text)
    tasks = re.findall(r"(?:task|item|check)\s*[:\-]?\s*([A-Za-z0-9 .,'\-]{3,80})", text, flags=re.IGNORECASE)
    return {
        "stock_number": _regex_match(t, r"(?:stock number|stock #)\s*[:\-]?\s*([A-Za-z0-9\-]{2,40})"),
        "make_model": _regex_match(t, r"(?:make\/?model|vehicle)\s*[:\-]?\s*([A-Za-z0-9 .\-]{2,80})"),
        "delivery_date": _regex_match(t, r"(?:delivery date)\s*[:\-]?\s*([0-9/\-]{6,20})"),
        "manager_signature": _regex_match(t, r"(?:manager signature|manager)\s*[:\-]?\s*([A-Za-z .'-]{2,80})"),
        "comments": _regex_match(t, r"(?:comments|notes)\s*[:\-]?\s*([A-Za-z0-9 .,'\-]{3,200})"),
        "tasks": [x.strip() for x in tasks if x.strip()],
    }


def _sold_regex(text: str) -> dict[str, Any]:
    t = _normalize(text)
    return {
        "customer_name": _regex_match(t, r"(?:customer|name)\s*[:\-]?\s*([A-Za-z .'-]{2,80})"),
        "sale_date": _regex_match(t, r"(?:sale date)\s*[:\-]?\s*([0-9/\-]{6,20})"),
        "delivery_date": _regex_match(t, r"(?:delivery date)\s*[:\-]?\s*([0-9/\-]{6,20})"),
        "sales_person": _regex_match(t, r"(?:sales person|salesperson|sales rep)\s*[:\-]?\s*([A-Za-z .'-]{2,80})"),
        "year": _regex_match(t, r"(?:year)\s*[:\-]?\s*([0-9]{4})"),
        "make": _regex_match(t, r"(?:make)\s*[:\-]?\s*([A-Za-z0-9 .\-]{2,40})"),
        "model": _regex_match(t, r"(?:model)\s*[:\-]?\s*([A-Za-z0-9 .\-]{2,40})"),
        "stock_number": _regex_match(t, r"(?:stock number|stock #)\s*[:\-]?\s*([A-Za-z0-9\-]{2,40})"),
        "color": _regex_match(t, r"(?:color)\s*[:\-]?\s*([A-Za-z ]{2,40})"),
    }


def _commission_regex(text: str) -> dict[str, Any]:
    t = _normalize(text)
    deals: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if re.search(r"deal", line, flags=re.IGNORECASE) and re.search(r"\$", line):
            deals.append(
                {
                    "date": _regex_match(line, r"([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})"),
                    "deal_number": _regex_match(line, r"(?:deal\s*#?|deal number)\s*[:\-]?\s*([A-Za-z0-9\-]{1,30})"),
                    "customer_name": _regex_match(line, r"customer\s*[:\-]?\s*([A-Za-z .'-]{2,80})"),
                    "stock_number": _regex_match(line, r"(?:stock\s*#?|stock number)\s*[:\-]?\s*([A-Za-z0-9\-]{1,30})"),
                    "commission_amount": _to_float(_regex_match(line, r"\$\s*([0-9,]+(?:\.[0-9]+)?)")),
                }
            )

    return {
        "salesperson_name": _regex_match(t, r"(?:salesperson|sales person|name)\s*[:\-]?\s*([A-Za-z .'-]{2,80})"),
        "week_ending": _regex_match(t, r"(?:week ending)\s*[:\-]?\s*([0-9/\-]{6,20})"),
        "deals": deals,
    }


def _credit_regex(text: str) -> dict[str, Any]:
    t = _normalize(text)
    return {
        "applicant_last_name": _regex_match(t, r"(?:last name|surname)\s*[:\-]?\s*([A-Za-z .'-]{2,60})"),
        "first_name": _regex_match(t, r"(?:first name)\s*[:\-]?\s*([A-Za-z .'-]{2,60})"),
        "ssn": _regex_match(t, r"(?:ssn|social security)\s*[:\-]?\s*([0-9\-]{9,11})"),
        "birth_date": _regex_match(t, r"(?:birth date|dob)\s*[:\-]?\s*([0-9/\-]{6,20})"),
        "address": _regex_match(t, r"(?:address)\s*[:\-]?\s*([A-Za-z0-9 .,'#\-]{6,160})"),
        "home_phone": _regex_match(t, r"(?:home phone)\s*[:\-]?\s*(\+?[0-9()\-\s]{7,})"),
        "cell_phone": _regex_match(t, r"(?:cell phone|mobile)\s*[:\-]?\s*(\+?[0-9()\-\s]{7,})"),
        "employer_name": _regex_match(t, r"(?:employer name|employer)\s*[:\-]?\s*([A-Za-z0-9 .&'\-]{2,100})"),
        "salary": _to_float(_regex_match(t, r"(?:salary|income)\s*[:\-]?\s*\$?([0-9,]+(?:\.[0-9]+)?)")),
        "signature_date": _regex_match(t, r"(?:signature date|signed on|date)\s*[:\-]?\s*([0-9/\-]{6,20})"),
    }


def _extract_from_text(text: str, doc_type: str, llm_prompt: str, regex_fn: Callable[[str], dict[str, Any]], use_llm: bool = True) -> dict[str, Any]:
    llm_data = call_ollama(prompt=llm_prompt, text=text) if use_llm else {}
    regex_data = regex_fn(text)

    merged = dict(regex_data)
    for key, value in llm_data.items():
        if value in (None, "", [], {}):
            continue
        merged[key] = value

    merged.update(
        {
            "raw_text": text[:15000],
            "created_at": datetime.utcnow().isoformat() + "Z",
        }
    )
    return validate_extracted_data(merged, doc_type)


def extract_lead_info(image_or_text: str, use_llm: bool = True) -> dict[str, Any]:
    """If argument is a real path, OCR it. Otherwise treat argument as raw text."""
    prompt = (
        "Extract lead / purchase order fields as JSON: "
        "customer_name, phone, email, vehicle_interest, trade_in_make, trade_in_model, "
        "sale_price, deposit, trade_in_allowance"
    )
    if os.path.exists(image_or_text):
        text = extract_text_from_image(image_or_text)
        data = _extract_from_text(text, "lead", prompt, _lead_regex, use_llm=use_llm)
        data["source_image"] = os.path.basename(image_or_text)
        return data

    data = _extract_from_text(image_or_text, "lead", prompt, _lead_regex, use_llm=use_llm)
    data["source_image"] = "voice_or_text_input"
    return data


def extract_insurance_info(image_path: str) -> dict[str, Any]:
    text = extract_text_from_image(image_path)
    prompt = (
        "Extract insurance verification fields as JSON: policy_holder_name, insurance_company, "
        "policy_number, effective_date, expiration_date, vin, agent_name, agent_phone"
    )
    data = _extract_from_text(text, "insurance", prompt, _insurance_regex)
    data["source_image"] = os.path.basename(image_path)
    return data


def extract_cleanup_info(image_path: str) -> dict[str, Any]:
    text = extract_text_from_image(image_path)
    prompt = (
        "Extract delivery get ready / cleanup fields as JSON: stock_number, make_model, delivery_date, "
        "manager_signature, comments, tasks"
    )
    data = _extract_from_text(text, "cleanup", prompt, _cleanup_regex)
    data["source_image"] = os.path.basename(image_path)
    return data


def extract_sold_info(image_path: str) -> dict[str, Any]:
    text = extract_text_from_image(image_path)
    prompt = (
        "Extract sold tag fields as JSON: customer_name, sale_date, delivery_date, sales_person, year, make, model, stock_number, color"
    )
    data = _extract_from_text(text, "sold", prompt, _sold_regex)
    data["source_image"] = os.path.basename(image_path)
    return data


def extract_commission_info(image_path: str) -> dict[str, Any]:
    text = extract_text_from_image(image_path)
    prompt = (
        "Extract commission sheet as JSON: salesperson_name, week_ending, deals (list of date, deal_number, customer_name, stock_number, commission_amount)"
    )
    data = _extract_from_text(text, "commission", prompt, _commission_regex)
    data["source_image"] = os.path.basename(image_path)
    return data


def extract_credit_info(image_path: str) -> dict[str, Any]:
    text = extract_text_from_image(image_path)
    prompt = (
        "Extract credit application fields as JSON: applicant_last_name, first_name, ssn, birth_date, address, home_phone, cell_phone, employer_name, salary, signature_date"
    )
    data = _extract_from_text(text, "credit", prompt, _credit_regex)
    data["source_image"] = os.path.basename(image_path)
    return data


def process_lead_image_from_text(lead_data: dict[str, Any]) -> dict[str, Any]:
    validated = validate_extracted_data(dict(lead_data), "lead")
    saved_to = _append_row("leads.csv", validated)
    return {"status": "ok", "doc_type": "lead", "saved_to": saved_to, "data": validated}


def process_lead_image(image_path: str) -> dict[str, Any]:
    data = extract_lead_info(image_path, use_llm=True)
    data = validate_extracted_data(data, "lead")
    saved_to = _append_row("leads.csv", data)
    return {"status": "ok", "doc_type": "lead", "saved_to": saved_to, "data": data}


def process_insurance_image(image_path: str) -> dict[str, Any]:
    data = extract_insurance_info(image_path)
    data = validate_extracted_data(data, "insurance")
    saved_to = _append_row("insurance.csv", data)
    return {"status": "ok", "doc_type": "insurance", "saved_to": saved_to, "data": data}


def process_cleanup_image(image_path: str) -> dict[str, Any]:
    data = extract_cleanup_info(image_path)
    data = validate_extracted_data(data, "cleanup")
    saved_to = _append_row("cleanup.csv", data)
    return {"status": "ok", "doc_type": "cleanup", "saved_to": saved_to, "data": data}


def process_sold_image(image_path: str) -> dict[str, Any]:
    data = extract_sold_info(image_path)
    data = validate_extracted_data(data, "sold")
    saved_to = _append_row("sold.csv", data)
    return {"status": "ok", "doc_type": "sold", "saved_to": saved_to, "data": data}


def process_commission_image(image_path: str) -> dict[str, Any]:
    data = extract_commission_info(image_path)
    data = validate_extracted_data(data, "commission")
    saved_to = _append_row("commission.csv", data)
    return {"status": "ok", "doc_type": "commission", "saved_to": saved_to, "data": data}


def process_credit_image(image_path: str) -> dict[str, Any]:
    data = extract_credit_info(image_path)
    data = validate_extracted_data(data, "credit")
    saved_to = _append_row("credit.csv", data)
    return {"status": "ok", "doc_type": "credit", "saved_to": saved_to, "data": data}


def process_document_image(image_path: str, doc_type: str) -> dict[str, Any]:
    doc = (doc_type or "").strip().lower()
    dispatch: dict[str, Callable[[str], dict[str, Any]]] = {
        "lead": process_lead_image,
        "insurance": process_insurance_image,
        "cleanup": process_cleanup_image,
        "sold": process_sold_image,
        "commission": process_commission_image,
        "credit": process_credit_image,
    }
    if doc not in dispatch:
        return {
            "status": "error",
            "message": f"Unsupported doc_type '{doc_type}'. Use one of: {', '.join(DOC_TYPES)}",
        }

    try:
        return dispatch[doc](image_path)
    except Exception as exc:
        return {"status": "error", "message": str(exc), "doc_type": doc}


def process_document_folder(folder_path: str, doc_type: str) -> dict[str, Any]:
    """Batch-process all supported image files in a directory."""
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return {"status": "error", "message": f"Invalid folder path: {folder_path}"}

    supported = {".png", ".jpg", ".jpeg", ".webp"}
    results = []
    for file_path in sorted(folder.iterdir()):
        if not file_path.is_file() or file_path.suffix.lower() not in supported:
            continue
        result = process_document_image(str(file_path), doc_type)
        result["file"] = file_path.name
        results.append(result)

    success = sum(1 for r in results if r.get("status") == "ok")
    return {
        "status": "ok",
        "folder": str(folder),
        "doc_type": doc_type,
        "processed": len(results),
        "succeeded": success,
        "failed": len(results) - success,
        "results": results,
    }
