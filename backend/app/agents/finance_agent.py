"""Sales finance helper logic for presenting payment ladders."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from backend.app.agents.finance_calibration import normalize_credit_tier
from backend.app.agents.math_tools import auto_loan_payment

DEFAULT_APR_BY_TIER = {
    "A": 4.9,
    "B": 7.9,
    "C": 12.9,
    "D": 18.9,
}



def _credit_tier_path() -> Path:
    return Path(os.getenv("DATA_DIR", "data")) / "credit_tiers.json"


def _load_apr_by_tier() -> dict[str, float]:
    credit_tier_path = _credit_tier_path()
    if not credit_tier_path.exists():
        return DEFAULT_APR_BY_TIER.copy()

    try:
        payload = json.loads(credit_tier_path.read_text(encoding="utf-8"))
        raw_rates = payload.get("tier_rates", {}) if isinstance(payload, dict) else {}
        calibrated = {
            str(tier).strip().upper(): float(rate)
            for tier, rate in raw_rates.items()
            if str(tier).strip() and rate is not None
        }
    except Exception:
        return DEFAULT_APR_BY_TIER.copy()

    merged = DEFAULT_APR_BY_TIER.copy()
    merged.update(calibrated)
    return merged


def payment_ladder(
    vehicle_price: float,
    down_payment: float,
    credit_tier: str,
    term_months: int,
    tax_rate: float = 0.0625,
    fees: float = 495.0,
    trade_in_value: float = 0.0,
    trade_payoff: float = 0.0,
    include_taxes_in_loan: bool = True,
    state: str = "MA",
) -> dict[str, Any]:
    price = max(float(vehicle_price), 0.0)
    down = max(float(down_payment), 0.0)
    term = int(max(min(term_months, 84), 12))
    apr_by_tier = _load_apr_by_tier()

    if term <= 0:
        return {"status": "error", "message": "term_months must be > 0"}

    tier = normalize_credit_tier(credit_tier or "B") or "B"
    apr = float(apr_by_tier.get(tier, apr_by_tier["B"]))

    primary = auto_loan_payment(
        price=price,
        down=down,
        trade_in=trade_in_value,
        owed_on_trade=trade_payoff,
        rate=apr,
        term=term,
        sales_tax_rate=float(tax_rate),
        fees=float(fees),
        include_taxes_in_loan=bool(include_taxes_in_loan),
        state=state,
    )

    monthly = float(primary.get("monthly_payment", 0.0))
    amount_financed = float(primary.get("total_loan_amount", 0.0))
    tax_amount = float(primary.get("sales_tax", 0.0))
    net_trade = float(primary.get("trade_in_equity", 0.0))
    total_paid = float(primary.get("total_cost", 0.0))

    monthly_income_required = monthly / 0.12 if monthly > 0 else 0.0

    down_options = [
        max(price * 0.00, 0.0),
        max(price * 0.05, 0.0),
        max(price * 0.10, 0.0),
        max(price * 0.15, 0.0),
        max(price * 0.20, 0.0),
    ]

    ladder = []
    for option in down_options:
        option_result = auto_loan_payment(
            price=price,
            down=option,
            trade_in=trade_in_value,
            owed_on_trade=trade_payoff,
            rate=apr,
            term=term,
            sales_tax_rate=float(tax_rate),
            fees=float(fees),
            include_taxes_in_loan=bool(include_taxes_in_loan),
            state=state,
        )
        financed = float(option_result.get("total_loan_amount", 0.0))
        pmt = float(option_result.get("monthly_payment", 0.0))
        ladder.append(
            {
                "down_payment": round(option, 2),
                "monthly_payment": round(pmt, 2),
                "amount_financed": round(financed, 2),
            }
        )

    objection_handlers = {
        "payment_too_high": "If we found a similar vehicle with lower miles at this payment, would that help?",
        "rate_too_high": "With two to three on-time payments, we can usually revisit refinance options.",
        "down_payment": "We can structure options from $0 down to 20% so you stay in budget today.",
    }

    return {
        "status": "ok",
        "vehicle_price": round(price, 2),
        "term_months": term,
        "credit_tier": tier,
        "apr": round(apr, 2),
        "tax_amount": round(tax_amount, 2),
        "state": (state or "").strip().upper() or "MA",
        "include_taxes_in_loan": bool(include_taxes_in_loan),
        "state_reduces_trade_tax": bool(primary.get("state_reduces_trade_tax", True)),
        "fees": round(float(fees), 2),
        "trade_in_value": round(float(trade_in_value), 2),
        "trade_payoff": round(float(trade_payoff), 2),
        "net_trade_equity": round(net_trade, 2),
        "down_payment": round(down, 2),
        "amount_financed": round(amount_financed, 2),
        "monthly_payment": round(monthly, 2),
        "total_paid_with_down": round(total_paid, 2),
        "monthly_income_required_for_12pct_rule": round(monthly_income_required, 2),
        "down_payment_ladder": ladder,
        "credit_tier_source": str(_credit_tier_path()) if _credit_tier_path().exists() else "defaults",
        "amortization_monthly": primary.get("amortization_monthly", []),
        "amortization_annual": primary.get("amortization_annual", []),
        "total_interest": primary.get("total_interest", 0.0),
        "objection_handlers": objection_handlers,
    }
