"""
Problem Type Inference Engine

Determines:
- Classification
- Regression
- Clustering
- Time Series

Also returns reasoning trace explaining the decision.
"""

from typing import Dict, Optional

import pandas as pd


LOW_CARDINALITY_THRESHOLD = 15
TIME_SERIES_MIN_DATETIME_RATIO = 0.6


def infer_problem_type(
    df: pd.DataFrame,
    target_column: Optional[str] = None,
) -> Dict:
    """
    Infer the type of ML problem from dataset structure.

    Returns:
        {
            "problem_type": str,
            "reasoning": list[str],
            "target_type": str | None
        }
    """

    reasoning = []

    # -----------------------------------
    # Case 1: No target provided
    # -----------------------------------
    if not target_column:
        datetime_cols = _detect_datetime_columns(df)

        if datetime_cols:
            reasoning.append(
                f"Detected datetime column(s): {datetime_cols}. "
                "No target provided — time series analysis recommended."
            )
            return {
                "problem_type": "time_series",
                "reasoning": reasoning,
                "target_type": None,
            }

        reasoning.append(
            "No target column provided. Defaulting to unsupervised clustering."
        )
        return {
            "problem_type": "clustering",
            "reasoning": reasoning,
            "target_type": None,
        }

    # -----------------------------------
    # Case 2: Target provided
    # -----------------------------------

    if target_column not in df.columns:
        reasoning.append(
            f"Target column '{target_column}' not found in dataset."
        )
        return {
            "problem_type": "unknown",
            "reasoning": reasoning,
            "target_type": None,
        }

    target_series = df[target_column]
    unique_values = target_series.nunique(dropna=True)

    # Numeric Target
    if pd.api.types.is_numeric_dtype(target_series):

        if unique_values <= LOW_CARDINALITY_THRESHOLD:
            reasoning.append(
                f"Target is numeric with {unique_values} unique values "
                f"(≤ {LOW_CARDINALITY_THRESHOLD}). Treating as classification."
            )
            return {
                "problem_type": "classification",
                "reasoning": reasoning,
                "target_type": "numeric_categorical",
            }

        reasoning.append(
            f"Target is numeric with {unique_values} unique values. "
            "Treating as regression."
        )
        return {
            "problem_type": "regression",
            "reasoning": reasoning,
            "target_type": "numeric_continuous",
        }

    # Categorical Target
    if pd.api.types.is_object_dtype(target_series) or pd.api.types.is_categorical_dtype(target_series):

        if unique_values <= LOW_CARDINALITY_THRESHOLD:
            reasoning.append(
                f"Target is categorical with {unique_values} classes. "
                "Treating as classification."
            )
            return {
                "problem_type": "classification",
                "reasoning": reasoning,
                "target_type": "categorical",
            }

        reasoning.append(
            f"Target has high cardinality ({unique_values} classes). "
            "Classification may require encoding strategies."
        )
        return {
            "problem_type": "classification",
            "reasoning": reasoning,
            "target_type": "high_cardinality_categorical",
        }

    reasoning.append("Unable to confidently infer problem type.")
    return {
        "problem_type": "unknown",
        "reasoning": reasoning,
        "target_type": None,
    }


# -----------------------------------------------------
# Helper Functions
# -----------------------------------------------------


def _detect_datetime_columns(df: pd.DataFrame) -> list[str]:
    """
    Detect columns that appear to be datetime-like.
    """

    datetime_cols = []

    for col in df.columns:
        series = df[col]

        if pd.api.types.is_datetime64_any_dtype(series):
            datetime_cols.append(col)
            continue

        if series.dtype == "object":
            try:
                converted = pd.to_datetime(series, errors="coerce")
                valid_ratio = converted.notna().mean()

                if valid_ratio >= TIME_SERIES_MIN_DATETIME_RATIO:
                    datetime_cols.append(col)
            except Exception:
                continue

    return datetime_cols