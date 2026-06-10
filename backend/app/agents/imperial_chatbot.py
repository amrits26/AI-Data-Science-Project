from __future__ import annotations

import re
import string
import logging
from typing import Any, Dict, Optional

from cachetools import TTLCache

from backend.app.agents.training_feedback import log_feedback_interaction
from backend.app.connectors import carfax as carfax_connector
from backend.app.connectors import fueleconomy as fueleconomy_connector
from backend.app.connectors import kbb as kbb_connector
from backend.app.connectors import nhtsa as nhtsa_connector
from backend.app.skills.live_car_finder import LiveCarFinder

semantic_cache = TTLCache(maxsize=500, ttl=3600)
logger = logging.getLogger(__name__)


def should_use_car_finder_mode(user_message: str) -> bool:
    keywords = [
        "2500",
        "heated seats",
        "find a car",
        "imperialcars.com",
        "chevy 2500",
        "ram 2500",
        "f-250",
    ]
    lowered = (user_message or "").lower()
    return any(k in lowered for k in keywords)


def _build_live_car_finder_payload(question: str, customer_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    logger.info("car_finder_mode_triggered")
    matches = LiveCarFinder.find_heated_2500_trucks()
    answer = LiveCarFinder.format_customer_response(matches)
    source = "live_car_finder"
    feedback = log_feedback_interaction(
        question=question,
        answer=answer,
        question_type="car_finder",
        source=source,
        context=customer_context,
        rating=0,
    )
    return {
        "answer": answer,
        "question_type": "car_finder",
        "source": source,
        "metadata": {
            "sources": ["Live Web"],
            "role": _detect_customer_role(question)[0],
            "tone": _detect_customer_role(question)[1],
            "matches": matches,
        },
        "knowledge_contexts": [],
        "interaction_id": feedback.get("interaction_id"),
        "conflict_mode": _detect_conflict_mode(question),
    }


def normalize_question(question: str) -> str:
    return "".join(ch for ch in (question or "").lower().strip() if ch not in string.punctuation)


def normalize_car_term(text: str) -> str:
    value = (text or "").lower().strip()
    aliases = {
        "chevy": "chevrolet",
        "merc": "mercedes",
        "vw": "volkswagen",
        "bimmer": "bmw",
        "f150": "f-150",
        "f 150": "f-150",
    }
    for source, target in aliases.items():
        value = value.replace(source, target)
    return re.sub(r"\s+", " ", value)


def _detect_customer_role(question: str) -> tuple[str, str]:
    text = (question or "").lower()
    if any(token in text for token in ("apr", "payment", "loan", "finance", "lease", "rate")):
        return "finance", "analytical"
    if any(token in text for token in ("service", "maintenance", "oil", "repair", "appointment")):
        return "service", "reassuring"
    if any(token in text for token in ("spec", "features", "compare", "research")):
        return "researcher", "informative"
    return "buyer", "decisive"


def _detect_conflict_mode(question: str) -> Dict[str, Any]:
    text = (question or "").lower()
    objection_tokens = ("expensive", "too much", "out of budget", "can't afford", "price is high")
    triggered = any(token in text for token in objection_tokens)
    options = [
        "Show lower total-cost alternatives",
        "Recalculate payments with adjusted down payment and term",
        "Suggest trade-in or incentive-based reductions",
    ]
    return {
        "triggered": triggered,
        "reason": "price_objection" if triggered else None,
        "options": options if triggered else [],
    }


def _get_maintenance_schedule() -> Dict[str, str]:
    return {
        "Oil & Filter Change": "Every 5,000 to 7,500 miles",
        "Tire Rotation": "Every 5,000 to 7,500 miles",
        "Brake Inspection": "Every 10,000 miles",
        "Cabin Air Filter": "Every 15,000 to 25,000 miles",
        "Engine Air Filter": "Every 20,000 to 30,000 miles",
        "Battery": "Inspect every service; replace around 3 to 5 years",
        "Spark Plugs": "Every 60,000 to 100,000 miles",
        "Brake Fluid": "About every 2 years",
    }


def _classify_question(question: str) -> str:
    text = (question or "").lower()

    maintenance_tokens = (
        "maintenance schedule",
        "when should i change",
        "when should i get",
        "how often should i",
        "how often to change",
        "service interval",
        "oil",
        "tire rotation",
        "spark plug",
        "brake fluid",
        "cabin air filter",
    )
    if any(token in text for token in maintenance_tokens):
        return "maintenance_schedule"

    if any(token in text for token in ("vin", "decode")):
        return "vin_decode"
    if any(token in text for token in ("compare", "vs", "versus")):
        return "comparison"
    if any(token in text for token in ("price", "cost", "msrp", "afford", "expensive")):
        return "price"
    if any(token in text for token in ("spec", "engine", "hp", "torque", "transmission", "feature")):
        return "specs"
    if any(token in text for token in ("loan", "finance", "financing", "payment", "monthly", "apr", "rate")):
        return "financing"
    if any(token in text for token in ("lease", "rent")):
        return "lease"
    if any(token in text for token in ("trade", "trade-in", "tradein")):
        return "trade_in"
    if any(token in text for token in ("service", "maintenance", "repair", "recall")):
        return "service"
    return "general_knowledge"


def _extract_inventory_entities(question: str) -> Dict[str, Any]:
    text = normalize_car_term(question)
    entities: Dict[str, Any] = {}

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    if year_match:
        entities["year"] = int(year_match.group(1))

    makes = [
        "acura", "audi", "bmw", "chevrolet", "ford", "gmc", "honda", "hyundai", "jeep", "kia",
        "lexus", "mazda", "mercedes", "nissan", "subaru", "tesla", "toyota", "volkswagen",
    ]
    for make in makes:
        if re.search(rf"\b{re.escape(make)}\b", text):
            entities["make"] = make.title()
            break

    model_match = re.search(r"\b(f-150|camry|accord|civic|corolla|rav4|cr-v|mustang|silverado|model 3|model y)\b", text)
    if model_match:
        entities["model"] = model_match.group(1).upper().replace("MODEL ", "Model ")

    return entities


def _structured_inventory_search(entities: Dict[str, Any], constraints: Dict[str, Any], limit: int = 5) -> Dict[str, Any]:
    try:
        from backend.app.database import Car, get_db_session
    except Exception:
        return {"total": 0, "rows": []}

    db = get_db_session()
    try:
        query = db.query(Car)
        make = entities.get("make")
        model = entities.get("model")
        year = entities.get("year")

        if make:
            query = query.filter(Car.make.ilike(f"%{make}%"))
        if model:
            query = query.filter(Car.model.ilike(f"%{model}%"))
        if year:
            query = query.filter(Car.year == int(year))

        rows = query.order_by(Car.year.desc(), Car.make.asc(), Car.model.asc()).limit(max(1, int(limit))).all()
        payload = []
        for row in rows:
            payload.append(
                {
                    "id": row.id,
                    "year": row.year,
                    "make": row.make,
                    "model": row.model,
                    "trim": row.trim,
                    "price": float(row.msrp or 0),
                    "mileage": int(getattr(row, "mileage", 0) or 0),
                    "color": getattr(row, "color", None),
                    "horsepower": row.horsepower,
                    "torque": row.torque,
                    "towing_capacity": getattr(row, "towing_capacity", None),
                    "mpg_highway": row.mpg_highway,
                    "vin": getattr(row, "vin", None),
                }
            )
        return {"total": len(payload), "rows": payload}
    finally:
        db.close()


def query_knowledge_base(question: str, top_k: int = 4) -> Dict[str, Any]:
    try:
        from backend.app.agents.knowledge_base.query import query_knowledge_base as kb_query
    except Exception as exc:
        return {"status": "error", "message": str(exc), "contexts": []}

    try:
        return kb_query(question, top_k=top_k)
    except Exception as exc:
        return {"status": "error", "message": str(exc), "contexts": []}


def fetch_nhtsa(**kwargs: Any) -> Dict[str, Any]:
    return nhtsa_connector.fetch(**kwargs)


def fetch_fueleconomy(**kwargs: Any) -> Dict[str, Any]:
    return fueleconomy_connector.fetch(**kwargs)


def fetch_kbb(**kwargs: Any) -> Dict[str, Any]:
    return kbb_connector.fetch(**kwargs)


def fetch_carfax(**kwargs: Any) -> Dict[str, Any]:
    return carfax_connector.fetch(**kwargs)


def _safety_refusal(question: str) -> Optional[str]:
    text = (question or "").lower()

    pii_tokens = (
        "customer", "phone number", "email", "social security", "ssn", "address",
        "list all customer", "last customer",
    )
    if any(token in text for token in pii_tokens):
        return "I cannot share personal customer information and I do not have that information available for disclosure."

    illegal_tokens = (
        "disable the airbags", "bypass the immobilizer", "roll back an odometer", "fake carfax",
        "fake documents", "hide income", "insurance fraud", "cheat", "illegal", "get away with",
        "avoid paying sales tax", "tell me something illegal",
    )
    if any(token in text for token in illegal_tokens):
        return "I cannot help with illegal or unsafe actions. Please use legal and safety-compliant options."

    disparagement_tokens = ("carmax", "tesla bad", "carvana", "autonation", "worse than")
    if any(token in text for token in disparagement_tokens):
        return "I cannot provide negative commentary about competitors; let us focus on our service and your needs."

    prompt_injection_tokens = (
        "ignore previous instructions",
        "forget all previous instructions",
        "tell me a secret",
        "imperial cars is a scam",
        "tell me a joke about your boss",
    )
    if any(token in text for token in prompt_injection_tokens):
        return "That request is not allowed. I cannot provide secrets or policy-breaking content."

    if "tax" in text and ("lease" in text or "buy" in text):
        return "I cannot provide legal or tax advice. Please speak with a finance manager."

    return None


def _build_answer_from_inventory_row(row: Dict[str, Any]) -> str:
    year = row.get("year")
    make = row.get("make")
    model = row.get("model")
    trim = row.get("trim")
    price = row.get("price")
    mpg = row.get("mpg_highway")
    tow = row.get("towing_capacity")

    parts = [f"{year} {make} {model}".strip()]
    if trim:
        parts.append(f"trim {trim}")
    summary = ", ".join(parts)

    details = []
    if price:
        details.append(f"Price around ${float(price):,.0f}")
    if mpg:
        details.append(f"Highway MPG about {mpg}")
    if tow:
        details.append(f"Towing capacity around {tow}")

    if details:
        return f"{summary}. " + ". ".join(details) + "."
    return f"{summary}."


def _build_maintenance_answer() -> str:
    schedule = _get_maintenance_schedule()
    lines = "\n".join(f"- {k}: {v}" for k, v in schedule.items())
    return (
        "Here is a standard maintenance schedule:\n\n"
        f"{lines}\n\n"
        "Always follow your owner's manual for model-specific intervals."
    )


def _build_sources_label(sources: list[str]) -> str:
    return ", ".join(sources)


def ask_imperial_detailed(
    question: str,
    customer_context: Optional[Dict[str, Any]] = None,
    prefer_template: bool = False,
) -> Dict[str, Any]:
    normalized = normalize_question(question)
    cache_key = f"{normalized}|{int(prefer_template)}"
    if cache_key in semantic_cache:
        return semantic_cache[cache_key]

    refusal = _safety_refusal(question)
    if refusal:
        feedback = log_feedback_interaction(
            question=question,
            answer=refusal,
            question_type="safety",
            source="policy",
            context=customer_context,
            rating=0,
        )
        payload = {
            "answer": refusal,
            "question_type": "safety",
            "source": "policy",
            "metadata": {"sources": ["Safety Policy"]},
            "knowledge_contexts": [],
            "interaction_id": feedback.get("interaction_id"),
            "conflict_mode": {"triggered": False, "options": []},
        }
        semantic_cache[cache_key] = payload
        return payload

    if should_use_car_finder_mode(question):
        logger.info("car_finder_mode_routed")
        payload = _build_live_car_finder_payload(question, customer_context)
        semantic_cache[cache_key] = payload
        return payload

    question_type = _classify_question(question)
    entities = _extract_inventory_entities(question)
    inventory = _structured_inventory_search(entities, {"query": question}, limit=5)

    kb = query_knowledge_base(question, top_k=4)
    kb_contexts = kb.get("contexts") if isinstance(kb, dict) else []
    kb_contexts = kb_contexts if isinstance(kb_contexts, list) else []

    nhtsa = fetch_nhtsa(
        vin=entities.get("vin"),
        make=entities.get("make"),
        model=entities.get("model"),
        year=entities.get("year"),
    )
    fe = fetch_fueleconomy(make=entities.get("make"), model=entities.get("model"), year=entities.get("year"))
    kbb = fetch_kbb(vin=entities.get("vin"), make=entities.get("make"), model=entities.get("model"), year=entities.get("year"))
    carfax = fetch_carfax(vin=entities.get("vin"), make=entities.get("make"), model=entities.get("model"), year=entities.get("year"))

    sources: list[str] = []
    answer_sections: list[str] = []

    rows = inventory.get("rows") if isinstance(inventory, dict) else []
    rows = rows if isinstance(rows, list) else []
    if rows:
        answer_sections.append(_build_answer_from_inventory_row(rows[0]))
        sources.append("Live Inventory")

    if kb_contexts:
        first_context = kb_contexts[0].get("text", "")
        if first_context:
            answer_sections.append(str(first_context).strip())
        sources.append("Knowledge Base")
        if any("wikipedia" in str(ctx.get("source", "")).lower() for ctx in kb_contexts):
            sources.append("Wikipedia")

    if isinstance(nhtsa, dict) and nhtsa.get("status") == "ok":
        sources.append("NHTSA")
    if isinstance(fe, dict) and fe.get("status") == "ok":
        sources.append("FuelEconomy.gov")
    if isinstance(kbb, dict) and kbb.get("status") == "ok":
        sources.append("KBB")
    if isinstance(carfax, dict) and carfax.get("status") == "ok":
        sources.append("Carfax")

    if question_type == "maintenance_schedule":
        answer_sections = [_build_maintenance_answer()]
        if "Template" not in sources:
            sources.append("Template")

    if question_type == "financing" and not answer_sections:
        answer_sections.append("We can review APR, monthly payment, and total cost options tailored to your budget.")
        sources.append("Template")

    if not answer_sections:
        answer_sections.append("General knowledge skill is ready. Hybrid retrieval logic will be added here.")
        sources.append("Template")

    # Remove duplicates while preserving order.
    deduped_sources = list(dict.fromkeys(sources))
    answer = "\n\n".join(section for section in answer_sections if section)
    if deduped_sources:
        answer = f"{answer}\n\nSources: {_build_sources_label(deduped_sources)}."

    if len(deduped_sources) > 1:
        source = "multi_source"
    elif deduped_sources == ["Live Inventory"]:
        source = "inventory"
    elif deduped_sources == ["Knowledge Base"] or deduped_sources == ["Knowledge Base", "Wikipedia"]:
        source = "knowledge_base"
    else:
        source = "template"

    feedback = log_feedback_interaction(
        question=question,
        answer=answer,
        question_type=question_type,
        source=source,
        context=customer_context,
        rating=0,
    )

    payload = {
        "answer": answer,
        "question_type": question_type,
        "source": source,
        "metadata": {
            "sources": deduped_sources,
            "role": _detect_customer_role(question)[0],
            "tone": _detect_customer_role(question)[1],
        },
        "knowledge_contexts": kb_contexts,
        "interaction_id": feedback.get("interaction_id"),
        "conflict_mode": _detect_conflict_mode(question),
    }
    semantic_cache[cache_key] = payload
    return payload


def ask_imperial(
    question: str,
    customer_context: Optional[Dict[str, Any]] = None,
    prefer_template: bool = False,
) -> Dict[str, Any]:
    return ask_imperial_detailed(question=question, customer_context=customer_context, prefer_template=prefer_template)


def ask_imperial_stream(question: str, customer_context: Optional[Dict[str, Any]] = None):
    result = ask_imperial(question=question, customer_context=customer_context)
    answer = str(result.get("answer", ""))
    yield {"content": answer, "delta": answer}
