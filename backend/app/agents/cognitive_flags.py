"""
Cognitive Flags: data leakage risk, Simpson's paradox possibility,
multicollinearity, high cardinality, small sample bias.
"""
import numpy as np
import pandas as pd
from typing import Any


def _multicollinearity_flags(statistical: dict[str, Any] | None) -> list[dict[str, Any]]:
    flags = []
    if not statistical or "correlation" not in statistical:
        return flags
    high = statistical["correlation"].get("high_corr_pairs", [])
    if len(high) > 5:
        flags.append({
            "flag_id": "multicollinearity",
            "severity": "warning",
            "title": "Multicollinearity warning",
            "description": f"{len(high)} feature pairs have |correlation| > 0.7. Consider VIF or dropping one of each pair.",
            "math_detail": "VIF = 1/(1-R²) for each regressor; VIF > 5–10 suggests multicollinearity.",
            "recommendation": "Run VIF or remove highly correlated features before linear models.",
        })
    return flags


def _leakage_flags(profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    flags = []
    if not profile or not profile.get("leakage_indicators"):
        return flags
    for ind in profile["leakage_indicators"]:
        flags.append({
            "flag_id": "data_leakage_risk",
            "severity": "critical",
            "title": "Data leakage risk",
            "description": ind,
            "math_detail": "Features that uniquely identify the target (e.g. IDs, future info) inflate metrics.",
            "recommendation": "Remove or mask ID-like and future-leaking columns before modeling.",
        })
    return flags


def _high_cardinality_flags(profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    flags = []
    if not profile or "column_profiles" not in profile:
        return flags
    for cp in profile.get("column_profiles", []):
        card = cp.get("cardinality")
        if card is not None and card > 100:
            flags.append({
                "flag_id": "high_cardinality",
                "severity": "warning",
                "title": "High cardinality warning",
                "description": f"Feature '{cp['name']}' has {card} unique values.",
                "math_detail": "High cardinality can cause overfitting and slow tree models.",
                "recommendation": "Consider grouping, hashing, or target encoding.",
            })
    return flags


def _small_sample_flags(profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    flags = []
    if not profile:
        return flags
    n = profile.get("rows", 0)
    if n < 100:
        flags.append({
            "flag_id": "small_sample_bias",
            "severity": "warning",
            "title": "Small sample bias",
            "description": f"Only {n} rows. Results may have high variance and poor generalization.",
            "math_detail": "Standard errors scale with 1/√n; small n implies wide confidence intervals.",
            "recommendation": "Report confidence intervals; consider simpler models or more data.",
        })
    return flags


def _simpsons_paradox_hint(statistical: dict[str, Any] | None, profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Hint that Simpson's paradox is possible when correlations exist and data is grouped."""
    flags = []
    if not statistical or "correlation" not in statistical:
        return flags
    high = statistical["correlation"].get("high_corr_pairs", [])
    if high and profile and profile.get("rows", 0) > 100:
        flags.append({
            "flag_id": "simpsons_paradox",
            "severity": "info",
            "title": "Simpson's paradox possibility",
            "description": "Aggregate correlations may reverse within subgroups. Check stratifications (e.g. by segment or time).",
            "math_detail": "P(A|B) vs P(A|B,C) can have opposite signs when C is a confounder.",
            "recommendation": "Stratify analysis by likely confounders and report per-group effects.",
        })
    return flags


def _feature_dominance_flags(modeling: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Flag when one or few features dominate importance."""
    flags = []
    if not modeling or "feature_importance" not in modeling:
        return flags
    imp = modeling.get("feature_importance") or {}
    if not imp:
        return flags
    total = sum(imp.values()) or 1
    sorted_imp = sorted(imp.items(), key=lambda t: -t[1])
    top1_pct = 100.0 * sorted_imp[0][1] / total if sorted_imp else 0
    if top1_pct > 50:
        flags.append({
            "flag_id": "feature_dominance",
            "severity": "warning",
            "title": "Feature dominance imbalance detected",
            "description": f"'{sorted_imp[0][0]}' accounts for {top1_pct:.0f}% of feature importance.",
            "math_detail": "Single-feature dominance may indicate leakage or a proxy for the target.",
            "recommendation": "Validate that the dominant feature is not leaking target information.",
        })
    return flags


def _overfitting_risk_flags(modeling: dict[str, Any] | None) -> list[dict[str, Any]]:
    flags = []
    if not modeling or not modeling.get("overfitting_risk"):
        return flags
    flags.append({
        "flag_id": "overfitting_risk",
        "severity": "warning",
        "title": "Potential overfitting risk",
        "description": modeling["overfitting_risk"],
        "math_detail": "High train/cv performance with limited data suggests overfitting (high variance).",
        "recommendation": "Use regularization, cross-validation, or collect more data.",
    })
    return flags


def _target_influence_flags(modeling: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Target strongly influenced by few variables."""
    flags = []
    if not modeling or "feature_importance" not in modeling:
        return flags
    imp = modeling.get("feature_importance") or {}
    if not imp:
        return flags
    sorted_imp = sorted(imp.items(), key=lambda t: -t[1])[:5]
    top3_sum = sum(t[1] for t in sorted_imp[:3])
    total = sum(imp.values()) or 1
    if total and top3_sum / total > 0.7:
        names = ", ".join(t[0] for t in sorted_imp[:3])
        flags.append({
            "flag_id": "target_influence",
            "severity": "info",
            "title": "Target strongly influenced by few variables",
            "description": f"Top 3 features ({names}) explain >70% of importance.",
            "math_detail": "Concentrated importance suggests interpretable, sparse drivers.",
            "recommendation": "Focus reporting and monitoring on these key drivers.",
        })
    return flags


def compute_cognitive_flags(
    profile: dict[str, Any] | None = None,
    statistical: dict[str, Any] | None = None,
    modeling: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Compute cognitive flags: leakage, Simpson's paradox, multicollinearity,
    high cardinality, small sample, feature dominance, overfitting, target influence.
    """
    flags = []
    flags.extend(_leakage_flags(profile))
    flags.extend(_multicollinearity_flags(statistical))
    flags.extend(_high_cardinality_flags(profile))
    flags.extend(_small_sample_flags(profile))
    flags.extend(_simpsons_paradox_hint(statistical, profile))
    flags.extend(_feature_dominance_flags(modeling))
    flags.extend(_overfitting_risk_flags(modeling))
    flags.extend(_target_influence_flags(modeling))
    return flags
