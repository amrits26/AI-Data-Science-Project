import os
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import RequestValidationError
from fastapi.exceptions import RequestValidationError as FastAPIRequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback

ERROR_LOG_PATH = os.path.join("data", "logs", "errors.log")

def log_error_to_file(exc: Exception, request: Request = None):
    os.makedirs(os.path.dirname(ERROR_LOG_PATH), exist_ok=True)
    with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n---\n")
        if request:
            f.write(f"URL: {request.url}\nMethod: {request.method}\n")
        f.write(f"Exception: {repr(exc)}\n")
        f.write(traceback.format_exc())


# Handler functions only; registration is done in main.py
async def global_exception_handler(request: Request, exc: Exception):
    log_error_to_file(exc, request)
    return JSONResponse(
        status_code=500,
        content={
            "message": "An unexpected error occurred. Our team has been notified.",
            "detail": "If this persists, please contact support.",
        },
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    log_error_to_file(exc, request)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": exc.detail or "HTTP error occurred.",
        },
    )

async def validation_exception_handler(request: Request, exc: FastAPIRequestValidationError):
    log_error_to_file(exc, request)
    return JSONResponse(
        status_code=422,
        content={
            "message": "Request validation error.",
            "errors": exc.errors(),
        },
    )
