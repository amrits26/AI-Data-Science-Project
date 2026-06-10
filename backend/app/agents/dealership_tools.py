"""Dealership tools: lead scoring, trade-in appraisal, and daily briefing."""

from __future__ import annotations

import os
import json
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from .modeling import recommend_and_run_models
from .anomaly import run_anomaly_detection
from .orchestrator import AnalysisOrchestrator


_clip_model = None
_clip_processor = None


def _get_data_dir() -> str:
    data_dir = os.getenv("DATA_DIR", "./data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _leads_path() -> str:
    return os.path.join(_get_data_dir(), "leads.csv")


def _deals_path() -> str:
    return os.path.join(_get_data_dir(), "deals.csv")


def _deal_notification_state_path() -> str:
    return os.path.join(_get_data_dir(), "deal_status_notifications.json")


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        cleaned = str(value).replace(",", "").replace("$", "").strip()
        return float(cleaned) if cleaned else None
    except Exception:
        return None


def _split_vehicle_interest(value: Any) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "unknown", "unknown"
    parts = text.split()
    if len(parts) == 1:
        return parts[0], "unknown"
    return parts[0], " ".join(parts[1:])


def _coerce_sold_target(series: pd.Series) -> pd.Series:
    mapping_true = {"1", "true", "yes", "y", "sold", "closed", "won"}
    return series.fillna("").astype(str).str.strip().str.lower().map(lambda x: 1 if x in mapping_true else 0)


def _prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    if "sale_price" in work.columns and "total_price" not in work.columns:
        work["total_price"] = work["sale_price"]

    num_cols = [
        c
        for c in ["sale_price", "deposit", "trade_in_allowance", "total_price"]
        if c in work.columns
    ]
    for col in num_cols:
        work[col] = work[col].apply(_safe_float)

    text_cols = [
        c
        for c in [
            "customer_name",
            "phone",
            "email",
            "vehicle_interest",
            "trade_in_make",
            "trade_in_model",
        ]
        if c in work.columns
    ]
    for col in text_cols:
        work[col] = work[col].fillna("").astype(str)
        work[f"{col}_len"] = work[col].str.len().astype(float)

    feature_cols = [c for c in work.columns if c.endswith("_len") or c in num_cols]
    if not feature_cols:
        feature_cols = []
        for col in work.columns:
            if pd.api.types.is_numeric_dtype(work[col]):
                feature_cols.append(col)

    X = work[feature_cols].copy() if feature_cols else pd.DataFrame(index=work.index)
    if not X.empty:
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return X


def score_leads_from_csv() -> dict[str, Any]:
    """Score leads using modeling pipeline + local RF probability when sold target exists."""
    csv_path = _leads_path()
    if not os.path.exists(csv_path):
        return {
            "status": "ok",
            "message": f"No leads file found at {csv_path}. Upload lead forms first.",
            "total_leads": 0,
            "top_leads": [],
        }

    df = pd.read_csv(csv_path)
    if df.empty:
        return {
            "status": "ok",
            "message": "Leads file is empty. Upload lead forms first.",
            "total_leads": 0,
            "top_leads": [],
        }

    modeling_info = recommend_and_run_models(df, target_column="sold") if "sold" in df.columns else {
        "message": "Target column 'sold' is missing; trained model scoring skipped."
    }

    ranked: list[dict[str, Any]] = []
    if "sold" in df.columns:
        X = _prepare_features(df)
        y = _coerce_sold_target(df["sold"])

        if not X.empty and y.nunique() >= 2 and len(X) >= 10:
            model = RandomForestClassifier(n_estimators=200, random_state=42)
            model.fit(X, y)
            probs = model.predict_proba(X)[:, 1]
        else:
            probs = np.full(shape=len(df), fill_value=0.5)
    else:
        probs = np.full(shape=len(df), fill_value=0.5)

    for idx, row in df.iterrows():
        prob = float(probs[idx])
        ranked.append(
            {
                "lead_id": int(idx),
                "customer_name": str(row.get("customer_name", "") or "Unknown"),
                "phone": str(row.get("phone", "") or ""),
                "email": str(row.get("email", "") or ""),
                "vehicle_interest": str(row.get("vehicle_interest", "") or ""),
                "predicted_sale_prob": round(prob, 4),
                "priority": "hot" if prob >= 0.75 else ("warm" if prob >= 0.5 else "cold"),
            }
        )

    ranked.sort(key=lambda x: x["predicted_sale_prob"], reverse=True)

    return {
        "status": "ok",
        "csv_path": csv_path,
        "total_leads": len(ranked),
        "average_probability": round(float(np.mean([r["predicted_sale_prob"] for r in ranked])), 4) if ranked else 0.0,
        "modeling_summary": modeling_info.get("summary") or modeling_info.get("message", "Modeling completed."),
        "top_leads": ranked[:10],
    }


def rank_leads_by_profit(leads_csv: str | None = None) -> list[dict[str, Any]]:
    """
    Load leads.csv and deals.csv, train a RandomForest to predict gross_profit,
    return top 5 leads with estimated profit.
    """
    data_dir = _get_data_dir()
    leads_path = leads_csv or os.path.join(data_dir, "leads.csv")
    deals_path = os.path.join(data_dir, "deals.csv")

    if not os.path.exists(deals_path):
        return [{"error": "No deals.csv found. Add historical deals to enable profit ranking."}]
    if not os.path.exists(leads_path):
        return [{"error": "No leads.csv found."}]

    df_leads = pd.read_csv(leads_path)
    if df_leads.empty:
        return [{"error": "leads.csv is empty."}]

    for col in ["sale_price", "deposit", "trade_in_allowance"]:
        if col in df_leads.columns:
            df_leads[col] = df_leads[col].apply(_safe_float)

    if "vehicle_interest" in df_leads.columns:
        parsed = df_leads["vehicle_interest"].apply(_split_vehicle_interest)
        df_leads["make"] = parsed.apply(lambda x: x[0])
        df_leads["model"] = parsed.apply(lambda x: x[1])

    try:
        df_deals = pd.read_csv(deals_path)
        if df_deals.empty:
            raise ValueError("deals.csv is empty")

        for col in ["sale_price", "trade_in_value", "commission", "gross_profit", "year", "mileage"]:
            if col in df_deals.columns:
                df_deals[col] = pd.to_numeric(df_deals[col], errors="coerce")

        train_cols = [c for c in ["sale_price", "trade_in_value", "commission", "year", "mileage", "make", "model"] if c in df_deals.columns]
        if "gross_profit" not in df_deals.columns or len(train_cols) < 2:
            raise ValueError("insufficient training columns")

        train = df_deals[train_cols + ["gross_profit"]].dropna(subset=["gross_profit"]).copy()
        if train.empty:
            raise ValueError("no valid gross_profit values")

        X_train = pd.get_dummies(train[train_cols], dummy_na=True)
        y_train = train["gross_profit"].astype(float)

        model = RandomForestRegressor(n_estimators=200, random_state=42)
        model.fit(X_train, y_train)

        pred_cols = [c for c in ["sale_price", "trade_in_allowance", "deposit", "year", "mileage", "make", "model"] if c in df_leads.columns]
        predict_df = df_leads[pred_cols].copy()
        if "trade_in_allowance" in predict_df.columns and "trade_in_value" not in predict_df.columns:
            predict_df["trade_in_value"] = predict_df["trade_in_allowance"]
            pred_cols = [c if c != "trade_in_allowance" else "trade_in_value" for c in pred_cols]

        predict_df = predict_df.rename(columns={"trade_in_allowance": "trade_in_value"})
        X_pred = pd.get_dummies(predict_df, dummy_na=True)
        X_pred = X_pred.reindex(columns=X_train.columns, fill_value=0)
        df_leads["estimated_profit"] = model.predict(X_pred)
    except Exception:
        # Fallback heuristic if model training/prediction is not possible.
        df_leads["estimated_profit"] = df_leads.get("sale_price", 0).fillna(0).astype(float) * 0.2

    cols = [c for c in ["customer_name", "vehicle_interest", "estimated_profit"] if c in df_leads.columns]
    if "customer_name" not in cols:
        df_leads["customer_name"] = "Unknown"
        cols.insert(0, "customer_name")
    if "vehicle_interest" not in cols:
        df_leads["vehicle_interest"] = "Unknown"
        cols.insert(1, "vehicle_interest")

    top5 = df_leads.nlargest(5, "estimated_profit")[cols].copy()
    top5["estimated_profit"] = top5["estimated_profit"].astype(float).round(2)
    return top5.to_dict("records")


def detect_damage(image_path: str) -> str:
    """Zero-shot CLIP classification: clean, minor, major."""
    global _clip_model, _clip_processor
    try:
        from transformers import CLIPProcessor, CLIPModel

        if _clip_model is None or _clip_processor is None:
            _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

        image = Image.open(image_path).convert("RGB")
        labels = [
            "clean car with no damage",
            "minor dents or scratches",
            "major damage like large dents or broken parts",
        ]
        inputs = _clip_processor(text=labels, images=image, return_tensors="pt", padding=True)
        outputs = _clip_model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=1)
        idx = int(probs.argmax().item())
        return ["clean", "minor", "major"][idx]
    except Exception:
        return "clean"


