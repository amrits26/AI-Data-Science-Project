SKILL_NAME = "build_sheet"
SKILL_DESCRIPTION = "Generate a comprehensive factory build sheet combining inventory, NHTSA, EPA, Carfax, reviews, and market data – better than any dealership website"
SKILL_PRIORITY = 55
SKILL_TRIGGERS = [
    "build sheet", "window sticker", "options list", "factory specs",
    "what options does", "tell me every detail", "full spec sheet",
    "all specs for", "vehicle details", "detailed specs",
    "tell me everything about"
]

from backend.app.database.db import get_db_session
from backend.app.database.models import Car
from backend.app.connectors import nhtsa, fueleconomy, kbb
from backend.app.skills.global_car_knowledge import execute as global_car_knowledge_execute
# from backend.app.connectors.vehicle_411 import get_vehicle_411_data  # Uncomment if available
import re

def extract_vin_or_stock(query: str):
    vin_match = re.search(r'vin[\s:]*([A-HJ-NPR-Z0-9]{11,17})', query, re.I)
    stock_match = re.search(r'stock[\s#:]*([\w-]+)', query, re.I)
    if vin_match:
        return 'vin', vin_match.group(1).strip()
    if stock_match:
        return 'stock', stock_match.group(1).strip()
    return None, None

def execute(query: str, context: dict, session_id: str) -> dict:
    key_type, key_value = extract_vin_or_stock(query)
    db = get_db_session()
    car = None
    try:
        if key_type == 'stock':
            car = db.query(Car).filter(Car.stock_number == key_value).first()
        elif key_type == 'vin':
            car = db.query(Car).filter(Car.vin == key_value).first()
        else:
            # fallback: try to find by make/model in query
            return {"answer": "Please provide a stock number or VIN for a detailed build sheet.", "source": "build_sheet", "question_type": "build_sheet", "metadata": {}}
        if not car:
            return {"answer": f"No vehicle found for {key_type}: {key_value}", "source": "build_sheet", "question_type": "build_sheet", "metadata": {}}
        # Gather data from connectors
        vin = car.vin
        nhtsa_data = nhtsa.decode_vin(vin) if vin else {}
        epa_result = fueleconomy.fetch(make=car.make, model=car.model, year=car.year) if car.make and car.model and car.year else {}
        epa_data = ((epa_result or {}).get("data") or {}).get("vehicle") or {}
        kbb_data = kbb.get_market_value(vin) if vin else {}
        carfax_url = getattr(car, "carfax_url", None)
        global_specs = global_car_knowledge_execute(f"specs for {car.year} {car.make} {car.model}", {}, session_id)
        # vehicle_411 = get_vehicle_411_data(vin) if vin else {}  # Uncomment if available
        # Compose build sheet sections
        overview = f"{car.year} {car.make} {car.model} {car.trim or ''} | Stock: {car.stock_number} | VIN: {car.vin} | MSRP: ${car.msrp or 'N/A'} | Mileage: {car.mileage or 'N/A'} | Color: {car.color or 'N/A'}"
        image_url = getattr(car, "image_url", None)
        engine = car.engine or nhtsa_data.get("EngineModel")
        transmission = car.transmission or nhtsa_data.get("TransmissionStyle")
        drivetrain = car.drivetrain or nhtsa_data.get("DriveType")
        towing = getattr(car, "towing_capacity", None) or nhtsa_data.get("TowingCapacity")
        payload = getattr(car, "payload_capacity", None) or nhtsa_data.get("PayloadCapacity")
        # ... more fields as needed
        # Format answer
        city_mpg = epa_data.get("city08") or "N/A"
        hwy_mpg = epa_data.get("highway08") or "N/A"
        comb_mpg = epa_data.get("comb08") or "N/A"
        annual_fuel_cost = epa_data.get("fuelCost08") or "N/A"
        fuel_type = epa_data.get("fuelType1") or nhtsa_data.get("FuelTypePrimary") or "N/A"

        answer = f"""
📋 **VEHICLE OVERVIEW**
{overview}
{'![Vehicle Image](' + image_url + ')' if image_url else ''}

🔧 **ENGINE & DRIVETRAIN**
Engine: {engine or 'N/A'}
Transmission: {transmission or 'N/A'}
Drivetrain: {drivetrain or 'N/A'}
Towing: {towing or 'N/A'}
Payload: {payload or 'N/A'}

⛽ **FUEL ECONOMY**
City/Highway/Combined MPG: {city_mpg}/{hwy_mpg}/{comb_mpg}
Annual Fuel Cost: {annual_fuel_cost}
Fuel Type: {fuel_type}

🛡️ **SAFETY & RECALLS**
NHTSA Star Rating: {nhtsa_data.get('OverallRating', 'N/A')}
Open Recalls: {nhtsa_data.get('RecallCount', 'N/A')}

📦 **FACTORY OPTIONS**
{nhtsa_data.get('OptionalEquipment', 'N/A')}

📎 **VEHICLE HISTORY**
{'[View Full Carfax History](' + carfax_url + ')' if carfax_url else 'N/A'}

💰 **MARKET VALUE**
KBB Trade-in: {kbb_data.get('trade_in_low', 'N/A')} - {kbb_data.get('trade_in_high', 'N/A')}
KBB Retail: {kbb_data.get('retail_low', 'N/A')} - {kbb_data.get('retail_high', 'N/A')}

🌐 **EXPERT REVIEWS & GLOBAL SPECS**
{global_specs.get('answer', 'N/A')}
"""
        return {
            "answer": answer.strip(),
            "source": "multi_source",
            "question_type": "build_sheet",
            "metadata": {
                "car": {
                    "stock_number": car.stock_number,
                    "vin": car.vin,
                    "year": car.year,
                    "make": car.make,
                    "model": car.model,
                    "trim": car.trim,
                    "msrp": car.msrp,
                },
                "nhtsa": nhtsa_data,
                "epa": epa_data,
                "kbb": kbb_data,
                "carfax_url": carfax_url,
                "global_specs": global_specs,
                # "vehicle_411": vehicle_411,  # Uncomment if available
            }
        }
    finally:
        db.close()
