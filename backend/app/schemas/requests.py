from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SalespersonPinRequest(StrictBaseModel):
    pin: str = Field(min_length=1)


class LoanRequest(StrictBaseModel):
    price: float = Field(ge=0)
    down_payment: float = Field(ge=0, default=0)
    annual_rate: float = Field(ge=0, default=0)
    term_months: int = Field(gt=0, default=60)


class LeaseRequest(StrictBaseModel):
    msrp: float = Field(ge=0)
    residual_percent: float = Field(ge=0, le=100)
    money_factor: float = Field(ge=0, default=0.0025)
    term_months: int = Field(gt=0, default=36)
    down_payment: float = Field(ge=0, default=0)


class LeaseVsBuyRequest(StrictBaseModel):
    price: float = Field(ge=0)
    residual_percent: float = Field(ge=0, le=100)
    money_factor: float = Field(ge=0, default=0.0025)
    loan_rate: float = Field(ge=0, default=0)
    term_months: int = Field(gt=0, default=36)
    lease_down: float = Field(ge=0, default=0)
    buy_down: float | None = Field(default=None, ge=0)


class TradeInEquityRequest(StrictBaseModel):
    amount_owed: float = Field(ge=0)
    market_value: float = Field(ge=0)


class FinanceEstimateRequest(StrictBaseModel):
    price: float = Field(gt=0)
    down_payment: float = Field(ge=0, default=0)
    annual_rate: float = Field(ge=0, default=0)
    term_months: int = Field(gt=0, default=60)
    msrp: float | None = Field(default=None, gt=0)


class TradeInEstimateRequest(StrictBaseModel):
    make: str = Field(min_length=1)
    model: str = Field(min_length=1)
    year: int | None = Field(default=None, ge=1900, le=2100)
    mileage: int = Field(default=0, ge=0)
    condition: str = Field(default="good")


class ServiceVideoApprovalRequest(StrictBaseModel):
    approved: bool = False
    reviewer: str | None = None


class BreakEvenMilesRequest(StrictBaseModel):
    ev_price: float = Field(ge=0)
    gas_price: float = Field(ge=0)
    ev_mpge: float = Field(gt=0)
    gas_mpg: float = Field(gt=0)
    gas_cost_per_gallon: float = Field(ge=0)
    electric_cost_per_kwh: float = Field(ge=0)


class VehicleLookupRequest(StrictBaseModel):
    stock_number_or_vin: str = Field(min_length=2)


class SimilarVehicleRequest(StrictBaseModel):
    stock_number: str = Field(min_length=1)
    max_results: int = Field(default=3, ge=1, le=10)


class FinanceLadderRequest(StrictBaseModel):
    vehicle_price: float = Field(gt=0)
    down_payment: float = Field(ge=0, default=0)
    credit_tier: str = Field(default="B", min_length=1, max_length=20)
    term_months: int = Field(gt=0, le=96)
    tax_rate: float = Field(default=0.0625, ge=0, le=0.2)
    fees: float = Field(default=495.0, ge=0)
    trade_in_value: float = Field(default=0.0, ge=0)
    trade_payoff: float = Field(default=0.0, ge=0)
    include_taxes_in_loan: bool = True
    state: str = Field(default="MA", min_length=2, max_length=2)


class NegotiationRequest(StrictBaseModel):
    message: str = Field(min_length=1, max_length=2000)


class PayoutRequest(StrictBaseModel):
    front_gross: float
    back_gross: float
    pack_fee: float = Field(default=0)
    commission_rate: float = Field(default=25, ge=0, le=100)
    unit_bonus: float = Field(default=0)
    csi_bonus: float = Field(default=0)


class DealStageRequest(StrictBaseModel):
    stock_number: str = Field(min_length=1)
    stage: str = Field(min_length=1)


class DealStatusUpdateRequest(StrictBaseModel):
    stock_number: str = Field(min_length=1)
    new_status: str = Field(min_length=1)
    customer_id: int | None = Field(default=None, ge=1)
    message: str | None = Field(default=None, max_length=1000)


class LeadQualityRequest(StrictBaseModel):
    name: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=30)
    email: str = Field(default="", max_length=255)
    message: str = Field(default="", max_length=2000)
    desired_vehicle: str = Field(default="", max_length=255)


class DailyGoalsRequest(StrictBaseModel):
    salesperson_id: str = Field(default="default-sales", min_length=1, max_length=100)
    call_goal: int = Field(default=0, ge=0, le=500)
    text_goal: int = Field(default=0, ge=0, le=500)
    email_goal: int = Field(default=0, ge=0, le=500)
    appointment_goal: int = Field(default=0, ge=0, le=200)


class KnowledgeQueryRequest(StrictBaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=10)


class FeedbackRequest(StrictBaseModel):
    interaction_id: str = Field(min_length=6, max_length=64)
    rating: int = Field(ge=-1, le=1)
    context: dict[str, str | int | float | bool | None] | None = None
    question: str = Field(default="", max_length=2000)
    answer: str = Field(default="", max_length=12000)
    question_type: str = Field(default="general", max_length=100)
    source: str = Field(default="streamlit", max_length=100)
