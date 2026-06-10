from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from backend.app.core.config import CACHE_TTL_HOURS, EXTERNAL_API_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CACHE_ROOT = _PROJECT_ROOT / "cache" / "connectors"
_API_LOG_PATH = _PROJECT_ROOT / "data" / "api_calls.log"


def ensure_runtime_dirs() -> None:
    _CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    _API_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ttl_seconds() -> int:
    return max(int(CACHE_TTL_HOURS), 1) * 3600


def build_cache_key(namespace: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
    return f"{namespace}_{digest}"


def cache_path(namespace: str, cache_key: str) -> Path:
    return _CACHE_ROOT / namespace / f"{cache_key}.json"


def load_cached(namespace: str, cache_key: str) -> dict[str, Any] | None:
    ensure_runtime_dirs()
    path = cache_path(namespace, cache_key)
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched_at = payload.get("fetched_at")
        if not fetched_at:
            return None
        age = now_utc() - datetime.fromisoformat(str(fetched_at))
        if age.total_seconds() > ttl_seconds():
            return None
        return payload.get("data") if isinstance(payload.get("data"), dict) else None
    except Exception as exc:
        logger.warning("connector_cache_read_failed", extra={"namespace": namespace, "cache_key": cache_key, "error": str(exc)})
        return None


def save_cached(namespace: str, cache_key: str, data: dict[str, Any]) -> None:
    ensure_runtime_dirs()
    path = cache_path(namespace, cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": now_utc().isoformat(),
        "data": data,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def log_api_call(source: str, endpoint: str, params: dict[str, Any], status: str, detail: str = "") -> None:
    ensure_runtime_dirs()
    entry = {
        "timestamp": now_utc().isoformat(),
        "source": source,
        "endpoint": endpoint,
        "params": params,
        "status": status,
        "detail": detail,
    }
    with _API_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=True, default=str) + os.linesep)


def make_result(source: str, status: str, data: dict[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
    payload = {
        "source": source,
        "status": status,
        "fetched_at": now_utc().isoformat(),
    }
    if data:
        payload.update(data)
    if error:
        payload["error"] = error
    return payload


def get_json(
    source: str,
    namespace: str,
    endpoint: str,
    params: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    cache_key = build_cache_key(namespace, params)
    cached = load_cached(namespace, cache_key)
    if cached is not None:
        log_api_call(source, endpoint, params, "cache_hit")
        return cached

    effective_timeout = float(timeout or EXTERNAL_API_TIMEOUT_SECONDS)
    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=effective_timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            payload = {"results": payload}
        save_cached(namespace, cache_key, payload)
        log_api_call(source, endpoint, params, "ok")
        return payload
    except Exception as exc:
        log_api_call(source, endpoint, params, "error", str(exc))
        raise


def get_text(
    source: str,
    namespace: str,
    endpoint: str,
    params: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> str:
    cache_key = build_cache_key(namespace, params)
    cached = load_cached(namespace, cache_key)
    if cached is not None:
        log_api_call(source, endpoint, params, "cache_hit")
        return str(cached.get("text", ""))

    effective_timeout = float(timeout or EXTERNAL_API_TIMEOUT_SECONDS)
    try:
        response = requests.get(endpoint, params=params, headers=headers, timeout=effective_timeout)
        response.raise_for_status()
        text = response.text
        save_cached(namespace, cache_key, {"text": text})
        log_api_call(source, endpoint, params, "ok")
        return text
    except Exception as exc:
        log_api_call(source, endpoint, params, "error", str(exc))
        raise