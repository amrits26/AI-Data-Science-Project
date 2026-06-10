from __future__ import annotations

import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _data_dir() -> Path:
    path = Path(os.getenv("DATA_DIR", "./data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def feedback_path() -> Path:
    return _data_dir() / "feedback.csv"


def _knowledge_root() -> Path:
    root = Path(os.getenv("KNOWLEDGE_BASE_DIR", "knowledge_base"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _serialize_context(context: dict[str, Any] | None) -> str:
    if not context:
        return "{}"
    return json.dumps(context, ensure_ascii=True)


def _deserialize_context(value: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def ensure_feedback_store() -> Path:
    path = feedback_path()
    if path.exists():
        return path
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["interaction_id", "timestamp", "question", "answer", "rating", "context", "question_type", "source"],
        )
        writer.writeheader()
    return path


def log_feedback_interaction(
    question: str,
    answer: str,
    question_type: str,
    source: str,
    context: dict[str, Any] | None = None,
    rating: int = 0,
) -> dict[str, Any]:
    ensure_feedback_store()
    interaction_id = uuid4().hex
    row = {
        "interaction_id": interaction_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "answer": answer,
        "rating": int(rating),
        "context": _serialize_context(context),
        "question_type": question_type,
        "source": source,
    }
    with feedback_path().open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writerow(row)
    return {"status": "ok", "interaction_id": interaction_id, "path": str(feedback_path())}


def update_feedback(
    interaction_id: str,
    rating: int,
    context: dict[str, Any] | None = None,
    question: str = "",
    answer: str = "",
    question_type: str = "",
    source: str = "feedback_api",
) -> dict[str, Any]:
    ensure_feedback_store()
    with feedback_path().open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    updated = False
    for row in rows:
        if row.get("interaction_id") == interaction_id:
            row["rating"] = str(int(rating))
            if context:
                merged = _deserialize_context(row.get("context", ""))
                merged.update(context)
                row["context"] = _serialize_context(merged)
            updated = True
            break

    if not updated:
        rows.append(
            {
                "interaction_id": interaction_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "question": question,
                "answer": answer,
                "rating": str(int(rating)),
                "context": _serialize_context(context),
                "question_type": question_type,
                "source": source,
            }
        )

    with feedback_path().open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["interaction_id", "timestamp", "question", "answer", "rating", "context", "question_type", "source"],
        )
        writer.writeheader()
        writer.writerows(rows)

    return {"status": "ok", "interaction_id": interaction_id, "updated": updated, "rating": int(rating)}


def summarize_feedback(limit: int = 3) -> dict[str, Any]:
    ensure_feedback_store()
    with feedback_path().open("r", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    today = datetime.now(timezone.utc).date().isoformat()
    today_rows = [row for row in rows if str(row.get("timestamp", "")).startswith(today)]
    low_rated = [row for row in rows if int(str(row.get("rating", "0") or 0)) < 0]
    top_low = sorted(low_rated, key=lambda row: row.get("timestamp", ""), reverse=True)[:limit]

    question_counts = Counter(row.get("question_type") or "general" for row in low_rated)
    suggestions = []
    for question_type, count in question_counts.most_common(limit):
        suggestions.append(
            {
                "question_type": question_type,
                "count": count,
                "suggestion": _suggestion_for_question_type(question_type),
            }
        )

    return {
        "status": "ok",
        "feedback_entries": len(rows),
        "feedback_today": len(today_rows),
        "top_low_rated": [
            {
                "interaction_id": row.get("interaction_id"),
                "timestamp": row.get("timestamp"),
                "question": row.get("question"),
                "answer": row.get("answer"),
                "rating": int(str(row.get("rating", "0") or 0)),
                "question_type": row.get("question_type") or "general",
                "context": _deserialize_context(row.get("context", "")),
            }
            for row in top_low
        ],
        "suggestions": suggestions,
    }


def knowledge_base_status() -> dict[str, Any]:
    root = _knowledge_root()
    meta_path = root / "metadata.json"
    index_path = root / "index"
    status = {
        "status": "not_ready",
        "root": str(root),
        "index_path": str(index_path),
        "metadata_path": str(meta_path),
        "files": [],
        "chunks": 0,
    }
    if not meta_path.exists():
        return status
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        status.update({"status": "error", "message": f"Unable to read metadata: {exc}"})
        return status
    if isinstance(payload, dict):
        status.update(payload)
    status["status"] = "ok"
    return status


def build_training_report(credit_tiers: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok",
        "feedback": summarize_feedback(),
        "credit_tiers": credit_tiers,
        "knowledge_base": knowledge_base_status(),
    }


def _suggestion_for_question_type(question_type: str) -> str:
    mapping = {
        "financing": "Review calibrated APR tiers and expand payment-oriented winning scripts.",
        "price": "Add value-comparison scripts and fresh market-proof documents to the knowledge base.",
        "specs": "Ingest more brochures, warranty guides, or OEM feature summaries.",
        "trade_in": "Add transparent appraisal and equity talk tracks to winning scripts.",
        "general": "Review low-rated answers for missing trust-building follow-up questions.",
    }
    return mapping.get(question_type, mapping["general"])