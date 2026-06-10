"""
Anomaly Detection Layer: Isolation Forest, Z-score rolling, optional DBSCAN.
"""
import numpy as np
import pandas as pd
from typing import Any


def _isolation_forest(df: pd.DataFrame, contamination: float = 0.05) -> dict[str, Any]:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    num = df.select_dtypes(include=[np.number]).dropna(axis="columns", how="all")
    if num.empty or len(num) < 10:
        return {"anomaly_pct": 0.0, "n_anomalies": 0, "method": "Isolation Forest", "summary": "Insufficient numeric data."}
    X = StandardScaler().fit_transform(num.fillna(num.median()))
    clf = IsolationForest(contamination=min(contamination, 0.5), random_state=42)
    pred = clf.fit_predict(X)
    n_anom = int((pred == -1).sum())
    pct = round(100.0 * n_anom / len(pred), 2)
    return {
        "method": "Isolation Forest",
        "n_anomalies": n_anom,
        "anomaly_pct": pct,
        "contamination": contamination,
        "summary": f"Isolation Forest: {pct}% of rows flagged as anomalous ({n_anom} points).",
    }


def _zscore_detection(df: pd.DataFrame, threshold: float = 3.0) -> dict[str, Any]:
    num = df.select_dtypes(include=[np.number]).dropna(axis="columns", how="all")
    if num.empty:
        return {"anomaly_pct": 0.0, "n_anomalies": 0, "method": "Z-score", "summary": "No numeric columns."}
    z = np.abs((num - num.mean()) / num.std().replace(0, 1))
    row_max_z = z.max(axis=1)
    n_anom = int((row_max_z > threshold).sum())
    pct = round(100.0 * n_anom / len(df), 2)
    return {
        "method": "Z-score",
        "threshold": threshold,
        "n_anomalies": n_anom,
        "anomaly_pct": pct,
        "summary": f"Z-score (|z| > {threshold}): {pct}% of rows have at least one extreme value.",
    }


def _dbscan_anomalies(df: pd.DataFrame, eps: float = 0.5, min_samples: int = 5) -> dict[str, Any]:
    from sklearn.cluster import DBSCAN
    from sklearn.preprocessing import StandardScaler
    num = df.select_dtypes(include=[np.number]).dropna(axis="columns", how="all")
    if num.empty or len(num) < 20:
        return {"anomaly_pct": 0.0, "n_noise": 0, "method": "DBSCAN", "summary": "Insufficient data for DBSCAN."}
    X = StandardScaler().fit_transform(num.fillna(num.median()))
    db = DBSCAN(eps=eps, min_samples=min_samples)
    labels = db.fit_predict(X)
    n_noise = int((labels == -1).sum())
    pct = round(100.0 * n_noise / len(labels), 2)
    return {
        "method": "DBSCAN",
        "eps": eps,
        "min_samples": min_samples,
        "n_noise": n_noise,
        "anomaly_pct": pct,
        "n_clusters": int(len(set(labels)) - (1 if -1 in labels else 0)),
        "summary": f"DBSCAN: {pct}% of points labeled as noise ({n_noise}).",
    }


def run_anomaly_detection(df: pd.DataFrame) -> dict[str, Any]:
    """
    Run Isolation Forest, Z-score, and DBSCAN. Return combined summary.
    """
    if df.empty:
        return {
            "isolation_forest": {"summary": "Empty dataset."},
            "zscore": {"summary": "Empty dataset."},
            "dbscan": {"summary": "Empty dataset."},
            "combined_summary": "No data to analyze.",
        }
    iso = _isolation_forest(df)
    zscore = _zscore_detection(df)
    dbscan = _dbscan_anomalies(df)

    # Only average percentages from methods that actually ran
    pcts = []
    methods_run = []
    if iso.get("anomaly_pct", 0) > 0 or "Insufficient" not in iso.get("summary", ""):
        pcts.append(iso.get("anomaly_pct", 0))
        methods_run.append("Isolation Forest")
    if zscore.get("anomaly_pct", 0) > 0 or "No numeric" not in zscore.get("summary", ""):
        pcts.append(zscore.get("anomaly_pct", 0))
        methods_run.append("Z-score")
    if dbscan.get("anomaly_pct", 0) > 0 or "Insufficient" not in dbscan.get("summary", ""):
        pcts.append(dbscan.get("anomaly_pct", 0))
        methods_run.append("DBSCAN")
    
    avg_pct = round(sum(pcts) / len(pcts), 1) if pcts else 0
    methods_note = f" (from {len(methods_run)} method{'s' if len(methods_run) != 1 else ''}: {', '.join(methods_run)})" if pcts else " (no methods applicable)"
    combined = (
        f"Anomaly detection: Isolation Forest {iso.get('anomaly_pct', 0)}%, "
        f"Z-score {zscore.get('anomaly_pct', 0)}%, DBSCAN {dbscan.get('anomaly_pct', 0)}%. "
        f"On average {avg_pct}% of data points exhibit high-leverage anomaly patterns{methods_note}."
    )
    return {
        "isolation_forest": iso,
        "zscore": zscore,
        "dbscan": dbscan,
        "combined_summary": combined,
        "average_anomaly_pct": avg_pct,
        "methods_count": len(methods_run),
    }
