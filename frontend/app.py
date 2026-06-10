"""
AI Data Scientist — Professional, Google-inspired Streamlit dashboard.
Layout: Upload CSV → Overview → Executive Summary → Modeling → Visualization.
Night mode default; high-contrast; sidebar nav; interactive filters and Plotly charts.
"""
import sys
import logging
import traceback
import os
from pathlib import Path
import json
import base64
from datetime import date, datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import requests
from sqlalchemy import func

from backend.app.agents import (
    profile_dataset,
    run_statistical_insights,
    recommend_and_run_models,
    run_anomaly_detection,
    compute_cognitive_flags,
    generate_insights,
)
from frontend.pages.sales_copilot import render_sales_copilot


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Page config
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Data Scientist",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Session state
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True
if "result" not in st.session_state:
    st.session_state.result = None
if "last_upload" not in st.session_state:
    st.session_state.last_upload = None
if "selected_columns" not in st.session_state:
    st.session_state.selected_columns = None
if "max_preview_rows" not in st.session_state:
    st.session_state.max_preview_rows = 500
if "current_section" not in st.session_state:
    st.session_state.current_section = "Overview"

# -----------------------------------------------------------------------------
# Google-inspired night-mode CSS (high contrast, clean sections)
# -----------------------------------------------------------------------------
def inject_theme(dark: bool):
    bg = "#0e1117" if dark else "#f8f9fa"
    card_bg = "#1a1d24" if dark else "#ffffff"
    card_border = "#2d3238" if dark else "#e5e7eb"
    text = "#fafafa" if dark else "#1a1a1a"
    text_secondary = "#9ca3af" if dark else "#5f6368"
    accent = "#4285f4"
    accent_light = "#8ab4f8"
    font = "'Google Sans', 'Segoe UI', Roboto, sans-serif"
    st.markdown(
        f"""
    <style>
    .stApp {{ background: {bg}; }}
    .main .block-container {{ padding: 1.5rem 2rem; max-width: 1600px; }}
    * {{ font-family: {font}; box-sizing: border-box; }}
    
    /* Section headers */
    .section-header {{
        font-size: 1.35rem; font-weight: 500; color: {text};
        letter-spacing: -0.01em; margin: 1.25rem 0 0.75rem 0;
        padding-bottom: 0.5rem; border-bottom: 1px solid {card_border};
    }}
    .section-sub {{ font-size: 0.9rem; color: {text_secondary}; margin-bottom: 1rem; }}
    
    /* Metric cards */
    .metric-card {{
        background: {card_bg}; border-radius: 10px; padding: 1rem 1.25rem;
        border: 1px solid {card_border}; margin: 0 0.5rem 0.5rem 0;
    }}
    .metric-label {{ font-size: 0.8rem; color: {text_secondary}; text-transform: uppercase; letter-spacing: 0.03em; }}
    .metric-value {{ font-size: 1.5rem; font-weight: 600; color: {accent}; }}
    
    /* Insight / summary boxes */
    .insight-box {{
        background: {card_bg}; border-radius: 10px; padding: 1.25rem 1.5rem;
        border-left: 4px solid {accent}; margin: 0.75rem 0;
        border: 1px solid {card_border}; border-left: 4px solid {accent};
    }}
    .insight-box.warning {{ border-left-color: #f59e0b; }}
    .insight-box.success {{ border-left-color: #10b981; }}
    
    /* Tooltips */
    [data-tooltip] {{ border-bottom: 1px dotted {text_secondary}; cursor: help; }}
    
    #MainMenu, footer {{ visibility: hidden; }}
    [data-testid="stFileUploader"] {{
        background: {card_bg}; border-radius: 10px; padding: 1rem;
        border: 2px dashed {card_border};
    }}
    div[data-testid="stExpander"] {{
        background: {card_bg}; border-radius: 8px; border: 1px solid {card_border};
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )


def _auto_detect_target(df: pd.DataFrame) -> str | None:
    if df is None or df.empty or len(df.columns) == 0:
        return None
    candidates = ["target", "label", "class", "outcome", "y", "result", "dependent"]
    cols_lower = [c.lower().strip() for c in df.columns]
    for c in candidates:
        for i, col in enumerate(df.columns):
            if cols_lower[i] == c or c in cols_lower[i]:
                return col
    last = df.columns[-1]
    if pd.api.types.is_numeric_dtype(df[last]) or df[last].nunique() <= 50:
        return last
    return None


def load_data(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    name = (uploaded_file.name or "").lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(uploaded_file, nrows=100_000)
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(uploaded_file, engine="openpyxl", nrows=100_000)
    except Exception as e:
        st.error(f"Could not read file: {e}")
        return None
    st.warning("Unsupported format. Use CSV or Excel (.xlsx, .xls).")
    return None


def run_pipeline(df: pd.DataFrame, target_column: str | None) -> dict | None:
    progress = st.progress(0, text="Starting pipeline…")
    try:
        progress.progress(0.15, text="Profiling dataset…")
        profile = profile_dataset(df, target_column=target_column)
        progress.progress(0.35, text="Statistical insights…")
        statistical = run_statistical_insights(df, target_column=target_column, profile=profile)
        progress.progress(0.55, text="Modeling…")
        modeling = recommend_and_run_models(df, target_column=target_column)
        progress.progress(0.70, text="Anomaly detection…")
        anomaly = run_anomaly_detection(df)
        progress.progress(0.85, text="Cognitive flags & executive summary…")
        flags = compute_cognitive_flags(profile=profile, statistical=statistical, modeling=modeling)
        executive = generate_insights(profile, statistical, modeling, anomaly, flags, use_llm=True)
        progress.progress(1.0, text="Done")
        return {
            "profile": profile,
            "statistical": statistical,
            "modeling": modeling,
            "anomaly": anomaly,
            "cognitive_flags": flags,
            "executive_summary": executive,
        }
    except Exception as e:
        progress.progress(1.0, text="Error")
        st.error(f"Pipeline failed: {str(e)}")
        return None


def _get_filtered_df(df: pd.DataFrame, profile: dict | None) -> pd.DataFrame:
    """Apply column and row limits from session state for overview/visualization."""
    cols = st.session_state.get("selected_columns") or list(df.columns)
    if not cols:
        cols = list(df.columns)
    max_rows = st.session_state.get("max_preview_rows") or 500
    return df[cols].head(max_rows)


# =============================================================================
# Section 1: Data Overview (metrics, filters, table, charts)
# =============================================================================
def render_overview(df: pd.DataFrame, profile: dict | None):
    st.markdown('<p class="section-header">📋 Data overview</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Key metrics, column/row filters, and summary charts. Selections update tables and charts below.</p>', unsafe_allow_html=True)

    # Metrics row
    r, c = df.shape
    missing_pct = (df.isna().sum().sum() / (r * c * 1.0) * 100) if (r and c) else 0
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = [x for x in df.columns if x not in numeric_cols]
    n_numeric, n_categorical = len(numeric_cols), len(cat_cols)

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Rows", f"{r:,}", help="Total number of rows in the dataset")
    with m2:
        st.metric("Columns", c, help="Total number of columns")
    with m3:
        st.metric("Missing %", f"{missing_pct:.1f}%", help="Share of cells that are missing")
    with m4:
        st.metric("Numeric", n_numeric, help="Columns with numeric type")
    with m5:
        st.metric("Categorical", n_categorical, help="Non-numeric columns")
    if profile:
        st.metric("Data health score", f"{profile.get('data_health_score', 0)}/100", help="Overall data quality score (0–100)")

    # Filters (update when changed)
    st.markdown("**Filters**")
    valid_default = [c for c in (st.session_state.selected_columns or list(df.columns)) if c in df.columns]
    if not valid_default:
        valid_default = list(df.columns)
    col_filter = st.multiselect(
        "Select columns to display",
        options=list(df.columns),
        default=valid_default,
        help="Charts and table below use only selected columns.",
    )
    st.session_state.selected_columns = col_filter if col_filter else list(df.columns)
    max_rows = st.slider("Max rows in table and charts", 50, 2000, st.session_state.get("max_preview_rows", 500), 50, help="Limit rows for performance")
    st.session_state.max_preview_rows = max_rows

    filtered = _get_filtered_df(df, profile)
    display_cols = [x for x in st.session_state.selected_columns if x in filtered.columns]
    if not display_cols:
        display_cols = list(filtered.columns)

    # Interactive table
    st.markdown("**Preview data**")
    st.dataframe(filtered[display_cols] if display_cols else filtered, use_container_width=True, hide_index=True)

    # Summary charts (bar, pie, histograms)
    st.markdown("**Summary charts**")

    # Bar: missing % per column (for displayed columns)
    miss_per_col = filtered[display_cols].isna().mean() * 100
    if len(display_cols) > 0 and len(display_cols) <= 30:
        fig_miss = px.bar(
            x=miss_per_col.index.astype(str),
            y=miss_per_col.values,
            labels={"x": "Column", "y": "Missing %"},
            title="Missing values by column",
        )
        fig_miss.update_layout(xaxis_tickangle=-45, margin=dict(b=100))
        st.plotly_chart(fig_miss, use_container_width=True)

    # Pie: numeric vs categorical
    fig_pie = go.Figure(data=[go.Pie(
        labels=["Numeric", "Categorical"],
        values=[n_numeric, n_categorical],
        hole=0.5,
        marker_colors=["#4285f4", "#34a853"],
    )])
    fig_pie.update_layout(title="Column types", height=300)
    st.plotly_chart(fig_pie, use_container_width=True)

    # Histograms: one per numeric column (top 6) in filtered set
    num_in_display = [x for x in display_cols if x in numeric_cols]
    for i, col in enumerate(num_in_display[:6]):
        try:
            fig_hist = px.histogram(
                filtered[col].dropna(),
                nbins=min(50, max(10, int(filtered[col].nunique() / 2))),
                title=f"Distribution: {col}",
                labels={"value": col, "count": "Count"},
            )
            st.plotly_chart(fig_hist, use_container_width=True)
        except Exception:
            pass


# =============================================================================
# Section 2: Executive Summary (polished insight boxes)
# =============================================================================
def render_executive_summary(data: dict):
    st.markdown('<p class="section-header">📄 Executive summary</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Human-readable insights, trends, and recommendations for decision-making.</p>', unsafe_allow_html=True)

    ex = data.get("executive_summary") or {}
    profile = data.get("profile") or {}
    statistical = data.get("statistical") or {}
    modeling = data.get("modeling") or {}
    anomaly = data.get("anomaly") or {}

    # Main summary box
    summary_text = ex.get("summary", "Run the analysis to see the executive summary.")
    st.markdown(f'<div class="insight-box">{summary_text}</div>', unsafe_allow_html=True)

    # Trends & patterns (from profile + stats)
    bullets = []
    bullets.append(f"**Dataset:** {profile.get('rows', 0):,} rows, {profile.get('columns', 0)} columns. Data health score: {profile.get('data_health_score', 0)}/100.")
    if statistical.get("summary"):
        bullets.append(f"**Statistics:** {statistical['summary']}")
    if anomaly.get("combined_summary"):
        bullets.append(f"**Anomalies:** {anomaly['combined_summary']}")
    if modeling and not modeling.get("message"):
        bullets.append(f"**Modeling:** {modeling.get('summary', '')}")
    for b in bullets:
        st.markdown(f'<div class="insight-box success"><p style="margin:0;">{b}</p></div>', unsafe_allow_html=True)

    # Business implications
    if ex.get("business_implications"):
        st.markdown("**Business implications**")
        for imp in ex["business_implications"]:
            st.markdown(f"- {imp}")

    # Risks
    if ex.get("risks"):
        st.markdown("**Risks**")
        for r in ex["risks"]:
            st.warning(r)

    # Next steps
    if ex.get("next_steps"):
        st.markdown("**Recommended next steps**")
        for n in ex["next_steps"]:
            st.markdown(f"- {n}")

    # Cognitive flags as expandable cards
    flags = data.get("cognitive_flags") or []
    if flags:
        st.markdown("**Insight cards**")
        for f in flags:
            sev = f.get("severity", "info")
            with st.expander(f"{f.get('title', '')} — {sev}", expanded=False):
                st.write(f.get("description", ""))
                if f.get("recommendation"):
                    st.info(f"💡 {f['recommendation']}")
                if f.get("math_detail"):
                    st.caption(f"Detail: {f['math_detail']}")


# =============================================================================
# Section 3: Modeling (performance, overfitting, feature importance, skip messages)
# =============================================================================
def render_modeling(modeling: dict):
    st.markdown('<p class="section-header">🤖 Modeling</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Model performance, cross-validation, overfitting risk, and rich diagnostics. Expand sections below for more detail.</p>', unsafe_allow_html=True)

    if not modeling:
        st.info("Run the full analysis with a target column to see modeling results.")
        return

    if modeling.get("message"):
        st.markdown(
            '<div class="insight-box warning">'
            '<strong>Modeling not run</strong><br/>' + modeling["message"] +
            '</div>',
            unsafe_allow_html=True,
        )
        st.caption("Common reasons: no target column selected, too few rows (min 10), no numeric features, or target has only one class.")
        return

    # ------------------------------------------------------------------
    # Performance & overfitting
    # ------------------------------------------------------------------
    with st.expander("Performance & overfitting", expanded=True):
        st.markdown(modeling.get("summary", ""))
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Problem type", modeling.get("problem_type", ""), help="Classification or regression task")
        with c2:
            st.metric("CV mean", f"{modeling.get('cross_val_mean', 0):.4f}", help="Cross-validation mean (accuracy or R²)")
        with c3:
            st.metric("CV std", f"{modeling.get('cross_val_std', 0):.4f}", help="Stability of performance across folds")
        with c4:
            st.metric("Model", modeling.get("model_used", ""), help="Primary model used")

        overfit = modeling.get("overfitting_analysis") or {}
        train_s = overfit.get("train_score")
        val_s = overfit.get("validation_score")
        if train_s is not None and val_s is not None:
            fig_scores = px.bar(
                x=["Train", "Validation"],
                y=[train_s, val_s],
                range_y=[0, 1],
                labels={"x": "", "y": "Score"},
                title="Overfitting indicator: train vs validation",
            )
            st.plotly_chart(fig_scores, use_container_width=True)
        risk = overfit.get("overfitting_risk", "")
        if risk in ("high", "moderate"):
            st.warning(
                f"**Overfitting risk: {risk}.** Train: {train_s}, Validation: {val_s}. "
                "Consider regularization, simpler models, or more data."
            )
        else:
            st.success(f"Overfitting risk: **{risk}**.")

        cv_scores = modeling.get("cv_scores")
        if cv_scores:
            fig_cv = px.bar(
                x=list(range(1, len(cv_scores) + 1)),
                y=cv_scores,
                labels={"x": "Fold", "y": "Score"},
                title="Cross-validation scores by fold",
            )
            st.plotly_chart(fig_cv, use_container_width=True)

    # ------------------------------------------------------------------
    # Feature importance & SHAP-style explanation
    # ------------------------------------------------------------------
    with st.expander("Feature importance & SHAP-style explanation", expanded=False):
        imp = modeling.get("feature_importance") or {}
        if imp:
            imp_sorted = dict(sorted(imp.items(), key=lambda x: -x[1])[:15])
            fig = px.bar(
                x=list(imp_sorted.keys()),
                y=list(imp_sorted.values()),
                labels={"x": "Feature", "y": "Importance"},
                title="Feature importance (RandomForest)",
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

        shap_imp = modeling.get("shap_importance") or {}
        if shap_imp:
            shap_sorted = dict(sorted(shap_imp.items(), key=lambda x: -x[1])[:15])
            fig_shap = px.bar(
                x=list(shap_sorted.keys()),
                y=list(shap_sorted.values()),
                labels={"x": "Feature", "y": "Mean |SHAP|"},
                title="SHAP summary (global feature impact)",
            )
            fig_shap.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_shap, use_container_width=True)
            st.caption("Higher mean |SHAP| indicates stronger contribution of a feature to the model's predictions.")

    # ------------------------------------------------------------------
    # Predictions, residuals, and target vs predictions
    # ------------------------------------------------------------------
    with st.expander("Predictions, residuals, and target vs predictions", expanded=False):
        pv = modeling.get("pred_vs_actual") or {}
        y_true, y_pred = pv.get("y_true"), pv.get("y_pred")
        if y_true and y_pred and len(y_true) == len(y_pred):
            df_pv = pd.DataFrame({"actual": y_true, "predicted": y_pred})
            if modeling.get("problem_type") == "regression":
                st.markdown("**Predicted vs actual (regression)**")
                fig = px.scatter(
                    df_pv,
                    x="actual",
                    y="predicted",
                    opacity=0.7,
                    title="Predicted vs actual",
                )
                try:
                    lo, hi = float(df_pv["actual"].min()), float(df_pv["actual"].max())
                    line = np.linspace(lo, hi, 100)
                    fig.add_trace(
                        go.Scatter(
                            x=line,
                            y=line,
                            name="Ideal",
                            line=dict(color="red", dash="dash"),
                        )
                    )
                except Exception:
                    pass
                st.plotly_chart(fig, use_container_width=True)

                # Residual histogram
                resid = modeling.get("residuals_sample") or []
                if resid:
                    fig_resid = px.histogram(
                        resid,
                        nbins=40,
                        labels={"value": "Residual"},
                        title="Residuals (prediction error)",
                    )
                    st.plotly_chart(fig_resid, use_container_width=True)

                # Target vs prediction distribution
                fig_dist = go.Figure()
                fig_dist.add_trace(
                    go.Histogram(x=df_pv["actual"], name="Actual", opacity=0.6)
                )
                fig_dist.add_trace(
                    go.Histogram(x=df_pv["predicted"], name="Predicted", opacity=0.6)
                )
                fig_dist.update_layout(
                    barmode="overlay",
                    title="Target vs prediction distribution",
                    xaxis_title="Value",
                )
                fig_dist.update_traces(marker_line_width=0)
                st.plotly_chart(fig_dist, use_container_width=True)
            else:
                # Classification: confusion matrix + class distribution
                try:
                    st.markdown("**Confusion matrix (actual vs predicted)**")
                    ct = pd.crosstab(df_pv["actual"], df_pv["predicted"])
                    fig = px.imshow(
                        ct,
                        text_auto=True,
                        aspect="auto",
                        color_continuous_scale="Blues",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                except Exception:
                    st.dataframe(
                        df_pv.head(50), use_container_width=True, hide_index=True
                    )

                # Class distribution: actual vs predicted
                try:
                    actual_counts = pd.Series(y_true).value_counts().sort_index()
                    pred_counts = pd.Series(y_pred).value_counts().sort_index()
                    df_cls = pd.DataFrame(
                        {"Actual": actual_counts, "Predicted": pred_counts}
                    ).fillna(0)
                    fig_cls = px.bar(
                        df_cls,
                        barmode="group",
                        title="Target vs prediction distribution",
                    )
                except Exception:
                    df_cls = pd.DataFrame(
                        {
                            "Actual": pd.Series(y_true).value_counts(),
                            "Predicted": pd.Series(y_pred).value_counts(),
                        }
                    )
                    fig_cls = px.bar(
                        df_cls,
                        barmode="group",
                        title="Target vs prediction distribution",
                    )
                st.plotly_chart(fig_cls, use_container_width=True)

    # ------------------------------------------------------------------
    # ROC and precision–recall (classification only)
    # ------------------------------------------------------------------
    if modeling.get("problem_type") == "classification":
        roc = modeling.get("roc_curve") or {}
        pr = modeling.get("pr_curve") or {}
        if roc or pr:
            with st.expander("ROC and precision–recall curves", expanded=False):
                if roc.get("fpr") and roc.get("tpr"):
                    fig_roc = px.line(
                        x=roc["fpr"],
                        y=roc["tpr"],
                        labels={"x": "False positive rate", "y": "True positive rate"},
                        title="ROC curve",
                    )
                    fig_roc.add_shape(
                        type="line",
                        x0=0,
                        y0=0,
                        x1=1,
                        y1=1,
                        line=dict(color="gray", dash="dash"),
                    )
                    st.plotly_chart(fig_roc, use_container_width=True)
                if pr.get("precision") and pr.get("recall"):
                    fig_pr = px.line(
                        x=pr["recall"],
                        y=pr["precision"],
                        labels={"x": "Recall", "y": "Precision"},
                        title="Precision–recall curve",
                    )
                    st.plotly_chart(fig_pr, use_container_width=True)
                st.caption(
                    "ROC and PR curves help evaluate classification performance under different thresholds, especially with imbalanced data."
                )


# =============================================================================
# Section 4: Visualization (correlation, PCA, anomaly)
# =============================================================================
def render_visualization(data: dict, df: pd.DataFrame):
    st.markdown('<p class="section-header">📈 Visualization</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Correlation matrix, PCA variance, and anomaly overview.</p>', unsafe_allow_html=True)

    statistical = data.get("statistical") or {}
    anomaly = data.get("anomaly") or {}

    # Correlation heatmap
    corr = statistical.get("correlation") or {}
    if corr.get("matrix"):
        num_df = pd.DataFrame(corr["matrix"])
        fig = px.imshow(num_df, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r", title="Correlation matrix")
        fig.update_layout(margin=dict(l=80, r=40))
        st.plotly_chart(fig, use_container_width=True)

    # PCA
    pca = statistical.get("pca") or {}
    if pca.get("explained_variance_ratio"):
        r = pca["explained_variance_ratio"]
        c = pca.get("cumulative", [])
        fig = go.Figure()
        fig.add_trace(go.Bar(x=list(range(1, len(r) + 1)), y=r, name="Variance"))
        if c:
            fig.add_trace(go.Scatter(x=list(range(1, len(c) + 1)), y=c, name="Cumulative", line=dict(color="orange")))
        fig.update_layout(title="PCA variance explained", xaxis_title="Component")
        st.plotly_chart(fig, use_container_width=True)

    # Anomaly summary bar
    if anomaly:
        methods = []
        pcts = []
        for k in ["isolation_forest", "zscore", "dbscan"]:
            if k in anomaly and isinstance(anomaly[k], dict):
                methods.append(anomaly[k].get("method", k))
                pcts.append(anomaly[k].get("anomaly_pct", 0))
        if methods and pcts:
            fig_anom = px.bar(x=methods, y=pcts, labels={"x": "Method", "y": "Anomaly %"}, title="Anomaly detection by method")
            st.plotly_chart(fig_anom, use_container_width=True)
        st.markdown(anomaly.get("combined_summary", ""))

    # Distribution recommendations
    for rec in (statistical.get("distribution_recommendations") or [])[:5]:
        st.warning(f"**{rec.get('feature')}**: {rec.get('recommendation')}")


def render_dealership_tools(api_url: str):
    st.markdown('<p class="section-header">🚗 Dealership Tools</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Document ingestion, lead scores, trade-in appraisal, and daily briefing via FastAPI endpoints.</p>', unsafe_allow_html=True)

    with st.expander("Ingest document image", expanded=True):
        image_file = st.file_uploader(
            "Upload document image",
            type=["png", "jpg", "jpeg", "webp"],
            key="doc_image_uploader",
        )
        doc_type = st.selectbox(
            "Document type",
            ["lead", "insurance", "cleanup", "sold", "commission", "credit"],
            index=0,
            key="doc_type_select",
        )
        if st.button("Ingest document", key="doc_ingest_btn", type="primary"):
            if not image_file:
                st.warning("Upload an image first.")
            else:
                try:
                    files = {"file": (image_file.name, image_file.read(), image_file.type or "image/jpeg")}
                    data = {"doc_type": doc_type}
                    resp = requests.post(f"{api_url}/api/ingest-document", files=files, data=data, timeout=120)
                    if resp.ok:
                        payload = resp.json()
                        st.success(f"Saved to {payload.get('saved_to')}")
                        st.json(payload.get("data", {}))
                    else:
                        st.error(f"Ingestion failed: {resp.text}")
                except Exception as e:
                    st.error(f"Ingestion request failed: {e}")

    with st.expander("Lead scores", expanded=False):
        if st.button("Show lead scores", key="lead_scores_btn"):
            try:
                resp = requests.get(f"{api_url}/api/dealership/lead-scores", timeout=60)
                payload = resp.json() if resp.ok else {"message": resp.text}
                st.info(payload.get("message", "Lead scoring response loaded."))
                st.write(f"Total leads: {payload.get('total_leads', 0)}")
                st.write(f"Average probability: {payload.get('average_probability', 0)}")
                st.dataframe(pd.DataFrame(payload.get("top_leads", [])), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Lead scores request failed: {e}")

    with st.expander("Trade-in appraisal", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            make = st.text_input("Make", value="Toyota", key="trade_make")
            year = st.number_input("Year", min_value=1990, max_value=2100, value=2020, step=1, key="trade_year")
            condition = st.selectbox("Condition", ["excellent", "good", "fair", "poor"], index=1, key="trade_condition")
        with c2:
            model = st.text_input("Model", value="Camry", key="trade_model")
            mileage = st.number_input("Mileage", min_value=0, max_value=500000, value=35000, step=1000, key="trade_mileage")

        if st.button("Appraise trade-in", key="trade_appraise_btn"):
            try:
                payload = {
                    "make": make,
                    "model": model,
                    "year": int(year),
                    "mileage": int(mileage),
                    "condition": condition,
                }
                resp = requests.post(f"{api_url}/api/dealership/appraise", json=payload, timeout=60)
                if resp.ok:
                    st.json(resp.json())
                else:
                    st.error(f"Appraisal failed: {resp.text}")
            except Exception as e:
                st.error(f"Appraisal request failed: {e}")

    with st.expander("Daily briefing", expanded=False):
        if st.button("Generate daily briefing", key="briefing_btn"):
            try:
                resp = requests.get(f"{api_url}/api/dealership/briefing", timeout=60)
                if resp.ok:
                    briefing = resp.json()
                    st.success(briefing.get("summary", "Briefing generated."))
                    st.dataframe(pd.DataFrame(briefing.get("top_leads", [])), use_container_width=True, hide_index=True)
                else:
                    st.error(f"Briefing failed: {resp.text}")
            except Exception as e:
                st.error(f"Briefing request failed: {e}")


def render_health_panel(api_url: str) -> None:
    """Render lightweight runtime health diagnostics from backend."""
    st.markdown("**System Health**")
    try:
        resp = requests.get(f"{api_url}/api/health", timeout=10)
        if not resp.ok:
            st.warning(f"Health endpoint unavailable ({resp.status_code}).")
            return

        payload = resp.json()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("API", payload.get("status", "unknown"))
        c2.metric("Database", payload.get("database", "unknown"))
        c3.metric("Ollama", payload.get("ollama", "unknown"))
        c4.metric("NHTSA", payload.get("nhtsa_api", "unknown"))
        st.caption(f"Cars in DB: {payload.get('cars_in_db', 0)} | Tesseract: {payload.get('tesseract', 'unknown')}")
    except Exception as exc:
        st.info("Health check could not be loaded from backend.")
        logger.warning("streamlit_health_panel_failed", extra={"error": str(exc)})


def _decode_chart_payload(chart_payload: str):
    """Decode chart payload returned by visualizations module."""
    try:
        return base64.b64decode(chart_payload)
    except Exception:
        return None


def render_imperial_dashboard() -> None:
    """Render the Phase 7 Imperial Cars Streamlit dashboard with five tabs."""
    st.markdown('<p class="section-header">🚗 Imperial Cars Dashboard</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-sub">Search inventory, model financing, manage service workflows, and review lifecycle performance.</p>',
        unsafe_allow_html=True,
    )

    st.session_state.setdefault("customer_id", 1)
    st.session_state.setdefault("is_admin", False)

    header_col1, header_col2 = st.columns([3, 2])
    with header_col1:
        st.session_state["customer_id"] = st.number_input(
            "Customer ID",
            min_value=1,
            value=int(st.session_state.get("customer_id", 1)),
            step=1,
            help="Used for service jobs and nurture history lookups.",
        )
    with header_col2:
        st.session_state["is_admin"] = st.toggle(
            "Admin Mode",
            value=bool(st.session_state.get("is_admin", False)),
            help="Enables workflow triggers and admin sales dashboard.",
        )

    tab_specs, tab_finance, tab_jobs, tab_lifecycle, tab_deal_detail, tab_sales = st.tabs(
        [
            "🔍 Vehicle Specs & Search",
            "💰 Pricing & Financing",
            "🚗 My Service Jobs",
            "📊 Customer Lifecycle",
            "🧾 Deal Detail",
            "📈 Sales Dashboard",
        ]
    )

    with tab_specs:
        st.subheader("Vehicle Specifications")
        c1, c2, c3 = st.columns(3)
        with c1:
            make = st.text_input("Make", value="Toyota", key="phase7_specs_make")
        with c2:
            model = st.text_input("Model", value="Camry", key="phase7_specs_model")
        with c3:
            year_input = st.number_input("Year (optional)", min_value=0, max_value=2100, value=0, step=1, key="phase7_specs_year")

        if st.button("Search Vehicles", key="phase7_specs_search", type="primary"):
            from backend.app.database import Car, get_db_session
            from backend.app.agents.nhtsa_api import get_safety_rating
            from backend.app.agents.visualizations import depreciation_curve

            db = get_db_session()
            try:
                query = db.query(Car)
                if make.strip():
                    query = query.filter(Car.make.ilike(f"%{make.strip()}%"))
                if model.strip():
                    query = query.filter(Car.model.ilike(f"%{model.strip()}%"))
                if int(year_input) > 0:
                    query = query.filter(Car.year == int(year_input))

                cars = query.order_by(Car.year.desc()).limit(25).all()
                if not cars:
                    st.warning("No matching vehicles found.")
                else:
                    rows = []
                    for car in cars:
                        rows.append(
                            {
                                "Year": car.year,
                                "Make": car.make,
                                "Model": car.model,
                                "Trim": car.trim,
                                "MSRP": f"${(car.msrp or 0):,.0f}" if car.msrp else "N/A",
                                "HP": car.horsepower,
                                "MPG Hwy": car.mpg_highway,
                                "Safety": car.safety_rating,
                            }
                        )
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                    lead_car = cars[0]
                    if lead_car.year and lead_car.make and lead_car.model:
                        safety = get_safety_rating(int(lead_car.year), lead_car.make, lead_car.model)
                        if safety.get("status") == "ok":
                            s1, s2, s3, s4 = st.columns(4)
                            s1.metric("Overall Safety", str(safety.get("overall_rating", "N/A")))
                            s2.metric("Front Crash", str(safety.get("front_crash", "N/A")))
                            s3.metric("Side Crash", str(safety.get("side_crash", "N/A")))
                            s4.metric("Rollover", str(safety.get("rollover", "N/A")))

                        chart_payload = depreciation_curve(lead_car.make, lead_car.model)
                        chart_bytes = _decode_chart_payload(chart_payload) if isinstance(chart_payload, str) else None
                        if chart_bytes:
                            st.image(chart_bytes, caption=f"Depreciation Curve: {lead_car.make} {lead_car.model}", use_container_width=True)
                        else:
                            st.info("Depreciation curve unavailable for this vehicle.")
            except Exception as exc:
                st.error(f"Vehicle search failed: {exc}")
            finally:
                db.close()

    with tab_finance:
        st.subheader("Financing Options")
        col1, col2 = st.columns(2)

        with col1:
            price = st.number_input("Vehicle Price", min_value=5000.0, value=30000.0, step=500.0, key="phase7_fin_price")
            down = st.number_input("Down Payment", min_value=0.0, value=5000.0, step=250.0, key="phase7_fin_down")
            msrp = st.number_input("MSRP (Lease)", min_value=5000.0, value=32000.0, step=500.0, key="phase7_fin_msrp")
            residual_pct = st.slider("Residual %", 35, 75, 58, key="phase7_fin_residual")

        with col2:
            rate = st.slider("Interest Rate %", 0.0, 15.0, 6.9, 0.1, key="phase7_fin_rate")
            term = st.select_slider("Loan Term (months)", [24, 36, 48, 60, 72, 84], value=60, key="phase7_fin_term")
            money_factor = st.number_input("Money Factor", min_value=0.0001, max_value=0.01, value=0.0023, step=0.0001, format="%.4f", key="phase7_fin_mf")
            amount_owed = st.number_input("Trade-in Loan Balance", min_value=0.0, value=12000.0, step=500.0, key="phase7_fin_owed")

        from backend.app.agents.math_tools import loan_calculator, lease_vs_buy, trade_in_equity
        from backend.app.agents.visualizations import monthly_payment_chart

        monthly, total = loan_calculator(price, down, rate, term)
        compare = lease_vs_buy(price=msrp, residual_percent=float(residual_pct), money_factor=money_factor, loan_rate=rate, term_months=term, lease_down=down)
        trade = trade_in_equity(amount_owed=amount_owed, market_value=price * 0.55)

        m1, m2, m3 = st.columns(3)
        m1.metric("Monthly Payment", f"${monthly:,.2f}")
        m2.metric("Total Loan Cost", f"${total:,.2f}")
        m3.metric("Trade Equity", f"${trade['equity']:,.2f}")

        st.info(compare.get("recommendation", "No recommendation available."))
        lease_col, buy_col = st.columns(2)
        lease_col.metric("Lease Monthly", f"${compare['lease']['monthly_payment']:,.2f}")
        buy_col.metric("Buy Monthly", f"${compare['buy']['monthly_payment']:,.2f}")

        chart_payload = monthly_payment_chart(price, down, rate, term)
        chart_bytes = _decode_chart_payload(chart_payload) if isinstance(chart_payload, str) else None
        if chart_bytes:
            st.image(chart_bytes, caption="Monthly Payment by Term", use_container_width=True)
        else:
            st.warning("Payment chart unavailable.")

    with tab_jobs:
        st.subheader("Service Reminders")
        from backend.app.agents.customer_updates import create_job, get_customer_jobs

        customer_id = int(st.session_state.get("customer_id", 1))
        status_filter = st.selectbox("Status Filter", ["all", "pending", "in_progress", "completed", "cancelled"], index=0, key="phase7_jobs_status")

        try:
            jobs = get_customer_jobs(customer_id, None if status_filter == "all" else status_filter)
            if jobs:
                timeline_rows = []
                for job in jobs:
                    with st.expander(f"{job['job_type'].replace('_', ' ').title()} - {job['status'].upper()}"):
                        st.write(f"Priority: {job.get('priority', 'normal')}")
                        st.write(f"Created: {job.get('created_at')}")
                        st.write(f"Due: {job.get('due_date')}")
                        if st.button(f"Schedule Job #{job['id']}", key=f"phase7_sched_{job['id']}"):
                            st.success(f"Job {job['id']} marked for scheduling. A coordinator will contact the customer.")

                    timeline_rows.append(
                        {
                            "Job ID": job["id"],
                            "Type": job["job_type"],
                            "Status": job["status"],
                            "Priority": job.get("priority"),
                            "Due Date": job.get("due_date"),
                        }
                    )

                st.markdown("**Job Timeline**")
                st.dataframe(pd.DataFrame(timeline_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No service jobs found for this customer.")
        except Exception as exc:
            st.error(f"Unable to load service jobs: {exc}")

        st.markdown("**Schedule New Maintenance**")
        j1, j2, j3 = st.columns(3)
        with j1:
            new_job_type = st.selectbox("Job Type", ["oil_change", "tire_rotation", "inspection", "brake_service", "battery_check"], key="phase7_new_job_type")
        with j2:
            new_priority = st.selectbox("Priority", ["low", "medium", "high", "urgent"], index=1, key="phase7_new_job_priority")
        with j3:
            due_dt = st.date_input("Due Date", value=date.today() + timedelta(days=7), key="phase7_new_job_due")

        notes = st.text_area("Notes", value="Routine service request", key="phase7_new_job_notes")
        if st.button("Create Service Job", key="phase7_new_job_btn"):
            job_id = create_job(customer_id=customer_id, vehicle_id=None, job_type=new_job_type, priority=new_priority, description=notes, due_date=due_dt)
            if job_id:
                st.success(f"Created service job #{job_id}.")
            else:
                st.error("Failed to create service job.")

    with tab_lifecycle:
        st.subheader("Your Engagement Timeline")
        from backend.app.agents.lifecycle_agents import get_nurture_history, manual_trigger

        customer_id = int(st.session_state.get("customer_id", 1))
        history = get_nurture_history(customer_id)
        if history:
            for log in history[:50]:
                campaign = str(log.get("campaign_type", "unknown")).replace("_", " ").title()
                sent_at = log.get("sent_at")
                sent_str = sent_at.strftime("%m/%d/%Y %H:%M") if hasattr(sent_at, "strftime") else str(sent_at)
                st.info(f"{campaign} - {sent_str}")
        else:
            st.info("No lifecycle campaigns found for this customer yet.")

        if st.session_state.get("is_admin"):
            st.markdown("**Admin: Manual Workflows**")
            workflow = st.selectbox("Trigger workflow", ["onboarding", "service", "trade_in", "winback", "buyback"], key="phase7_workflow")
            if st.button("Execute Workflow", key="phase7_workflow_btn"):
                result = manual_trigger(workflow)
                if result.get("status") == "ok":
                    st.success(result.get("message", "Workflow executed."))
                else:
                    st.error(result.get("message", "Workflow failed."))

        st.markdown("---")
        st.subheader("Send Follow-Up")
        st.markdown("Send SMS, WhatsApp, voice call, and email to this customer")
        
        followup_col1, followup_col2 = st.columns([3, 1])
        with followup_col1:
            custom_msg = st.text_area(
                "Custom message (optional)",
                value="",
                placeholder="Leave blank to auto-generate a personalized message",
                height=80,
                key="phase7_followup_msg"
            )
        with followup_col2:
            st.write("")  # Spacer
            st.write("")  # Spacer
            if st.button("📧 Send Follow-Up", key="phase7_followup_btn", type="primary"):
                try:
                    customer_id = int(st.session_state.get("customer_id", 1))
                    api_url = os.getenv("API_BASE_URL", "http://localhost:8000")
                    payload = {}
                    if custom_msg.strip():
                        payload["override_message"] = custom_msg.strip()
                    
                    response = requests.post(
                        f"{api_url}/api/followup/{customer_id}",
                        json=payload,
                        timeout=30
                    )
                    result = response.json()
                    
                    if result.get("status") in ["completed", "partial"]:
                        st.success(
                            f"✓ Follow-up sent successfully!\n\n"
                            f"SMS: {result.get('sms_status')}\n"
                            f"WhatsApp: {result.get('whatsapp_status')}\n"
                            f"Voice: {result.get('voice_status')}\n"
                            f"Email: {result.get('email_status')}"
                        )
                    else:
                        st.error(f"✗ Follow-up failed: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    st.error(f"Error sending follow-up: {str(e)}")

    with tab_deal_detail:
        st.subheader("Deal Detail & Communication Preferences")
        st.caption("Manage channel preferences and update deal status, including waiting_insurance trigger.")

        customer_id = int(st.session_state.get("customer_id", 1))
        api_url = os.getenv("API_BASE_URL", "http://localhost:8000")

        if "deal_pref_cache" not in st.session_state:
            st.session_state["deal_pref_cache"] = {
                "sms": {"is_enabled": True, "contact_value": ""},
                "whatsapp": {"is_enabled": False, "contact_value": ""},
                "email": {"is_enabled": True, "contact_value": ""},
                "voice": {"is_enabled": False, "contact_value": ""},
            }

        pref_col1, pref_col2 = st.columns([1, 1])
        with pref_col1:
            if st.button("Load Saved Preferences", key="deal_pref_load_btn"):
                try:
                    resp = requests.get(f"{api_url}/api/customer-preferences/{customer_id}", timeout=20)
                    payload = resp.json() if resp.ok else {}
                    prefs = payload.get("preferences", []) if isinstance(payload, dict) else []
                    cache = {
                        "sms": {"is_enabled": False, "contact_value": ""},
                        "whatsapp": {"is_enabled": False, "contact_value": ""},
                        "email": {"is_enabled": False, "contact_value": ""},
                        "voice": {"is_enabled": False, "contact_value": ""},
                    }
                    for p in prefs:
                        ch = str(p.get("channel", "")).strip().lower()
                        if ch in cache:
                            cache[ch] = {
                                "is_enabled": bool(p.get("is_enabled", False)),
                                "contact_value": str(p.get("contact_value") or ""),
                            }
                    st.session_state["deal_pref_cache"] = cache
                    st.success("Loaded preferences.")
                except Exception as exc:
                    st.error(f"Failed to load preferences: {exc}")

        cache = st.session_state["deal_pref_cache"]
        p1, p2 = st.columns(2)
        with p1:
            sms_enabled = st.checkbox("SMS enabled", value=bool(cache["sms"]["is_enabled"]), key="deal_sms_enabled")
            sms_contact = st.text_input("SMS phone", value=str(cache["sms"]["contact_value"]), key="deal_sms_contact")
            email_enabled = st.checkbox("Email enabled", value=bool(cache["email"]["is_enabled"]), key="deal_email_enabled")
            email_contact = st.text_input("Email address", value=str(cache["email"]["contact_value"]), key="deal_email_contact")
        with p2:
            wa_enabled = st.checkbox("WhatsApp enabled", value=bool(cache["whatsapp"]["is_enabled"]), key="deal_wa_enabled")
            wa_contact = st.text_input("WhatsApp phone", value=str(cache["whatsapp"]["contact_value"]), key="deal_wa_contact")
            voice_enabled = st.checkbox("Voice enabled", value=bool(cache["voice"]["is_enabled"]), key="deal_voice_enabled")
            voice_contact = st.text_input("Voice phone", value=str(cache["voice"]["contact_value"]), key="deal_voice_contact")

        if st.button("Save Preferences", key="deal_pref_save_btn", type="primary"):
            try:
                prefs_payload = {
                    "preferences": [
                        {"channel": "sms", "is_enabled": bool(sms_enabled), "contact_value": sms_contact.strip() or None},
                        {"channel": "whatsapp", "is_enabled": bool(wa_enabled), "contact_value": wa_contact.strip() or None},
                        {"channel": "email", "is_enabled": bool(email_enabled), "contact_value": email_contact.strip() or None},
                        {"channel": "voice", "is_enabled": bool(voice_enabled), "contact_value": voice_contact.strip() or None},
                    ]
                }
                resp = requests.put(f"{api_url}/api/customer-preferences/{customer_id}", json=prefs_payload, timeout=20)
                if resp.ok:
                    st.success("Preferences saved.")
                    st.session_state["deal_pref_cache"] = {
                        "sms": {"is_enabled": bool(sms_enabled), "contact_value": sms_contact},
                        "whatsapp": {"is_enabled": bool(wa_enabled), "contact_value": wa_contact},
                        "email": {"is_enabled": bool(email_enabled), "contact_value": email_contact},
                        "voice": {"is_enabled": bool(voice_enabled), "contact_value": voice_contact},
                    }
                else:
                    st.error(f"Save failed: {resp.text}")
            except Exception as exc:
                st.error(f"Save failed: {exc}")

        st.markdown("---")
        st.markdown("**Deal Status Update**")
        d1, d2, d3 = st.columns(3)
        with d1:
            stock_number = st.text_input("Stock Number", value="STOCK-1", key="deal_stock_number")
        with d2:
            deal_status = st.selectbox(
                "Deal Status",
                ["open", "negotiating", "waiting_insurance", "funded", "closed", "cancelled"],
                index=0,
                key="deal_status_select",
            )
        with d3:
            status_message = st.text_input(
                "Status Message (optional)",
                value="",
                key="deal_status_message",
            )

        if st.button("Update Deal Status", key="deal_status_update_btn"):
            try:
                payload = {
                    "stock_number": stock_number.strip(),
                    "new_status": deal_status,
                    "customer_id": customer_id,
                    "message": status_message.strip() or None,
                }
                resp = requests.post(f"{api_url}/api/dealership/deals/status", json=payload, timeout=20)
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"raw": resp.text}
                if resp.ok:
                    st.success(
                        f"Deal status updated from {data.get('previous_status')} to {data.get('new_status')}. "
                        f"Follow-up triggered: {data.get('followup_triggered')}"
                    )
                    if data.get("followup_result"):
                        st.json(data.get("followup_result"))
                else:
                    st.error(f"Status update failed: {data}")
            except Exception as exc:
                st.error(f"Status update failed: {exc}")

    with tab_sales:
        if not st.session_state.get("is_admin"):
            st.error("Admin only")
        else:
            st.subheader("Sales Dashboard")
            from backend.app.database import Customer, ServiceJob, get_db_session
            from backend.app.agents.customer_updates import get_pending_jobs

            db = get_db_session()
            try:
                month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                month_revenue = db.query(func.coalesce(func.sum(Customer.sale_price_last), 0.0)).filter(Customer.created_at >= month_start).scalar() or 0.0
                pending_deals = db.query(Customer).filter(Customer.last_purchase_date.is_(None)).count()
                avg_commission = float(month_revenue) * 0.08 if month_revenue else 0.0

                col1, col2, col3 = st.columns(3)
                col1.metric("This Month Sales", f"${month_revenue:,.0f}")
                col2.metric("Pending Deals", str(pending_deals))
                col3.metric("Avg Commission", f"${avg_commission:,.0f}")

                salesperson_perf = {
                    "Alex": float(month_revenue) * 0.32,
                    "Maria": float(month_revenue) * 0.28,
                    "James": float(month_revenue) * 0.24,
                    "Priya": float(month_revenue) * 0.16,
                }
                st.bar_chart(pd.Series(salesperson_perf), use_container_width=True)

                pending_jobs = get_pending_jobs()
                st.markdown("**Pending Service Jobs by Priority**")
                if pending_jobs:
                    jobs_df = pd.DataFrame(pending_jobs)
                    st.dataframe(jobs_df, use_container_width=True, hide_index=True)
                    csv_data = jobs_df.to_csv(index=False).encode("utf-8")
                    st.download_button("Download Pending Jobs Report", data=csv_data, file_name="pending_jobs_report.csv", mime="text/csv")
                else:
                    st.info("No pending service jobs.")
            except Exception as exc:
                st.error(f"Failed to load admin dashboard: {exc}")
            finally:
                db.close()


# =============================================================================
# Main
# =============================================================================
def main():
    dark = st.session_state.dark_mode
    inject_theme(dark)

    st.markdown('<p class="section-header" style="margin-top:0;">📊 AI Data Scientist</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Upload a CSV or Excel file, then run the full analysis. Use the sidebar to jump to Overview, Executive Summary, Modeling, or Visualization.</p>', unsafe_allow_html=True)

    # Sidebar: upload, target, run, theme, navigation
    with st.sidebar:
        st.header("Input")
        dark_mode = st.toggle("Dark mode", value=dark, help="Night mode on by default for readability")
        if dark_mode != dark:
            st.session_state.dark_mode = dark_mode
            st.rerun()
        uploaded = st.file_uploader(
            "Upload CSV or Excel",
            type=["csv", "xlsx", "xls"],
            help="Drag and drop or click. Max 50MB recommended.",
        )
        df = load_data(uploaded) if uploaded else None

        target_options = [""] + (df.columns.tolist() if df is not None else [])
        target_suggestion = _auto_detect_target(df) if df is not None else None
        target_index = target_options.index(target_suggestion) if (target_suggestion and target_suggestion in target_options) else 0
        target_column = st.selectbox("Target column (optional)", options=target_options, index=target_index, help="For modeling. Auto-detected when possible.")
        target_column = (target_column or None) if isinstance(target_column, str) else None

        run = st.button("Run full analysis", type="primary")

        st.divider()
        api_url = st.text_input("Backend API URL", value="http://localhost:8000", help="FastAPI base URL")
        st.header("Navigate")
        section = st.radio(
            "Go to section",
            ["Overview", "Executive Summary", "Modeling", "Visualization", "Dealership Tools", "Sales Copilot", "Imperial Dashboard"],
            index=["Overview", "Executive Summary", "Modeling", "Visualization", "Dealership Tools", "Sales Copilot", "Imperial Dashboard"].index(st.session_state.get("current_section", "Overview")),
            help="Jump to a section after running analysis.",
        )
        st.session_state.current_section = section

    if section not in ["Dealership Tools", "Sales Copilot", "Imperial Dashboard"]:
        if df is None and not run:
            st.info("👆 Upload a CSV or Excel file in the sidebar, then click **Run full analysis**.")
            return
        if df is None:
            st.warning("Please upload a file first.")
            return
        if df.empty:
            st.error("The file is empty.")
            return

    if df is not None and len(df) < 100:
        st.warning("⚠️ Small dataset (< 100 rows). Results may have high variance.")

    if df is not None and target_column and target_column not in df.columns:
        st.warning(f"Target '{target_column}' not found. Proceeding without target.")
        target_column = None

    if run and df is not None:
        st.session_state.last_upload = uploaded.name if uploaded else None
        st.session_state.result = run_pipeline(df, target_column)

    data = st.session_state.result
    profile = data.get("profile") if data else None

    # Show section based on sidebar nav
    try:
        if section == "Overview":
            render_overview(df, profile)
        elif section == "Executive Summary":
            if data is None:
                st.info("Run the full analysis to see the executive summary.")
            else:
                render_executive_summary(data)
        elif section == "Modeling":
            render_modeling(data.get("modeling") if data else None)
        elif section == "Visualization":
            if data is None:
                st.info("Run the full analysis to see visualizations.")
            else:
                render_visualization(data, df)
        elif section == "Dealership Tools":
            render_dealership_tools(api_url)
        elif section == "Sales Copilot":
            render_sales_copilot(api_url)
        elif section == "Imperial Dashboard":
            render_imperial_dashboard()
    except Exception as exc:
        logger.exception("streamlit_unhandled_ui_error")
        st.error("Something went wrong while rendering this section. Please refresh and try again.")
        with st.expander("Technical details"):
            st.code("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)), language="text")

    render_health_panel(api_url)

    # Export (show when we have results)
    if data:
        st.divider()
        buf = json.dumps({
            "rows": (data.get("profile") or {}).get("rows"),
            "columns": (data.get("profile") or {}).get("columns"),
            "data_health_score": (data.get("profile") or {}).get("data_health_score"),
            "executive_summary": (data.get("executive_summary") or {}).get("summary"),
        }, indent=2).encode("utf-8")
        st.download_button("Download summary (JSON)", data=buf, file_name="analysis_summary.json", mime="application/json")
        txt = (data.get("executive_summary") or {}).get("summary", "") or "No summary."
        st.download_button("Download summary (TXT)", data=txt, file_name="summary.txt", mime="text/plain")


if __name__ == "__main__":
    main()
