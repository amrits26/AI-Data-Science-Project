# backend/app/agents/timeseries.py
"""
Time-Series Analysis Agent.
Detects datetime columns, computes trends, seasonality hints,
rolling statistics, autocorrelation, and stationarity signals.
"""

from typing import Any, Optional
import numpy as np
import pandas as pd


def _detect_datetime_col(df: pd.DataFrame) -> Optional[str]:
    """Return the first plausible datetime column name, or None."""
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
        if df[col].dtype == "object":
            try:
                converted = pd.to_datetime(df[col], errors="coerce")
                if converted.notna().mean() >= 0.6:
                    return col
            except Exception:
                pass
    return None


def _rolling_stats(series: pd.Series, window: int = 7) -> dict[str, Any]:
    """Rolling mean and std for trend visualization."""
    if len(series) < window * 2:
        window = max(2, len(series) // 4)
    roll_mean = series.rolling(window=window, min_periods=1).mean()
    roll_std = series.rolling(window=window, min_periods=1).std().fillna(0)
    return {
        "window": window,
        "rolling_mean": [round(float(x), 4) if not np.isnan(x) else None for x in roll_mean],
        "rolling_std": [round(float(x), 4) if not np.isnan(x) else None for x in roll_std],
    }


def _autocorrelation(series: pd.Series, max_lags: int = 20) -> list[float]:
    """Compute autocorrelation up to max_lags."""
    n = len(series)
    lags = min(max_lags, n // 3)
    if lags < 1:
        return []
    s = series.dropna()
    s = s - s.mean()
    var = float((s ** 2).sum())
    if var == 0:
        return [0.0] * lags
    acf = []
    for lag in range(1, lags + 1):
        cov = float((s.iloc[:-lag].values * s.iloc[lag:].values).sum())
        acf.append(round(cov / var, 4))
    return acf


def _stationarity_hint(series: pd.Series) -> dict[str, Any]:
    """
    Simple stationarity signal: compare first-half vs second-half mean/std.
    Full ADF test would require statsmodels — kept lightweight here.
    """
    n = len(series)
    if n < 10:
        return {"likely_stationary": None, "note": "Too few points to assess stationarity."}
    half = n // 2
    s1, s2 = series.iloc[:half].dropna(), series.iloc[half:].dropna()
    mean_shift = abs(float(s1.mean()) - float(s2.mean())) / (float(series.std()) + 1e-9)
    std_ratio = float(s1.std() + 1e-9) / float(s2.std() + 1e-9)
    likely_stationary = mean_shift < 0.3 and 0.5 < std_ratio < 2.0
    return {
        "likely_stationary": bool(likely_stationary),
        "mean_shift_normalized": round(mean_shift, 4),
        "std_ratio_halves": round(std_ratio, 4),
        "note": (
            "Series appears stationary (stable mean/variance)."
            if likely_stationary
            else "Non-stationary signal detected (shifting mean or variance). Consider differencing."
        ),
    }


def _seasonality_hint(series: pd.Series, index: pd.DatetimeIndex) -> dict[str, Any]:
    """
    Rough seasonality hint: check if monthly or weekly patterns exist
    by computing mean per period and measuring coefficient of variation.
    """
    hints = {}
    try:
        monthly_means = series.groupby(index.month).mean()
        cv_monthly = float(monthly_means.std() / (monthly_means.mean() + 1e-9))
        hints["monthly_cv"] = round(cv_monthly, 4)
        hints["monthly_pattern"] = cv_monthly > 0.1
    except Exception:
        pass
    try:
        if hasattr(index, "dayofweek"):
            weekly_means = series.groupby(index.dayofweek).mean()
            cv_weekly = float(weekly_means.std() / (weekly_means.mean() + 1e-9))
            hints["weekly_cv"] = round(cv_weekly, 4)
            hints["weekly_pattern"] = cv_weekly > 0.1
    except Exception:
        pass
    return hints


def run_timeseries_analysis(
    df: pd.DataFrame,
    datetime_col: Optional[str] = None,
    value_col: Optional[str] = None,
) -> dict[str, Any]:
    """
    Run time-series analysis on the dataset.
    Returns trend data, rolling stats, autocorrelation, stationarity,
    seasonality hints, and per-series summaries for numeric columns.
    """
    if df.empty:
        return {"available": False, "reason": "Empty dataset."}

    # Detect datetime column
    dt_col = datetime_col or _detect_datetime_col(df)
    if dt_col is None:
        return {"available": False, "reason": "No datetime column detected."}

    try:
        ts_df = df.copy()
        ts_df[dt_col] = pd.to_datetime(ts_df[dt_col], errors="coerce")
        ts_df = ts_df.dropna(subset=[dt_col]).sort_values(dt_col).set_index(dt_col)
    except Exception as e:
        return {"available": False, "reason": f"Could not parse datetime column '{dt_col}': {e}"}

    if ts_df.empty:
        return {"available": False, "reason": "No valid datetime rows."}

    numeric_cols = ts_df.select_dtypes(include=np.number).columns.tolist()
    if not numeric_cols:
        return {"available": False, "reason": "No numeric columns for time-series analysis."}

    # Use specified value column or first numeric
    primary_col = value_col if (value_col and value_col in numeric_cols) else numeric_cols[0]
    series = ts_df[primary_col].dropna()

    if len(series) < 4:
        return {"available": False, "reason": f"Too few data points in '{primary_col}' for time-series analysis."}

    dt_index = series.index
    window = max(2, len(series) // 10)

    rolling = _rolling_stats(series, window=window)
    acf = _autocorrelation(series)
    stationarity = _stationarity_hint(series)
    seasonality = {}
    if isinstance(dt_index, pd.DatetimeIndex):
        seasonality = _seasonality_hint(series, dt_index)

    # Build timeline data for plotting
    timeline = {
        "timestamps": [str(t) for t in series.index],
        "values": [round(float(v), 4) if not np.isnan(v) else None for v in series.values],
        "rolling_mean": rolling["rolling_mean"],
        "rolling_std": rolling["rolling_std"],
        "rolling_window": rolling["window"],
    }

    # Per-series summary for all numeric cols (top 5)
    series_summaries = []
    for col in numeric_cols[:5]:
        s = ts_df[col].dropna()
        if len(s) < 2:
            continue
        trend_slope = float(np.polyfit(np.arange(len(s)), s.values, 1)[0]) if len(s) >= 2 else 0.0
        series_summaries.append({
            "column": col,
            "n_points": len(s),
            "mean": round(float(s.mean()), 4),
            "std": round(float(s.std()), 4),
            "min": round(float(s.min()), 4),
            "max": round(float(s.max()), 4),
            "trend_slope": round(trend_slope, 6),
            "trend_direction": "up" if trend_slope > 0 else ("down" if trend_slope < 0 else "flat"),
        })

    # Infer frequency
    freq_hint = "unknown"
    try:
        if len(dt_index) >= 3:
            diffs = pd.Series(dt_index).diff().dropna()
            median_diff = diffs.median()
            if median_diff <= pd.Timedelta("1h"):
                freq_hint = "sub-hourly / hourly"
            elif median_diff <= pd.Timedelta("2d"):
                freq_hint = "daily"
            elif median_diff <= pd.Timedelta("10d"):
                freq_hint = "weekly"
            elif median_diff <= pd.Timedelta("40d"):
                freq_hint = "monthly"
            else:
                freq_hint = "quarterly / annual"
    except Exception:
        pass

    summary_parts = [
        f"Time-series analysis on '{primary_col}' ({len(series)} points, {freq_hint} frequency).",
        stationarity["note"],
    ]
    if seasonality.get("monthly_pattern"):
        summary_parts.append("Monthly seasonality pattern detected.")
    if seasonality.get("weekly_pattern"):
        summary_parts.append("Weekly seasonality pattern detected.")
    dominant_trend = series_summaries[0]["trend_direction"] if series_summaries else "unknown"
    summary_parts.append(f"Overall trend: {dominant_trend}.")

    return {
        "available": True,
        "datetime_col": dt_col,
        "primary_value_col": primary_col,
        "n_points": len(series),
        "frequency_hint": freq_hint,
        "timeline": timeline,
        "autocorrelation": acf,
        "stationarity": stationarity,
        "seasonality": seasonality,
        "series_summaries": series_summaries,
        "all_numeric_cols": numeric_cols,
        "summary": " ".join(summary_parts),
    }
