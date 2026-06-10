from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from backend.app.core.config import FUELECONOMY_API_ENABLED
from backend.app.connectors.shared import get_text, make_result

BASE_URL = "https://www.fueleconomy.gov/ws/rest"


def _xml_to_records(text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(text)
    items: list[dict[str, Any]] = []

    def _strip(tag: str) -> str:
        return tag.split("}", 1)[-1]

    for item in root.iter():
        if _strip(item.tag) != "menuItem" and _strip(item.tag) != "vehicle":
            continue
        row: dict[str, Any] = {}
        for child in list(item):
            row[_strip(child.tag)] = (child.text or "").strip()
        if row:
            items.append(row)
    return items


def _best_vehicle_match(vehicles: list[dict[str, Any]], model: str | None) -> dict[str, Any] | None:
    if not vehicles:
        return None
    if not model:
        return vehicles[0]
    target = model.strip().lower()
    for vehicle in vehicles:
        if target in str(vehicle.get("model") or vehicle.get("text") or "").lower():
            return vehicle
    return vehicles[0]


def fetch(*, make: str | None = None, model: str | None = None, year: int | None = None) -> dict[str, Any]:
    if not FUELECONOMY_API_ENABLED:
        return make_result("FuelEconomy.gov", "disabled")
    if not make or not model or not year:
        return make_result("FuelEconomy.gov", "error", error="make, model, and year are required")

    try:
        menu_text = get_text(
            "FuelEconomy.gov",
            "fueleconomy_menu_options",
            f"{BASE_URL}/vehicle/menu/options",
            {"year": int(year), "make": make, "model": model},
        )
        options = _xml_to_records(menu_text)
        best_option = _best_vehicle_match(options, model)
        vehicle_id = str(best_option.get("value") or "").strip() if best_option else ""
        vehicle_detail = None
        if vehicle_id:
            vehicle_text = get_text(
                "FuelEconomy.gov",
                "fueleconomy_vehicle",
                f"{BASE_URL}/vehicle/{vehicle_id}",
                {},
            )
            vehicles = _xml_to_records(vehicle_text)
            vehicle_detail = vehicles[0] if vehicles else None

        return make_result(
            "FuelEconomy.gov",
            "ok",
            data={
                "year": int(year),
                "make": make,
                "model": model,
                "options": options,
                "vehicle_id": vehicle_id or None,
                "vehicle": vehicle_detail,
            },
        )
    except Exception as exc:
        return make_result(
            "FuelEconomy.gov",
            "error",
            data={"year": int(year), "make": make, "model": model},
            error=str(exc),
        )