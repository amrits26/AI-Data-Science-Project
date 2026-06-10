# backend/app/agents/modeling.py
"""
Self-contained modeling agent: infers problem type, trains RandomForest,
computes CV and overfitting risk. Safe for Streamlit; handles target_column=None
and partially empty CSVs. No circular imports — core imports are inside the function.
"""

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

MIN_SAMPLES_FOR_MODEL = 10
MIN_SAMPLES_FOR_CV = 5
DEFAULT_CV = 5


def recommend_and_run_models(df: pd.DataFrame, target_column: Optional[str] = None):
    """
    Run supervised modeling when possible; otherwise return a clear skip/fail message.

    - Avoids circular imports: app.core imports are inside this function.
    - Guards: target missing/empty, target not in CSV, too few rows (min 10),
      no numeric features, classification with only one class.
    - Automatically detects problem type (classification vs regression) via infer_problem_type.
    - Encodes categorical targets safely for classification.
    - Uses RandomForestClassifier (classification) or RandomForestRegressor (regression).
    - Computes training score, test score, and cross-validation scores (adapts CV folds for small datasets).
    - Computes overfitting risk via compute_overfitting_risk.
    - Returns dict with problem_type, model_used, cross_val_mean, cross_val_std, overfitting_analysis,
      OR a "message" if skipped/failed. Whole pipeline wrapped in try/except.
    """
    # -------------------------------------------------------------------------
    # Guards (no app.core imports here — safe even if CSV is missing or empty)
    # -------------------------------------------------------------------------
    if df is None or (not isinstance(df, pd.DataFrame)):
        return {"message": "Modeling skipped — no dataset provided."}

    if df.empty or len(df) == 0:
        return {"message": "Modeling skipped — CSV is empty."}

    # Target column missing or empty
    if not target_column or not str(target_column).strip():
        return {
            "message": "Modeling skipped — no target column provided. Choose a target when uploading to run supervised modeling.",
        }

    # Target column not in CSV
    if target_column not in df.columns:
        return {
            "message": f"Modeling skipped — target column '{target_column}' not found in the CSV. Available columns: {list(df.columns)}.",
        }

    try:
        # Imports inside function to avoid circular imports.
        from ..core.problem_inference import infer_problem_type
        from ..core.overfitting import compute_overfitting_risk

        # Metrics for advanced visualizations
        from sklearn.metrics import roc_curve, precision_recall_curve

        # Automatically detect problem type
        problem_info = infer_problem_type(df, target_column)
        problem_type = problem_info.get("problem_type")

        if problem_type not in ("classification", "regression"):
            return {"message": f"Modeling skipped — unsupported problem type: {problem_type}."}

        # Prepare features (numeric only) and target; drop rows where target is missing
        X = df.drop(columns=[target_column]).select_dtypes(include=np.number).fillna(0)
        y = df[target_column].copy()

        valid = y.notna()
        if valid.sum() < MIN_SAMPLES_FOR_MODEL:
            return {
                "message": f"Modeling skipped — too few valid rows for target '{target_column}' (need at least {MIN_SAMPLES_FOR_MODEL}).",
            }
        X = X.loc[valid].reset_index(drop=True)
        y = y.loc[valid].reset_index(drop=True)

        # No numeric features
        if X.shape[1] == 0:
            return {
                "message": "Modeling skipped — no numeric feature columns in the CSV. Add numeric columns (besides the target) to run modeling.",
            }

        if len(X) < MIN_SAMPLES_FOR_MODEL:
            return {
                "message": f"Modeling skipped — need at least {MIN_SAMPLES_FOR_MODEL} rows after dropping missing targets.",
            }

        # Choose model; encode categorical targets safely for classification
        if problem_type == "classification":
            if y.dtype == "object" or pd.api.types.is_categorical_dtype(y):
                # Encode categorical targets safely (NaNs already dropped above)
                y = pd.Series(LabelEncoder().fit_transform(y.astype(str)), index=y.index)
            # Classification target with only one class
            if y.nunique() < 2:
                return {
                    "message": "Modeling skipped — target has only one unique value; need at least two classes for classification.",
                }
            model = RandomForestClassifier(n_estimators=100)
            scoring = "accuracy"
        else:
            model = RandomForestRegressor(n_estimators=100)
            scoring = "r2"

        # Split (stratify for classification when enough samples)
        if problem_type == "classification" and y.nunique() >= 2 and len(y) >= 20:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

        # Train and evaluate: training score, test score
        model.fit(X_train, y_train)
        train_score = float(model.score(X_train, y_train))
        test_score = float(model.score(X_test, y_test))

        # Predicted vs actual on held-out set
        try:
            y_pred = model.predict(X_test)
        except Exception:
            y_pred = None

        # Classification probabilities for ROC / PR
        y_proba = None
        if problem_type == "classification" and hasattr(model, "predict_proba"):
            try:
                proba = model.predict_proba(X_test)
                # Use positive class (index 1) when binary, else best-effort first non-baseline
                if proba.ndim == 2 and proba.shape[1] >= 2:
                    y_proba = proba[:, 1]
                elif proba.ndim == 2 and proba.shape[1] == 1:
                    y_proba = proba[:, 0]
            except Exception:
                y_proba = None

        # Cross-validation; adapt CV folds if dataset is small
        n = len(X)
        cv = (
            min(DEFAULT_CV, max(2, n // 2))
            if n < MIN_SAMPLES_FOR_CV * DEFAULT_CV
            else DEFAULT_CV
        )
        cv_scores = cross_val_score(model, X, y, cv=cv, scoring=scoring)

        # Overfitting risk
        overfit = compute_overfitting_risk(train_score, test_score)

        # Feature importance for downstream agents and UI
        feat_imp = dict(
            zip(
                X.columns.tolist(),
                [
                    round(float(x), 6)
                    for x in getattr(
                        model,
                        "feature_importances_",
                        np.ones(len(X.columns)) / max(len(X.columns), 1),
                    )
                ],
            )
        )
        risk_label = overfit.get("overfitting_risk", "unknown")
        summary = (
            f"{problem_type.capitalize()} model {type(model).__name__}: "
            f"CV {scoring} = {np.mean(cv_scores):.4f} (±{np.std(cv_scores):.4f}). "
            f"Overfitting risk: {risk_label}."
        )
        overfitting_risk_str = (
            f"Train/test gap: {overfit.get('score_gap', 0):.2f} — {risk_label} risk. "
            f"Train score: {overfit.get('train_score', 0):.2f}, validation: {overfit.get('validation_score', 0):.2f}."
        )

        # Predicted vs actual (down-sampled to keep UI fast)
        pred_vs_actual = None
        if y_pred is not None:
            max_points = 1000
            n_test = len(y_test)
            if n_test > 0:
                if n_test > max_points:
                    rng = np.random.RandomState(42)
                    idx = rng.choice(n_test, size=max_points, replace=False)
                    y_true_plot = y_test.iloc[idx].tolist()
                    y_pred_plot = [
                        float(y_pred[i])
                        if isinstance(y_pred[i], (int, float, np.number))
                        else y_pred[i]
                        for i in idx
                    ]
                else:
                    y_true_plot = y_test.tolist()
                    y_pred_plot = [
                        float(v)
                        if isinstance(v, (int, float, np.number))
                        else v
                        for v in y_pred
                    ]
                pred_vs_actual = {
                    "y_true": y_true_plot,
                    "y_pred": y_pred_plot,
                }

        # Residuals for regression (sampled)
        residuals_sample = None
        if problem_type == "regression" and y_pred is not None:
            try:
                residuals = y_test.to_numpy() - np.asarray(y_pred)
                max_points = 2000
                n_res = len(residuals)
                if n_res > max_points:
                    rng = np.random.RandomState(42)
                    idx = rng.choice(n_res, size=max_points, replace=False)
                    residuals_sample = [float(residuals[i]) for i in idx]
                else:
                    residuals_sample = [float(r) for r in residuals]
            except Exception:
                residuals_sample = None

        # ROC and precision-recall curves for binary classification
        roc_curve_pts = None
        pr_curve_pts = None
        if problem_type == "classification" and y_proba is not None:
            try:
                unique_classes = np.unique(y_test)
                if len(unique_classes) == 2:
                    fpr, tpr, _ = roc_curve(y_test, y_proba)
                    prec, rec, _ = precision_recall_curve(y_test, y_proba)
                    roc_curve_pts = {
                        "fpr": [float(x) for x in fpr],
                        "tpr": [float(x) for x in tpr],
                    }
                    pr_curve_pts = {
                        "precision": [float(x) for x in prec],
                        "recall": [float(x) for x in rec],
                    }
            except Exception:
                roc_curve_pts = None
                pr_curve_pts = None

        # SHAP-style global importance (mean |SHAP| per feature) for RandomForest
        shap_importance = None
        try:
            import shap
            # Use a small sample for efficiency
            sample_size = min(200, len(X_train))
            if sample_size > 0 and hasattr(model, "feature_importances_"):
                sample_X = X_train.sample(sample_size, random_state=42)
                explainer = shap.TreeExplainer(model)
                shap_vals = explainer.shap_values(sample_X)
                if isinstance(shap_vals, list):
                    shap_arr = np.array(shap_vals[1 if len(shap_vals) > 1 else 0])
                else:
                    shap_arr = np.array(shap_vals)
                shap_abs_mean = np.mean(np.abs(shap_arr), axis=0)
                shap_importance = dict(
                    zip(
                        sample_X.columns.tolist(),
                        [float(x) for x in shap_abs_mean],
                    )
                )
        except Exception:
            shap_importance = None

        return {
            "problem_type": problem_type,
            "model_used": type(model).__name__,
            "cross_val_mean": float(np.mean(cv_scores)),
            "cross_val_std": float(np.std(cv_scores)),
            "cv_scores": [float(x) for x in cv_scores],
            "train_score": train_score,
            "test_score": test_score,
            "overfitting_analysis": overfit,
            "overfitting_risk": overfitting_risk_str,
            "inferred_task": problem_type,
            "summary": summary,
            "feature_importance": feat_imp,
            "best_model": type(model).__name__,
            "pred_vs_actual": pred_vs_actual,
            "residuals_sample": residuals_sample,
            "roc_curve": roc_curve_pts,
            "pr_curve": pr_curve_pts,
            "shap_importance": shap_importance,
        }

    except Exception as e:
        return {
            "message": f"Modeling failed: {str(e)}",
        }