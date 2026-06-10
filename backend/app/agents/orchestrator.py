"""
Central Orchestration Engine for AI Data Scientist

Features:
- Problem type inference
- Data health scoring
- Multicollinearity (VIF) analysis
- Statistical insights
- Conditional modeling
- Overfitting awareness
- Anomaly detection
- Cognitive risk flags
- Executive summary generation
- Performance timing
- Guardrails for stability
"""

import os
import time
from typing import Any, Dict, Optional

import pandas as pd

# -----------------------------
# Agents
# -----------------------------
from .profiler import profile_dataset
from .statistical import run_statistical_insights
from .modeling import recommend_and_run_models
from .anomaly import run_anomaly_detection
from .cognitive_flags import compute_cognitive_flags
from .insight_generator import generate_insights

# -----------------------------
# Core Intelligence Modules
# -----------------------------
from ..core.problem_inference import infer_problem_type
from ..core.data_health import compute_data_health_score
from ..core.multicollinearity import compute_vif_index


# -----------------------------
# Performance Guardrails
# -----------------------------
MAX_ROWS = 100_000
MAX_COLUMNS = 200


class AnalysisOrchestrator:
    def __init__(self, df: pd.DataFrame, target_column: Optional[str] = None):
        self.trace: list[str] = []
        self.timings: Dict[str, float] = {}
        self.df = self._apply_guardrails(df)
        self.target = target_column

    # =====================================================
    # PUBLIC EXECUTION PIPELINE
    # =====================================================

    def run(self) -> Dict[str, Any]:
        start_total = time.time()

        # ---------------------------------------------
        # 1️⃣ Problem Type Inference
        # ---------------------------------------------
        problem_info = infer_problem_type(self.df, self.target)
        problem_type = problem_info["problem_type"]
        self.trace.extend(problem_info["reasoning"])

        # ---------------------------------------------
        # 2️⃣ Dataset Profiling
        # ---------------------------------------------
        profile = self._timed_step(
            "profiling_sec",
            "Dataset profiling completed",
            lambda: profile_dataset(self.df, target_column=self.target),
        )

        # ---------------------------------------------
        # 3️⃣ Data Health Score
        # ---------------------------------------------
        health = self._timed_step(
            "data_health_sec",
            "Data health score computed",
            lambda: compute_data_health_score(self.df, self.target),
        )

        # ---------------------------------------------
        # 4️⃣ Multicollinearity Analysis (VIF)
        # ---------------------------------------------
        multicollinearity = self._timed_step(
            "multicollinearity_sec",
            "Multicollinearity assessment completed",
            lambda: compute_vif_index(self.df),
        )

        # ---------------------------------------------
        # 5️⃣ Statistical Insights
        # ---------------------------------------------
        statistical = self._timed_step(
            "statistical_sec",
            "Statistical structure analysis completed",
            lambda: run_statistical_insights(
                self.df,
                target_column=self.target,
                profile=profile,
            ),
        )

        # ---------------------------------------------
        # 6️⃣ Modeling (Only if Supervised)
        # ---------------------------------------------
        modeling = None

        if problem_type in ["classification", "regression"]:
            modeling = self._timed_step(
                "modeling_sec",
                f"{problem_type.capitalize()} modeling pipeline executed",
                lambda: recommend_and_run_models(
                    self.df,
                    target_column=self.target,
                ),
            )
        else:
            self.trace.append(
                f"Modeling skipped — detected problem type: {problem_type}"
            )

        # ---------------------------------------------
        # 7️⃣ Anomaly Detection
        # ---------------------------------------------
        anomaly = self._timed_step(
            "anomaly_sec",
            "Anomaly detection completed",
            lambda: run_anomaly_detection(self.df),
        )

        # ---------------------------------------------
        # 8️⃣ Cognitive Risk Flags
        # ---------------------------------------------
        flags = self._timed_step(
            "flags_sec",
            "Cognitive risk flags generated",
            lambda: compute_cognitive_flags(
                profile=profile,
                statistical=statistical,
                modeling=modeling,
            ),
        )

        # ---------------------------------------------
        # 9️⃣ Executive Summary (LLM Optional)
        # ---------------------------------------------
        use_llm = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

        executive = self._timed_step(
            "summary_sec",
            "Executive summary generated",
            lambda: generate_insights(
                profile,
                statistical,
                modeling,
                anomaly,
                flags,
                use_llm=use_llm,
            ),
        )

        # ---------------------------------------------
        # 🔟 Final Timing
        # ---------------------------------------------
        total_runtime = time.time() - start_total
        self.timings["total_runtime_sec"] = round(total_runtime, 4)

        return {
            "problem_type": problem_type,
            "data_health": health,
            "multicollinearity": multicollinearity,
            "profile": profile,
            "statistical": statistical,
            "modeling": modeling,
            "anomaly": anomaly,
            "cognitive_flags": flags,
            "executive_summary": executive,
            "analysis_trace": self.trace,
            "performance_metrics": self.timings,
        }

    # =====================================================
    # INTERNAL UTILITIES
    # =====================================================

    def _timed_step(self, key: str, trace_msg: str, func):
        start = time.time()
        result = func()
        elapsed = time.time() - start
        self.timings[key] = round(elapsed, 4)
        self.trace.append(trace_msg)
        return result

    def _apply_guardrails(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prevent runaway memory usage or long compute times.
        """

        if df.shape[0] > MAX_ROWS:
            df = df.sample(MAX_ROWS, random_state=42)
            self.trace.append(
                f"Dataset truncated to {MAX_ROWS} rows for performance stability."
            )

        if df.shape[1] > MAX_COLUMNS:
            df = df.iloc[:, :MAX_COLUMNS]
            self.trace.append(
                f"Dataset truncated to {MAX_COLUMNS} columns for performance stability."
            )

        return df