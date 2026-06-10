"""
Data Profiler Agent: dataset profiling, health score, leakage indicators.
"""
import numpy as np
import pandas as pd
from typing import Any


def _safe_skew(series: pd.Series) -> float | None:
    if not pd.api.types.is_numeric_dtype(series) or series.nunique() < 2:
        return None
    try:
        from scipy.stats import skew
        return float(skew(series.dropna()))
    except Exception:
        return None


def _safe_kurtosis(series: pd.Series) -> float | None:
    if not pd.api.types.is_numeric_dtype(series) or series.nunique() < 2:
        return None
    try:
        from scipy.stats import kurtosis
        return float(kurtosis(series.dropna()))
    except Exception:
        return None


def _leakage_indicators(df: pd.DataFrame, target_col: str | None) -> list[str]:
    """Heuristic leakage indicators: ID-like columns, future info, near-perfect predictors."""
    indicators = []
    for col in df.columns:
        if col == target_col:
            continue
        s = df[col]
        # High cardinality + string often means ID
        if s.dtype == object or (s.dtype.name in ("string", "category")):
            uniq = s.nunique()
            if uniq >= 0.9 * len(df) and len(df) > 100:
                indicators.append(f"Column '{col}' has very high cardinality ({uniq} unique) and may be an ID (leakage risk).")
        # Numeric: exactly unique per row
        if pd.api.types.is_numeric_dtype(s):
            if s.nunique() >= 0.99 * len(df) and len(df) > 50:
                indicators.append(f"Column '{col}' is almost unique per row (possible index/ID).")
    return indicators


def _data_health_score(
    df: pd.DataFrame,
    missing_pcts: dict[str, float],
    leakage: list[str],
    high_cardinality_count: int,
) -> float:
    """Score 0-100: penalize missing data, leakage risk, high cardinality."""
    score = 100.0
    n_cols = len(df.columns) or 1
    avg_missing = sum(missing_pcts.values()) / n_cols if missing_pcts else 0
    score -= min(40, avg_missing * 2)  # up to 40 pts for missing
    score -= min(25, len(leakage) * 8)   # leakage
    score -= min(20, high_cardinality_count * 4)  # high cardinality
    return max(0.0, min(100.0, round(score, 1)))


def profile_dataset(df: pd.DataFrame, target_column: str | None = None) -> dict[str, Any]:
    """
    Profile the dataset: dtypes, missing %, skewness, kurtosis, cardinality,
    class imbalance (if target given), leakage indicators, and a data health score.
    """
    if df.empty or len(df.columns) == 0:
        return {
            "rows": 0,
            "columns": 0,
            "column_profiles": [],
            "data_health_score": 0.0,
            "class_imbalance": None,
            "leakage_indicators": [],
            "summary": "Empty dataset.",
        }

    column_profiles = []
    missing_pcts = {}
    high_cardinality_count = 0
    for col in df.columns:
        s = df[col]
        missing = s.isna().sum()
        missing_pct = round(100.0 * missing / len(df), 2)
        missing_pcts[col] = missing_pct
        numeric = pd.api.types.is_numeric_dtype(s)
        skewness = _safe_skew(s) if numeric else None
        kurtosis = _safe_kurtosis(s) if numeric else None
        card = int(s.nunique()) if s.dtype == object or s.dtype.name in ("string", "category") else None
        if card is not None and card > 100:
            high_cardinality_count += 1
        sample = s.dropna().head(5).astype(str).tolist() if s.dtype == object else None
        column_profiles.append({
            "name": col,
            "dtype": str(s.dtype),
            "missing_pct": missing_pct,
            "numeric": bool(numeric),
            "skewness": round(skewness, 4) if skewness is not None else None,
            "kurtosis": round(kurtosis, 4) if kurtosis is not None else None,
            "cardinality": card,
            "sample_values": sample,
        })

    leakage = _leakage_indicators(df, target_column)
    health = _data_health_score(df, missing_pcts, leakage, high_cardinality_count)

    class_imbalance = None
    if target_column and target_column in df.columns:
        counts = df[target_column].value_counts()
        if len(counts) <= 20:
            total = counts.sum()
            class_imbalance = {
                "classes": int(len(counts)),
                "distribution": {str(k): round(100.0 * v / total, 2) for k, v in counts.items()},
                "minority_pct": round(100.0 * counts.min() / total, 2),
            }

    summary = (
        f"Dataset has {len(df)} rows and {len(df.columns)} columns. "
        f"Data health score: {health}/100. "
    )
    if leakage:
        summary += f"Leakage risk: {len(leakage)} indicator(s). "
    if class_imbalance and class_imbalance["minority_pct"] < 10:
        summary += "Class imbalance detected; consider stratification or resampling. "

    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_profiles": column_profiles,
        "data_health_score": health,
        "class_imbalance": class_imbalance,
        "leakage_indicators": leakage,
        "summary": summary.strip(),
    }
