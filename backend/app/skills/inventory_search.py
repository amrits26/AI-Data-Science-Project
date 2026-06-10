SKILL_NAME = "inventory_search"
SKILL_DESCRIPTION = "Search live inventory for vehicles matching a description."
SKILL_PRIORITY = 60
SKILL_TRIGGERS = [
    "do you have", "ford", "chevy", "gmc", "truck", "suv", "tell me about", "show me", "looking for", "inventory"
]
SKILL_EMBEDDING = None


from backend.app.database.db import get_db_session
from backend.app.database.models import Car
from sqlalchemy import or_

def execute(query: str, context: dict, session_id: str) -> dict:
    import re
    def normalize_car_term(text: str) -> str:
        text = text.lower().strip()
        aliases = {
            "chevy": "chevrolet",
            "merc": "mercedes",
            "vw": "volkswagen",
            "bimmer": "bmw",
            "f150": "f-150",
            "f 150": "f-150",
            "ford 150": "f-150",
            "silverado": "silverado 1500"
        }
        for k, v in aliases.items():
            if k in text:
                text = text.replace(k, v)
        text = re.sub(r"\s+", " ", text)
        return text

    db = get_db_session()
    try:
        norm_query = normalize_car_term(query)
        query_lower = norm_query.lower()
        make_filter = None
        model_filter = None
        color_filter = None
        has_make_filter = False
        has_model_filter = False
        makes = ["ford", "chevrolet", "gmc", "toyota", "honda", "nissan", "bmw", "mercedes", "audi"]
        models = []
        colors = ["blue", "red", "black", "white", "silver", "gray", "green"]
        for m in makes:
            if m in query_lower:
                make_filter = Car.make.ilike(f"%{m}%")
                has_make_filter = True
        for c in colors:
            if c in query_lower:
                color_filter = Car.color.ilike(f"%{c}%")
        words = query_lower.split()
        for w in words:
            if w not in makes and len(w) > 1:
                models.append(w)
        for w in models:
            if w not in colors:
                model_filter = Car.model.ilike(f"%{w}%")
                has_model_filter = True
                break
        feature_filters = []
        if "tow package" in query_lower:
            feature_filters.append(Car.towing_capacity > 0)
        filters = [f for f in [make_filter, model_filter, color_filter] if f is not None] + feature_filters
        cars = db.query(Car).filter(*filters).limit(5).all() if filters else []
        if not cars and (has_make_filter or has_model_filter):
            filters_no_color = [f for f in [make_filter, model_filter] if f is not None] + feature_filters
            cars = db.query(Car).filter(*filters_no_color).limit(5).all() if filters_no_color else []
        if not cars and has_make_filter:
            filters_make_only = [make_filter] + feature_filters
            cars = db.query(Car).filter(*filters_make_only).limit(5).all()
        if not cars:
            make_str = "Ford F-150s" if (has_make_filter and has_model_filter) else ("Ford" if has_make_filter else "vehicles")
            return {
                "answer": f"I couldn't find any {make_str} on our lot right now. Let me know if you'd like me to search for something else.",
                "source": "inventory",
                "question_type": "inventory"
            }
        lines = ["Here are a few matching vehicles on our lot:"]
        for car in cars:
            specs = []
            if car.horsepower:
                specs.append(f"{car.horsepower} hp")
            if car.torque:
                specs.append(f"{car.torque} lb-ft")
            spec_str = ", ".join(specs) if specs else ""
            price = car.msrp or car.invoice_price or car.used_avg_price or 0
            price_str = f"${price:,.0f}" if price else "N/A"
            carfax_link = ""
            if getattr(car, "carfax_url", None):
                carfax_url = car.carfax_url.strip()
                if carfax_url:
                    carfax_link = f" | [View Carfax](<{carfax_url}>)"
            lines.append(
                f"- {car.year} {car.make} {car.model} {car.trim or ''} | "
                f"Stock: {car.stock_number or 'N/A'} | Price: {price_str}" +
                (f" | {spec_str}" if spec_str else "") + carfax_link
            )
        answer_text = "\n".join(lines)
        return {
            "answer": answer_text,
            "source": "inventory",
            "question_type": "inventory"
        }
    finally:
        db.close()
