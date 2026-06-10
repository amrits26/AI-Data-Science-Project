

# --- Ensure environment is loaded before any other import ---
import os
from dotenv import load_dotenv

load_dotenv(".env.local", override=True)
load_dotenv(".env", override=False)
os.environ.setdefault("DATABASE_URL", "sqlite:///./data/imperial_cars.db")

from fastapi import FastAPI
from pathlib import Path
from contextlib import asynccontextmanager
import asyncio
HEARTBEAT_FILE = Path("data/logs/heartbeat.txt")

async def heartbeat_writer():
    while True:
        HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_FILE.write_text(str(time.time()))
        await asyncio.sleep(30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    _log_event("api_startup", app=APP_NAME, version=APP_VERSION, env=APP_ENV)
    heartbeat_task = asyncio.create_task(heartbeat_writer())
    yield
    heartbeat_task.cancel()
    _log_event("api_shutdown", app=APP_NAME, version=APP_VERSION, env=APP_ENV)

"""
from apscheduler.schedulers.background import BackgroundScheduler
import subprocess
import threading
# --- Automated Knowledge Base Update Scheduler ---
def run_auto_ingest():
    log_path = "data/logs/auto_ingest.log"
    with open(log_path, "a", encoding="utf-8") as log:
        subprocess.run([
            ".venv/Scripts/python.exe", "scripts/auto_ingest_faq.py"
        ], stdout=log, stderr=log)

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_auto_ingest, 'cron', day_of_week='sun', hour=3, minute=0)
    scheduler.start()

# Start scheduler in a background thread after FastAPI startup
@app.on_event("startup")
async def startup_event() -> None:
    _log_event("api_startup", app=APP_NAME, version=APP_VERSION, env=APP_ENV)
    threading.Thread(target=start_scheduler, daemon=True).start()
"""
from fastapi import Depends
from fastapi.security import APIKeyHeader
import os
API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key")


import sys
print("PYTHONPATH sys.path:", sys.path)
import logging
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router
from backend.app.api.test_error_route import router as test_error_router
from backend.app.global_error_handlers import (
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from backend.app.core.config import (
    APP_ENV,
    APP_NAME,
    APP_VERSION,
    CORS_ORIGINS,
    LOG_JSON,
    LOG_LEVEL,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    TRUSTED_HOSTS,
)
from backend.app.core.logging_config import configure_logging, get_logger

from backend.app.core.security import RateLimitMiddleware
from backend.app.core.api_key_auth import APIKeyAuthMiddleware, get_configured_api_keys, is_valid_api_key

configure_logging(getattr(logging, LOG_LEVEL, logging.INFO), json_output=LOG_JSON)
logger = get_logger(__name__)


app = FastAPI(
    title=APP_NAME,
    description="Imperial Cars AI API for analytics, chatbot, VIN decode, and dealership workflows.",
    version=APP_VERSION,
    lifespan=lifespan,
)

# Register global exception handlers
from fastapi.exceptions import RequestValidationError as FastAPIRequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(FastAPIRequestValidationError, validation_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED_HOSTS)

app.add_middleware(
    APIKeyAuthMiddleware,
    api_key_header="X-API-Key",
    api_key_env="IMPERIAL_API_KEY",
)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_window=RATE_LIMIT_REQUESTS,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)

app.include_router(router)
app.include_router(test_error_router)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = PROJECT_ROOT / "frontend-react" / "dist"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"


def _log_event(event: str, **fields) -> None:
    if hasattr(logger, "bind"):
        logger.bind(**fields).info(event)
    else:
        tail = " ".join(f"{k}={v}" for k, v in fields.items())
        logger.info(f"{event} {tail}".strip())


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    _log_event(
        "http_request",
        method=request.method,
        path=request.url.path,
        query=request.url.query,
        status_code=response.status_code,
        duration_ms=elapsed_ms,
        client_ip=request.client.host if request.client else None,
    )
    return response


@app.get("/")
async def root():
    index_file = FRONTEND_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    return JSONResponse(
        status_code=503,
        content={
            "message": "Frontend build not found.",
            "hint": "Run scripts/build_frontend.ps1 to create frontend-react/dist.",
            "environment": APP_ENV,
            "docs": "/docs",
            "health": "/api/health",
        },
    )


if FRONTEND_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="frontend-assets")
else:
    _log_event("frontend_assets_missing", path=str(FRONTEND_ASSETS_DIR))



# --- Skill feedback endpoint ---
from fastapi import Request
@app.post("/api/skill/feedback")
async def skill_feedback(request: Request):
    data = await request.json()
    log_path = "data/skill_feedback.jsonl"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        import json
        f.write(json.dumps(data) + "\n")
    return {"status": "logged"}

# --- Cache clear endpoint for semantic cache ---
@app.post("/api/cache/clear")
def clear_cache(api_key: str = Depends(api_key_header)):
    accepted_keys = get_configured_api_keys(
        "IMPERIAL_API_KEY",
        "API_KEY",
        "IMPERIAL_API_KEY_LEGACY",
        "API_KEY_LEGACY",
    )
    if not is_valid_api_key(api_key, accepted_keys):
        raise HTTPException(status_code=401, detail="Invalid API key")
    from backend.app.agents.imperial_chatbot import semantic_cache
    semantic_cache.clear()
    return {"status": "cleared"}

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """Serve SPA routes while preserving API namespace behavior."""
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not Found")

    requested = FRONTEND_DIST_DIR / full_path
    if requested.is_file():
        return FileResponse(requested)

    index_file = FRONTEND_DIST_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Frontend build not found")
