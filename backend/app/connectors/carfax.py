from __future__ import annotations

from typing import Any

from backend.app.core.config import CARFAX_API_KEY
from backend.app.connectors.shared import log_api_call, make_result


def fetch(*, vin: str | None = None, make: str | None = None, model: str | None = None, year: int | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"vin": vin, "make": make, "model": model, "year": year}
    if not CARFAX_API_KEY:
        log_api_call("Carfax", "configured-placeholder", params, "not_configured")
        return make_result(
            "Carfax",
            "not_configured",
            data={"vin": vin, "make": make, "model": model, "year": year},
            error="CARFAX_API_KEY is not configured",
        )

    log_api_call("Carfax", "configured-placeholder", params, "unavailable", "Connector placeholder not yet implemented")
    return make_result(
        "Carfax",
        "unavailable",
        data={"vin": vin, "make": make, "model": model, "year": year},
        error="Carfax connector placeholder is ready for credentialed implementation",
    )