def _ensure_market_values_seed(path: str) -> None:
    if os.path.exists(path):
        return
    seed = pd.DataFrame(
        [
            {"make": "Toyota", "model": "Camry", "year": 2020, "mileage": 35000, "condition": "good", "market_value": 21500},
            {"make": "Toyota", "model": "Camry", "year": 2019, "mileage": 52000, "condition": "fair", "market_value": 17800},
            {"make": "Honda", "model": "Civic", "year": 2021, "mileage": 28000, "condition": "good", "market_value": 20800},
            {"make": "Ford", "model": "F-150", "year": 2018, "mileage": 64000, "condition": "fair", "market_value": 24400},
            {"make": "Nissan", "model": "Altima", "year": 2020, "mileage": 41000, "condition": "good", "market_value": 18600},
        ]
    )
    seed.to_csv(path, index=False)


def appraise_trade_in(
    make: str,
    model: str,
    year: int,
    mileage: int,
    condition: str = "good",
    damage_level: str = "clean",
) -> dict[str, Any]:
    """Appraise a trade-in using local market_values.csv and deterministic fallback."""
    data_dir = _get_data_dir()
    market_path = os.path.join(data_dir, "market_values.csv")
    _ensure_market_values_seed(market_path)

    condition_norm = (condition or "good").strip().lower()
    condition_factor = {
        "excellent": 1.06,
        "good": 1.0,
        "fair": 0.9,
        "poor": 0.78,
    }.get(condition_norm, 1.0)

    try:
        mdf = pd.read_csv(market_path)
    except Exception as exc:
        return {"status": "error", "message": f"Unable to read market values: {exc}"}

    subset = mdf[
        (mdf["make"].astype(str).str.lower() == str(make).lower())
        & (mdf["model"].astype(str).str.lower() == str(model).lower())
    ].copy()

    if subset.empty:
        base = 24000.0
    else:
        subset["year_dist"] = (subset["year"].astype(int) - int(year)).abs()
        subset["mile_dist"] = (subset["mileage"].astype(float) - float(mileage)).abs()
        subset = subset.sort_values(["year_dist", "mile_dist"]).head(5)
        base = float(subset["market_value"].median())

    age = max(0, datetime.utcnow().year - int(year))
    age_factor = max(0.45, 1.0 - (age * 0.06))
    mileage_factor = max(0.65, 1.0 - (max(0, int(mileage) - 12000 * max(age, 1)) / 200000.0))

    estimate = base * age_factor * mileage_factor * condition_factor
    estimate = max(1200.0, estimate)

    adjustment = 1.0
    if damage_level == "minor":
        adjustment = 0.9
    elif damage_level == "major":
        adjustment = 0.85

    estimate = estimate * adjustment

    anomaly_snapshot = None
    if not subset.empty:
        anomaly_df = subset[["year", "mileage", "market_value"]].copy()
        anomaly_snapshot = run_anomaly_detection(anomaly_df)

    return {
        "status": "ok",
        "vehicle": {
            "make": make,
            "model": model,
            "year": int(year),
            "mileage": int(mileage),
            "condition": condition_norm,
        },
        "appraisal": {
            "recommended_offer": round(estimate, 2),
            "offer_range_low": round(estimate * 0.92, 2),
            "offer_range_high": round(estimate * 1.08, 2),
            "currency": "USD",
        },
        "damage_level": damage_level,
        "damage_adjustment": adjustment,
        "reference": {
            "market_file": market_path,
            "matching_records": int(len(subset)) if not subset.empty else 0,
        },
        "market_anomaly_analysis": anomaly_snapshot,
    }


