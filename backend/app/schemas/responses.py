"""Response schemas for pipeline outputs."""
from typing import Any, Optional

from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    missing_pct: float
    numeric: bool
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    cardinality: Optional[int] = None
    sample_values: Optional[list] = None


class ProfilerOutput(BaseModel):
    rows: int
    columns: int
    column_profiles: list[ColumnProfile]
    data_health_score: float
    class_imbalance: Optional[dict] = None
    leakage_indicators: list[str] = Field(default_factory=list)
    summary: str = ""


class CognitiveFlag(BaseModel):
    flag_id: str
    severity: str  # info, warning, critical
    title: str
    description: str
    math_detail: Optional[str] = None
    recommendation: Optional[str] = None


class InsightCard(BaseModel):
    id: str
    type: str  # e.g. feature_dominance, target_influence, overfitting_risk
    severity: str
    title: str
    summary: str
    detail: Optional[str] = None
    math_explanation: Optional[str] = None


class ExecutiveSummary(BaseModel):
    summary: str
    business_implications: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    model_justification: Optional[str] = None
    next_steps: list[str] = Field(default_factory=list)
    technical_notes: Optional[str] = None
