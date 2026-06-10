SKILL_NAME = "vin_decoder"
SKILL_DESCRIPTION = "Decodes a 17-character VIN and returns vehicle details."
SKILL_PRIORITY = 50
SKILL_TRIGGERS = [
    "vin", "decode", "vehicle identify"
]
SKILL_EMBEDDING = None

from backend.app.connectors.nhtsa import decode_vin
import re

def execute(query: str, context: dict, session_id: str) -> dict:
    vin_match = re.search(r"\b([A-HJ-NPR-Z0-9]{17})\b", query, re.I)
    if vin_match:
        vin = vin_match.group(1)
        vin_data = decode_vin(vin)
        return {"answer": f"Decoded VIN: {vin_data}", "question_type": "vin_decode", "data": vin_data, "source": "vin_decoder"}
    return {"answer": "No valid VIN found in your question.", "question_type": "vin_decode", "data": {}, "source": "vin_decoder"}
