"""Security middleware components for production deployments."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter by client IP and path.

    Note: this limiter is process-local. In multi-worker or multi-instance deployments,
    each process tracks its own counters, so global rate limits are not enforced.
    For distributed enforcement, use a shared backend (for example Redis).
    """

    def __init__(self, app, requests_per_window: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.enabled = os.getenv("RATE_LIMIT_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._last_cleanup_ts = time.time()
        self._cleanup_interval_seconds = max(300, window_seconds * 5)

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path}"
        now = time.time()
        window_start = now - self.window_seconds

        if now - self._last_cleanup_ts >= self._cleanup_interval_seconds:
            self._cleanup(now)
            self._last_cleanup_ts = now

        history = self._hits[key]
        while history and history[0] < window_start:
            history.popleft()

        if len(history) >= self.requests_per_window:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please retry shortly."},
            )

        history.append(now)
        return await call_next(request)

    def _cleanup(self, now: float) -> None:
        stale_before = now - self.window_seconds
        stale_keys: list[str] = []
        for key, history in self._hits.items():
            while history and history[0] < stale_before:
                history.popleft()
            if not history:
                stale_keys.append(key)

        for key in stale_keys:
            self._hits.pop(key, None)
