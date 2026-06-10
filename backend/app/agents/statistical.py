"""
Statistical Insight Engine: correlation, mutual information, PCA,
feature clustering, outlier detection, distribution fitting.
"""
import numpy as np
import pandas as pd
from typing import Any


def _numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.select_dtypes(include=[np.number]).dropna(axis="columns", how="all")


def _correlation_matrix(df: pd.DataFrame) -> dict[str, Any]:
    num = _numeric_df(df)
    if num.empty or len(num.columns) < 2:
        return {"matrix": {}, "high_corr_pairs": [], "summary": "Insufficient numeric columns."}
    corr = num.corr()
    high_pairs = []
    for i, a in enumerate(corr.columns):
        for b in corr.columns[i + 1 :]:
            v = corr.loc[a, b]
            if abs(v) > 0.7:
                high_pairs.append({"feature_1": a, "feature_2": b, "correlation": round(float(v), 4)})
    return {
        "matrix": corr.round(4).to_dict(),
        "high_corr_pairs": high_pairs[:20],
        "summary": f"Correlation computed for {len(num.columns)} numeric features. {len(high_pairs)} pair(s) with |r| > 0.7.",
    }


def _mutual_info(df: pd.DataFrame, target_col: str | None) -> dict[str, Any]:
    from sklearn.feature_selection import mutual_info_regression, mutual_info_classif
    num = _numeric_df(df)
    if target_col and target_col in num.columns:
        num = num.drop(columns=[target_col], errors="ignore")
    if num.empty:
        return {"scores": {}, "summary": "No numeric features for mutual information."}
    y = df[target_col] if target_col and target_col in df.columns else None
    if y is not None:
        X = num.fillna(num.median())
        # Classification if few unique classes, including categorical targets.
        if y.nunique() <= 20:
            if pd.api.types.is_numeric_dtype(y):
                y_filled = y.fillna(y.median())
            else:
                mode = y.mode(dropna=True)
                mode_value = mode.iloc[0] if not mode.empty else "unknown"
                y_filled = y.fillna(mode_value)
            try:
                y_cls = pd.factorize(y_filled.astype(str))[0]
                mi = mutual_info_classif(X, y_cls, random_state=42)
            except Exception:
                # Fall back to regression MI on encoded classes when classifier MI fails.
                mi = mutual_info_regression(X, pd.factorize(y_filled.astype(str))[0], random_state=42)
        else:
            if pd.api.types.is_numeric_dtype(y):
                y_reg = y.fillna(y.median())
            else:
                mode = y.mode(dropna=True)
                mode_value = mode.iloc[0] if not mode.empty else "unknown"
                y_reg = pd.factorize(y.fillna(mode_value).astype(str))[0]
            mi = mutual_info_regression(X, y_reg, random_state=42)
        scores = dict(zip(num.columns, [round(float(x), 4) for x in mi]))
        top = sorted(scores.items(), key=lambda t: -t[1])[:10]
        return {
            "scores": scores,
            "top_features": [{"feature": k, "score": v} for k, v in top],
            "summary": f"Mutual information vs target. Top: {top[0][0] if top else 'N/A'}.",
        }
    return {"scores": {}, "summary": "No target column; mutual information not computed."}


def _pca_variance(df: pd.DataFrame, n_components: int = 10) -> dict[str, Any]:
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    num = _numeric_df(df)
    if num.empty or len(num.columns) < 2:
        return {"explained_variance_ratio": [], "n_components": 0, "summary": "Insufficient numeric columns."}
    n_comp = min(n_components, len(num.columns), len(num) - 1)
    if n_comp < 1:
        return {"explained_variance_ratio": [], "n_components": 0, "summary": "Not enough samples or features."}
    X = StandardScaler().fit_transform(num.fillna(num.median()))
    pca = PCA(n_components=n_comp, random_state=42).fit(X)
    ratios = [round(float(x), 4) for x in pca.explained_variance_ratio_]
    cum = np.cumsum(ratios)
    n_95 = int(np.searchsorted(cum, 0.95)) + 1 if cum.size else 0
    return {
        "explained_variance_ratio": ratios,
        "cumulative": [round(float(x), 4) for x in cum],
        "n_components": n_comp,
        "components_to_95pct": n_95,
        "summary": f"PCA: {n_comp} components. First component explains {ratios[0]*100:.1f}% of variance; {n_95} components for 95%.",
    }


def _outlier_detection_iqr(df: pd.DataFrame) -> dict[str, Any]:
    num = _numeric_df(df)
    if num.empty:
        return {"per_column": {}, "total_outlier_pct": 0.0, "summary": "No numeric columns."}
    per_col = {}
    for col in num.columns:
        q1, q3 = num[col].quantile(0.25), num[col].quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        out = ((num[col] < low) | (num[col] > high)).sum()
        per_col[col] = {"count": int(out), "pct": round(100.0 * out / len(num), 2)}
    total_cells = len(num) * len(num.columns)
    outlier_cells = sum(p["count"] for p in per_col.values())
    total_pct = round(100.0 * outlier_cells / total_cells, 2) if total_cells else 0
    return {
        "per_column": per_col,
        "total_outlier_pct": total_pct,
        "summary": f"IQR-based outliers: {total_pct}% of numeric cells flagged.",
    }


def _distribution_recommendations(profile: dict[str, Any] | None) -> list[dict[str, str]]:
    """Suggest transforms based on skewness from profiler output."""
    recs = []
    if not profile or "column_profiles" not in profile:
        return recs
    for cp in profile.get("column_profiles", []):
        if not cp.get("numeric") or cp.get("skewness") is None:
            continue
        s = cp["skewness"]
        name = cp["name"]
        if s > 1.5:
            recs.append({
                "feature": name,
                "issue": "Highly right-skewed",
                "recommendation": "Log transform or Box-Cox recommended.",
                "skewness": round(s, 2),
            })
        elif s < -1.5:
            recs.append({
                "feature": name,
                "issue": "Highly left-skewed",
                "recommendation": "Consider reflection + log or other transform.",
                "skewness": round(s, 2),
            })
    return recs


def run_statistical_insights(
    df: pd.DataFrame,
    target_column: str | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run correlation, mutual information, PCA, IQR outliers, and distribution
    recommendations. Optionally use existing profile for skew-based suggestions.
    """
    correlation = _correlation_matrix(df)
    mutual_info = _mutual_info(df, target_column)
    pca = _pca_variance(df)
    outliers = _outlier_detection_iqr(df)
    distribution_recs = _distribution_recommendations(profile)

    return {
        "correlation": correlation,
        "mutual_information": mutual_info,
        "pca": pca,
        "outliers_iqr": outliers,
        "distribution_recommendations": distribution_recs,
        "summary": (
            f"Statistics: {correlation.get('summary', '')} "
            f"PCA: {pca.get('summary', '')} "
            f"Outliers: {outliers.get('summary', '')} "
            + (" ".join(f"'{r['feature']}' {r['recommendation']}" for r in distribution_recs[:3]))
        ).strip(),
    }
