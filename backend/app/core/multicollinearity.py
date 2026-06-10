"""
Multicollinearity Detection using VIF
"""

import pandas as pd
import numpy as np
from statsmodels.stats.outliers_influence import variance_inflation_factor


def compute_vif_index(df: pd.DataFrame) -> dict:
    numeric_df = df.select_dtypes(include=np.number).dropna()

    if numeric_df.shape[1] < 2:
        return {"multicollinearity_index": 0, "high_vif_features": []}

    vif_data = []
    for i in range(numeric_df.shape[1]):
        try:
            vif = variance_inflation_factor(numeric_df.values, i)
            vif_data.append(vif)
        except Exception:
            vif_data.append(0)

    high_vif = [
        numeric_df.columns[i]
        for i, v in enumerate(vif_data)
        if v > 10
    ]

    index_score = min(int(len(high_vif) * 2), 10)

    return {
        "multicollinearity_index": index_score,
        "high_vif_features": high_vif,
    }