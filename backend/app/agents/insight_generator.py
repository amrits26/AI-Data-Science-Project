"""
AI Insight Generator: turn structured outputs into executive summary,
business implications, risks, model justification, next steps.

LLM priority:
  1. Anthropic Claude (ANTHROPIC_API_KEY)  ← preferred
  2. OpenAI-compatible (OPENAI_API_KEY)
  3. Template fallback (no key required)
"""
import json
import os
from typing import Any


def _template_executive_summary(
    profile: dict[str, Any],
    statistical: dict[str, Any],
    modeling: dict[str, Any],
    anomaly: dict[str, Any],
    flags: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a rich executive summary from structured data when no LLM is configured."""
    bullets = []
    bullets.append(f"The dataset contains {profile.get('rows', 0)} rows and {profile.get('columns', 0)} columns, with a data health score of {profile.get('data_health_score', 0)}/100.")
    if profile.get("class_imbalance"):
        bullets.append(f"Class imbalance is present (minority class {profile['class_imbalance'].get('minority_pct')}%); consider stratified sampling or resampling.")
    if profile.get("leakage_indicators"):
        bullets.append(f"Leakage risk: {len(profile['leakage_indicators'])} indicator(s) suggest reviewing ID-like or future-leaking columns.")
    bullets.append(statistical.get("summary", "Statistical checks were run."))
    if modeling.get("inferred_task"):
        bullets.append(f"Modeling: inferred task is {modeling['inferred_task']}. {modeling.get('summary', '')}")
    if modeling.get("overfitting_risk"):
        bullets.append(f"Caution: {modeling['overfitting_risk']}")
    bullets.append(anomaly.get("combined_summary", "Anomaly detection was run."))
    if flags:
        bullets.append(f"Cognitive flags: {len(flags)} issue(s) or recommendation(s) — review before productionizing.")

    implications = []
    if profile.get("data_health_score", 0) >= 70:
        implications.append("Data quality is acceptable for modeling; minor cleaning may still help.")
    if modeling.get("best_model"):
        implications.append(f"Best performing model: {modeling['best_model']}; suitable as a baseline for production.")
    if anomaly.get("average_anomaly_pct", 0) > 5:
        implications.append("Anomaly rate is notable; consider separate handling or investigation of outliers.")

    risks = []
    for f in flags:
        if f.get("severity") == "critical":
            risks.append(f.get("title", "") + ": " + f.get("description", ""))
    if modeling.get("overfitting_risk"):
        risks.append("Overfitting: " + modeling["overfitting_risk"])

    next_steps = [
        "Review cognitive flags and fix leakage/high cardinality if needed.",
        "Apply recommended transforms (e.g. log) for skewed features.",
        "Validate best model on a held-out set and monitor drift in production.",
    ]
    if not modeling.get("best_model") and modeling.get("inferred_task") == "clustering":
        next_steps.insert(0, "Choose number of clusters (e.g. from elbow plot) and interpret segments.")

    return {
        "summary": " ".join(bullets[:4]) + (" " + " ".join(bullets[4:7]) if len(bullets) > 4 else "") + ".",
        "business_implications": implications,
        "risks": risks,
        "model_justification": f"Inferred task: {modeling.get('inferred_task', 'unknown')}. {modeling.get('summary', '')}" if modeling else None,
        "next_steps": next_steps,
        "technical_notes": "Generated from automated profiling, statistics, modeling, and anomaly detection.",
    }


def _call_anthropic(prompt: str, system: str) -> str | None:
    """Call Anthropic Claude API if ANTHROPIC_API_KEY is set (preferred LLM)."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        message = client.messages.create(
            model=model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return (message.content[0].text or "").strip()
    except Exception:
        return None


def _call_openai(prompt: str, system: str) -> str | None:
    """Call OpenAI-compatible API if OPENAI_API_KEY is set (fallback)."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import openai
        client = openai.OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_API_BASE") or None)
        r = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
        )
        return (r.choices[0].message.content or "").strip()
    except Exception:
        return None


def _call_llm(prompt: str, system: str) -> str | None:
    """Try Anthropic first, fall back to OpenAI."""
    result = _call_anthropic(prompt, system)
    if result:
        return result
    return _call_openai(prompt, system)


def generate_insights(
    profile: dict[str, Any],
    statistical: dict[str, Any],
    modeling: dict[str, Any],
    anomaly: dict[str, Any],
    flags: list[dict[str, Any]],
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    Generate executive summary, business implications, risks, model justification,
    next steps. If OPENAI_API_KEY is set and use_llm=True, use LLM; else template.
    """
    template = _template_executive_summary(profile, statistical, modeling, anomaly, flags)

    if use_llm:
        system = (
            "You are a senior data scientist. Given JSON summaries of data profiling, "
            "statistics, modeling, anomaly detection, and cognitive flags, produce a short "
            "executive summary in plain English, then list business implications, risks, "
            "model justification, and recommended next steps. Be concise and actionable."
        )
        payload = {
            "profile_summary": profile.get("summary"),
            "data_health_score": profile.get("data_health_score"),
            "statistical_summary": statistical.get("summary"),
            "modeling_summary": modeling.get("summary"),
            "anomaly_summary": anomaly.get("combined_summary"),
            "cognitive_flags_count": len(flags),
            "flags_sample": [{"title": f.get("title"), "severity": f.get("severity")} for f in flags[:5]],
        }
        prompt = "Summarize this data science run for an executive:\n\n" + json.dumps(payload, indent=2)
        llm_text = _call_llm(prompt, system)
        if llm_text:
            return {
                "summary": llm_text,
                "business_implications": template["business_implications"],
                "risks": template["risks"],
                "model_justification": template["model_justification"],
                "next_steps": template["next_steps"],
                "technical_notes": "LLM-generated summary.",
            }

    return template