def daily_briefing() -> dict[str, Any]:
    """Run orchestrator on leads and return health, anomalies, and top leads summary."""
    csv_path = _leads_path()
    if not os.path.exists(csv_path):
        return {
            "status": "ok",
            "summary": "No leads data available yet. Upload lead forms to generate daily briefing.",
            "health": None,
            "anomalies": None,
            "top_leads": [],
        }

    df = pd.read_csv(csv_path)
    if df.empty:
        return {
            "status": "ok",
            "summary": "Leads CSV is empty. No briefing generated.",
            "health": None,
            "anomalies": None,
            "top_leads": [],
        }

    target_col = "sold" if "sold" in df.columns else None
    orchestration = AnalysisOrchestrator(df=df, target_column=target_col).run()
    scored = score_leads_from_csv()

    health = orchestration.get("data_health", {})
    anomaly = orchestration.get("anomaly", {})
    top_leads = scored.get("top_leads", [])[:3]

    summary = (
        f"Daily briefing: {len(df)} leads analyzed. "
        f"Health score {health.get('score', health.get('data_health_score', 'N/A'))}. "
        f"Anomaly snapshot: {anomaly.get('combined_summary', 'No anomaly summary available.')}. "
        f"Top leads available: {len(top_leads)}."
    )

    return {
        "status": "ok",
        "summary": summary,
        "health": health,
        "health_score": health.get("score", health.get("data_health_score")),
        "anomalies": anomaly,
        "top_anomalies": anomaly.get("combined_summary"),
        "top_leads": top_leads,
        "top_3_leads": top_leads,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def list_deals(limit: int = 100) -> list[dict[str, Any]]:
    """Return deals from local deals.csv with inferred defaults."""
    path = _deals_path()
    if not os.path.exists(path):
        return []

    try:
        df = pd.read_csv(path)
    except Exception:
        return []

    if "status" not in df.columns:
        df["status"] = "open"

    if "stock_number" not in df.columns:
        df["stock_number"] = [f"ROW-{i+1}" for i in range(len(df))]

    rows = df.head(max(1, min(limit, 1000))).fillna("").to_dict("records")
    return rows


def _load_deal_notification_state() -> dict[str, Any]:
    path = _deal_notification_state_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_deal_notification_state(state: dict[str, Any]) -> None:
    path = _deal_notification_state_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def update_deal_status(
    stock_number: str,
    new_status: str,
    customer_id: int | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """Update deal status in deals.csv and trigger follow-up on waiting_insurance transitions.

    Idempotency guard: a follow-up is sent once per deal per waiting_insurance transition record.
    """
    path = _deals_path()
    if not os.path.exists(path):
        return {"status": "failed", "error": "deals.csv not found"}

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}

    if "stock_number" not in df.columns:
        df["stock_number"] = [f"ROW-{i+1}" for i in range(len(df))]

    if "status" not in df.columns:
        df["status"] = "open"

    mask = df["stock_number"].astype(str).str.lower().str.strip() == str(stock_number).lower().strip()
    if not mask.any():
        return {"status": "failed", "error": f"Deal not found for stock_number={stock_number}"}

    idx = df.index[mask][0]
    previous_status = str(df.at[idx, "status"] or "").strip().lower()
    normalized_new = str(new_status or "").strip().lower()
    df.at[idx, "status"] = normalized_new
    df.to_csv(path, index=False)

    trigger_result: dict[str, Any] | None = None
    notification_state = _load_deal_notification_state()
    state_key = str(stock_number).strip().lower()

    should_trigger = (
        normalized_new == "waiting_insurance"
        and previous_status != "waiting_insurance"
        and notification_state.get(state_key) != "waiting_insurance"
        and customer_id is not None
    )

    if should_trigger:
        from .customer_updates import send_followup_by_preferences

        followup_message = (
            message
            or "Your deal is currently waiting on insurance verification. Please share updated insurance details so we can proceed."
        )
        trigger_result = send_followup_by_preferences(int(customer_id), followup_message)
        notification_state[state_key] = "waiting_insurance"
        _save_deal_notification_state(notification_state)

    if normalized_new != "waiting_insurance":
        if state_key in notification_state:
            notification_state.pop(state_key, None)
            _save_deal_notification_state(notification_state)

    return {
        "status": "ok",
        "stock_number": stock_number,
        "previous_status": previous_status,
        "new_status": normalized_new,
        "followup_triggered": bool(trigger_result),
        "followup_result": trigger_result,
    }


def calculate_lead_quality_score(
    name: str,
    phone: str,
    email: str,
    message: str,
    desired_vehicle: str,
) -> dict[str, Any]:
    """Lightweight deterministic lead quality score for quick triage."""
    has_name = bool(str(name or "").strip())
    has_phone = bool(str(phone or "").strip())
    has_email = bool(str(email or "").strip())
    msg_len = len(str(message or "").strip())
    has_vehicle = bool(str(desired_vehicle or "").strip())

    completeness = sum([has_name, has_phone, has_email, has_vehicle]) / 4.0
    intent_strength = min(msg_len / 140.0, 1.0)

    score = (completeness * 0.65) + (intent_strength * 0.35)
    pct = round(score * 100, 2)

    if pct >= 80:
        tier = "hot"
    elif pct >= 55:
        tier = "warm"
    else:
        tier = "cold"

    return {
        "status": "ok",
        "score": pct,
        "tier": tier,
        "components": {
            "completeness": round(completeness, 3),
            "intent_strength": round(intent_strength, 3),
        },
    }


def track_sales_stage(stock_number: str, stage: str) -> dict[str, Any]:
    """Persist and return sales stage transitions via deals.csv."""
    allowed = {
        "new_lead",
        "contacted",
        "appointment_set",
        "test_drive",
        "negotiation",
        "waiting_insurance",
        "funded",
        "closed_won",
        "closed_lost",
    }
    normalized = str(stage or "").strip().lower()
    if normalized not in allowed:
        return {
            "status": "failed",
            "error": f"Invalid stage '{stage}'. Allowed: {', '.join(sorted(allowed))}",
        }

    return update_deal_status(stock_number=stock_number, new_status=normalized)
