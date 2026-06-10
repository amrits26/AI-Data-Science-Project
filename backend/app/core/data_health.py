"""
Data Health Scoring Engine
Produces a 0–100 readiness score based on structural risk factors.
"""

import numpy as np
import pandas as pd


def compute_data_health_score(df: pd.DataFrame, target_column=None) -> dict:
    score = 100
    penalties = []
    n_rows, n_cols = df.shape

    # ----------------------------
    # Missing Value Penalty
    # ----------------------------
    missing_ratio = df.isna().mean().mean()
    if missing_ratio > 0.2:
        score -= 20
        penalties.append("High overall missing data (>20%)")
    elif missing_ratio > 0.1:
        score -= 10
        penalties.append("Moderate missing data (>10%)")

    # ----------------------------
    # Small Sample Size
    # ----------------------------
    if n_rows < 500:
        score -= 15
        penalties.append("Small sample size (<500 rows)")
    elif n_rows < 2000:
        score -= 5
        penalties.append("Limited sample size (<2000 rows)")

    # ----------------------------
    # High Cardinality
    # ----------------------------
    high_card_cols = [
        col for col in df.columns
        if df[col].nunique() > 0.5 * n_rows
    ]
    if high_card_cols:
        score -= 10
        penalties.append("High-cardinality feature(s) detected")

    # ----------------------------
    # Skewness
    # ----------------------------
    numeric_cols = df.select_dtypes(include=np.number).columns
    if len(numeric_cols) > 0:
        skew_vals = df[numeric_cols].skew().abs()
        if (skew_vals > 2).mean() > 0.3:
            score -= 10
            penalties.append("High skewness across numeric features")

    score = max(score, 0)

    return {
        "data_health_score": score,
        "penalties": penalties,
    }