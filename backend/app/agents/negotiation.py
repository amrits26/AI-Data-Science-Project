"""Negotiation coaching responses for showroom and digital sales."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.agents.vehicle_intel import get_similar_vehicles


_WINNING_SCRIPTS_PATH = Path("knowledge_base") / "winning_scripts.txt"


def _normalized(text: str) -> str:
    return (text or "").strip().lower()


def _intent_from_text(text: str) -> str:
    t = _normalized(text)
    if not t:
        return "general"

    rules = [
        ("monthly_payment", ["payment", "monthly", "budget"]),
        ("cash_price", ["cash", "out the door", "otd", "discount"]),
        ("trade_value", ["trade", "appraise", "my car"]),
        ("rate_apr", ["rate", "apr", "interest"]),
        ("delay_decision", ["think about", "not ready", "later", "spouse"]),
        ("competitor", ["other dealer", "competitor", "elsewhere", "another"]),
    ]

    for intent, keys in rules:
        if any(k in t for k in keys):
            return intent
    return "general"


def _load_winning_scripts() -> dict[str, dict[str, str]]:
    if not _WINNING_SCRIPTS_PATH.exists():
        return {}

    blocks = _WINNING_SCRIPTS_PATH.read_text(encoding="utf-8", errors="ignore").split("\n\n")
    scripts: dict[str, dict[str, str]] = {}
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or not lines[0].startswith("[Scenario:"):
            continue
        key = lines[0].replace("[Scenario:", "").replace("]", "").strip()
        payload = {"scenario": key, "example": "", "principle": ""}
        for line in lines[1:]:
            if ":" not in line:
                continue
            label, value = line.split(":", 1)
            normalized = label.strip().lower()
            cleaned = value.strip()
            if normalized in {"response", "script"}:
                payload["example"] = cleaned
            elif normalized == "principle":
                payload["principle"] = cleaned
        scripts[key] = payload
    return scripts


def _scenario_for_intent(intent: str) -> str:
    return {
        "monthly_payment": "objection_monthly_payment",
        "cash_price": "objection_price",
        "trade_value": "trust_building_trade",
        "rate_apr": "objection_credit",
        "delay_decision": "objection_think_about_it",
        "competitor": "competitor_comparison",
        "general": "true_need_triage",
    }.get(intent, "true_need_triage")


def cross_sell_alternatives(stock_number: str, max_results: int = 3) -> list[dict[str, Any]]:
    if not (stock_number or "").strip():
        return []
    return get_similar_vehicles(stock_number.strip(), max_results=max_results)


def negotiation_assistant(
    message: str,
    customer_name: str | None = None,
    stock_number: str | None = None,
    year: int | None = None,
    make: str | None = None,
    model: str | None = None,
    key_feature: str | None = None,
) -> dict[str, Any]:
    intent = _intent_from_text(message)
    winning_scripts = _load_winning_scripts()
    scenario = _scenario_for_intent(intent)
    script = winning_scripts.get(scenario, {})

    script_map = {
        "monthly_payment": {
            "ack": "Totally fair. Most customers shop by payment first.",
            "pivot": "If we could keep it around your target payment with the right term, would you move forward today?",
            "close": "Let me show 2 options side-by-side so you can pick what feels comfortable.",
        },
        "cash_price": {
            "ack": "I hear you. You want the strongest value up front.",
            "pivot": "Are you open to comparing total value, including warranty and reconditioning, not just the sticker?",
            "close": "If I can show this is the best total deal in-market, are you ready to wrap it up?",
        },
        "trade_value": {
            "ack": "Absolutely, your trade value matters.",
            "pivot": "Would you like to see a transparent appraisal breakdown so you know exactly how we got the number?",
            "close": "If we improve your trade by a bit and keep payment in range, can we finalize today?",
        },
        "rate_apr": {
            "ack": "Good question. Rate has a big impact.",
            "pivot": "We can submit to multiple lenders and structure term/down to lower total cost.",
            "close": "If I get lender options with clear monthly and total paid, do we have a deal?",
        },
        "delay_decision": {
            "ack": "Makes sense. Big decisions deserve clarity.",
            "pivot": "What specific question is still unanswered so we can solve that now?",
            "close": "If we solve that one concern, would today still work for you?",
        },
        "competitor": {
            "ack": "I appreciate you comparing options.",
            "pivot": "Let's compare apples-to-apples: miles, condition, warranty, and fees.",
            "close": "If ours wins on real total value, are you comfortable choosing this one?",
        },
        "general": {
            "ack": "Thanks for sharing that.",
            "pivot": "Can I clarify your top priority so I can tailor the best option?",
            "close": "If we align on that priority, are you ready for next steps?",
        },
    }

    chosen = script_map[intent]
    customer = customer_name or "there"
    vehicle_name = " ".join(part for part in [str(year or "").strip(), make or "", model or ""] if part).strip() or "this vehicle"
    feature_clause = f" Highlight {key_feature}." if key_feature else ""
    example_script = script.get("example") or chosen["ack"]
    principle = script.get("principle") or "Use service-minded confidence and a tie-down question."
    talk_track = (
        f"Use this tone model: {example_script}\n\n"
        f"Draft for {customer}: Based on what you've shared, {vehicle_name} is worth a closer look.{feature_clause} "
        f"{chosen['ack']} {chosen['pivot']} {chosen['close']}"
    ).strip()

    return {
        "intent": intent,
        "response": f"{chosen['ack']} {chosen['pivot']} {chosen['close']}",
        "example_script": example_script,
        "scenario": scenario,
        "principle": principle,
        "talk_track": talk_track,
        "cross_sell_alternatives": cross_sell_alternatives(stock_number or ""),
        "framework": chosen,
    }
