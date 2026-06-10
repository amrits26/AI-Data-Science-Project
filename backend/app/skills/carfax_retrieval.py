SKILL_NAME = "carfax_retrieval"
SKILL_DESCRIPTION = "Retrieves Carfax or vehicle history for a given stock number or VIN."
SKILL_PRIORITY = 70
SKILL_TRIGGERS = [
    "carfax", "vehicle history", "accident", "service record", "show me the carfax", "history for"
]
SKILL_EMBEDDING = None


from backend.app.database.db import get_db_session
from backend.app.database.models import Car

def execute(query: str, context: dict, session_id: str) -> dict:
    import re
    stock_match = re.search(r"stock[\s#:]*([A-Za-z0-9\-]+)", query, re.I)
    vin_match = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", query, re.I)
    carfax_cmd = re.match(r"show me the carfax for (stock|vin)?\s*([a-zA-Z0-9\-]+)", query.strip(), re.I)
    if carfax_cmd:
        stock_or_vin = carfax_cmd.group(2)
        db = get_db_session()
        try:
            car = db.query(Car).filter(
                (Car.stock_number.ilike(stock_or_vin)) | (Car.vin.ilike(stock_or_vin))
            ).first()
            if car and getattr(car, "carfax_url", None):
                url = car.carfax_url.strip()
                if url:
                    return {
                        "answer": f"Here is the Carfax report for stock {car.stock_number or stock_or_vin}: [View Carfax](<{url}>)",
                        "question_type": "carfax_lookup",
                        "visualization": None,
                        "data": {"carfax_url": url, "stock_number": car.stock_number, "vin": car.vin},
                        "source": "carfax_direct"
                    }
            return {
                "answer": f"Sorry, I couldn't find a Carfax link for stock {stock_or_vin}. Please check the stock number or try again later.",
                "question_type": "carfax_lookup",
                "visualization": None,
                "data": {},
                "source": "carfax_direct"
            }
        finally:
            db.close()
    return {"answer": "Please specify a stock number or VIN for Carfax lookup (e.g., 'show me the carfax for stock 12345')."}
