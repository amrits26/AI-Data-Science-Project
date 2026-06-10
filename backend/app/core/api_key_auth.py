from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import os
import secrets
from typing import Iterable


def get_configured_api_keys(*env_names: str):
    keys = []
    for name in env_names:
        value = os.getenv(name, "").strip()
        if value and value not in keys:
            keys.append(value)
    return keys


def is_valid_api_key(header_key: str, accepted_keys) -> bool:
    if not header_key:
        return False
    return any(secrets.compare_digest(header_key, key) for key in accepted_keys)


def _extract_request_api_key(request: Request, api_key_header: str) -> str | None:
    header_key = request.headers.get(api_key_header)
    if header_key:
        return header_key

    # Web UI fallback for browser sessions that cannot inject custom headers.
    for cookie_name in ("imperial_api_key", "api_key", "x_api_key"):
        cookie_value = request.cookies.get(cookie_name)
        if cookie_value:
            return cookie_value
    return None


def _is_protected_path(path: str) -> bool:
    normalized_path = (path or "/").rstrip("/") or "/"

    # Costly or state-mutating API routes requiring API key protection.
    exact_matches = {
        "/api/ask",
        "/api/knowledge/query",
        "/api/knowledge/ingest",
    }
    protected_prefixes = (
        "/api/followup",
        "/api/dealership/",
        "/api/leads",
        "/api/feedback",
        "/api/deal/",
        "/api/unanswered",
        "/api/visualizations",
        "/api/paperwork/",
    )
    return normalized_path in exact_matches or any(normalized_path.startswith(prefix.rstrip("/")) for prefix in protected_prefixes)


def _should_bypass_auth_for_request() -> bool:
    if os.getenv("IMPERIAL_BYPASS_API_KEY_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    # Pytest sets this for active test execution; keep tests isolated from local .env keys.
    if "PYTEST_CURRENT_TEST" in os.environ:
        return True
    return False

class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key_header: str = "X-API-Key", api_key_env: str = "API_KEY"):
        super().__init__(app)
        self.api_key_header = api_key_header
        self.accepted_keys = get_configured_api_keys(
            api_key_env,
            "IMPERIAL_API_KEY",
            "API_KEY",
            "IMPERIAL_API_KEY_LEGACY",
            "API_KEY_LEGACY",
        )

    async def dispatch(self, request: Request, call_next):
        if _should_bypass_auth_for_request():
            return await call_next(request)

        path = request.url.path
        if _is_protected_path(path):
            request_key = _extract_request_api_key(request, self.api_key_header)
            if not self.accepted_keys or not is_valid_api_key(request_key, self.accepted_keys):
                return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key."})
        return await call_next(request)
