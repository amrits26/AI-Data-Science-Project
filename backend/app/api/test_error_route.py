# Test endpoint to trigger an unhandled exception for error handler validation
from fastapi import APIRouter

router = APIRouter()

@router.get("/api/trigger_error")
def trigger_error():
    raise RuntimeError("Test unhandled exception for global error handler.")
