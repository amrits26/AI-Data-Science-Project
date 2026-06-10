"""Financial math utilities for dealership workflows using Decimal precision."""

from __future__ import annotations

import json
import os
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation, getcontext
from pathlib import Path
from typing import Any

getcontext().prec = 28
MONEY_Q = Decimal("0.01")


def _d(value: Any) -> Decimal:
    """Safely coerce arbitrary numeric input to Decimal."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _money(value: Decimal) -> float:
    """Round to cents and return float for API/json compatibility."""
    return float(value.quantize(MONEY_Q, rounding=ROUND_HALF_UP))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def _state_tax_rules_path() -> Path:
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    return data_dir / "state_tax_rules.json"


def _load_state_tax_rules() -> dict[str, Any]:
    path = _state_tax_rules_path()
    if not path.exists():
        return {"no_trade_in_tax_credit": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"no_trade_in_tax_credit": []}
    return payload if isinstance(payload, dict) else {"no_trade_in_tax_credit": []}


def _state_reduces_trade_tax(state: str) -> bool:
    norm = (state or "").strip().upper()
    blocked = {
        str(item).strip().upper()
        for item in _load_state_tax_rules().get("no_trade_in_tax_credit", [])
        if str(item).strip()
    }
    return norm not in blocked


def _pmt(rate: Decimal, periods: int, principal: Decimal) -> Decimal:
    if periods <= 0 or principal <= 0:
        return Decimal("0")
    if rate <= 0:
        return principal / Decimal(periods)
    factor = (Decimal("1") + rate) ** Decimal(periods)
    denominator = factor - Decimal("1")
    if denominator == 0:
        return principal / Decimal(periods)
    return principal * (rate * factor) / denominator


def auto_loan_payment(
    price: float,
    down: float,
    trade_in: float,
    owed_on_trade: float,
    rate: float,
    term: int,
    sales_tax_rate: float,
    fees: float,
    include_taxes_in_loan: bool,
    state: str,
) -> dict[str, Any]:
    """Calculator-parity auto loan math with state trade-in tax treatment.

    Returns monthly payment, total loan amount, total interest, total cost,
    and both monthly and annual amortization summaries.
    """

    safe_price = _d(max(float(price or 0), 0.0))
    safe_down = _d(max(float(down or 0), 0.0))
    safe_trade = _d(max(float(trade_in or 0), 0.0))
    safe_owed = _d(max(float(owed_on_trade or 0), 0.0))
    safe_rate = _d(_clamp(float(rate or 0), 0.0, 30.0))
    safe_term = int(_clamp(float(term or 0), 12.0, 84.0))
    safe_tax_rate = _d(_clamp(float(sales_tax_rate or 0), 0.0, 0.25))
    safe_fees = _d(max(float(fees or 0), 0.0))

    trade_in_equity = max(safe_trade - safe_owed, Decimal("0"))
    reduces_tax_base = _state_reduces_trade_tax(state)
    taxable_amount = safe_price
    if include_taxes_in_loan and reduces_tax_base:
        taxable_amount = max(safe_price - safe_trade, Decimal("0"))

    sales_tax = taxable_amount * safe_tax_rate

    amount_financed = safe_price - safe_down - trade_in_equity + safe_fees
    if include_taxes_in_loan:
        amount_financed += sales_tax
    amount_financed = max(amount_financed, Decimal("0"))

    monthly_rate = safe_rate / Decimal("1200")
    monthly_payment = _pmt(monthly_rate, safe_term, amount_financed)
    if amount_financed <= 0:
        monthly_payment = Decimal("0")

    amortization_monthly: list[dict[str, Any]] = []
    amortization_annual_map: dict[int, dict[str, Decimal]] = {}
    balance = amount_financed

    for month in range(1, safe_term + 1):
        if monthly_payment <= 0 and balance <= 0:
            break

        interest_paid = balance * monthly_rate if monthly_rate > 0 else Decimal("0")
        principal_paid = monthly_payment - interest_paid
        if principal_paid > balance:
            principal_paid = balance
        if principal_paid < 0:
            principal_paid = Decimal("0")

        payment_value = principal_paid + interest_paid
        balance = max(balance - principal_paid, Decimal("0"))

        amortization_monthly.append(
            {
                "month": month,
                "payment": _money(payment_value),
                "principal": _money(principal_paid),
                "interest": _money(interest_paid),
                "remaining_balance": _money(balance),
            }
        )

        year = (month - 1) // 12 + 1
        bucket = amortization_annual_map.setdefault(
            year,
            {"payment": Decimal("0"), "principal": Decimal("0"), "interest": Decimal("0"), "ending_balance": Decimal("0")},
        )
        bucket["payment"] += payment_value
        bucket["principal"] += principal_paid
        bucket["interest"] += interest_paid
        bucket["ending_balance"] = balance

    amortization_annual = [
        {
            "year": year,
            "payment": _money(values["payment"]),
            "principal": _money(values["principal"]),
            "interest": _money(values["interest"]),
            "ending_balance": _money(values["ending_balance"]),
        }
        for year, values in sorted(amortization_annual_map.items())
    ]

    total_interest = sum(_d(row["interest"]) for row in amortization_monthly)
    tax_due_at_signing = sales_tax if not include_taxes_in_loan else Decimal("0")
    total_cost = safe_down + safe_fees + tax_due_at_signing + sum(_d(row["payment"]) for row in amortization_monthly)

    return {
        "status": "ok",
        "state": (state or "").strip().upper() or "MA",
        "state_reduces_trade_tax": reduces_tax_base,
        "include_taxes_in_loan": bool(include_taxes_in_loan),
        "price": _money(safe_price),
        "down_payment": _money(safe_down),
        "trade_in_value": _money(safe_trade),
        "owed_on_trade": _money(safe_owed),
        "trade_in_equity": _money(trade_in_equity),
        "sales_tax_rate": float(safe_tax_rate),
        "taxable_amount": _money(taxable_amount),
        "sales_tax": _money(sales_tax),
        "fees": _money(safe_fees),
        "term_months": safe_term,
        "annual_rate": float(safe_rate),
        "monthly_payment": _money(monthly_payment),
        "total_loan_amount": _money(amount_financed),
        "total_interest": _money(total_interest),
        "total_cost": _money(total_cost),
        "tax_due_at_signing": _money(tax_due_at_signing),
        "amortization_monthly": amortization_monthly,
        "amortization_annual": amortization_annual,
    }


def reverse_loan_calculator(monthly_payment: float, rate: float, term: int) -> dict[str, Any]:
    safe_payment = _d(max(float(monthly_payment or 0), 0.0))
    safe_rate = _d(_clamp(float(rate or 0), 0.0, 30.0))
    safe_term = int(_clamp(float(term or 0), 12.0, 84.0))

    monthly_rate = safe_rate / Decimal("1200")
    if safe_payment <= 0:
        principal = Decimal("0")
    elif monthly_rate <= 0:
        principal = safe_payment * Decimal(safe_term)
    else:
        factor = (Decimal("1") + monthly_rate) ** Decimal(safe_term)
        principal = safe_payment * ((factor - Decimal("1")) / (monthly_rate * factor))

    return {
        "status": "ok",
        "monthly_payment": _money(safe_payment),
        "annual_rate": float(safe_rate),
        "term_months": safe_term,
        "estimated_price": _money(max(principal, Decimal("0"))),
    }


def cash_back_vs_low_interest(price: float, cash_back: float, low_rate: float, standard_rate: float, term: int) -> dict[str, Any]:
    safe_price = max(float(price or 0), 0.0)
    safe_cash_back = max(float(cash_back or 0), 0.0)
    low = auto_loan_payment(
        price=safe_price,
        down=0,
        trade_in=0,
        owed_on_trade=0,
        rate=low_rate,
        term=term,
        sales_tax_rate=0,
        fees=0,
        include_taxes_in_loan=False,
        state="MA",
    )
    standard = auto_loan_payment(
        price=max(safe_price - safe_cash_back, 0.0),
        down=0,
        trade_in=0,
        owed_on_trade=0,
        rate=standard_rate,
        term=term,
        sales_tax_rate=0,
        fees=0,
        include_taxes_in_loan=False,
        state="MA",
    )

    low_cost = float(low.get("total_cost", 0.0))
    standard_cost = float(standard.get("total_cost", 0.0))
    if low_cost <= standard_cost:
        recommendation = "low_interest"
        savings = standard_cost - low_cost
    else:
        recommendation = "cash_back"
        savings = low_cost - standard_cost

    return {
        "status": "ok",
        "price": safe_price,
        "cash_back": safe_cash_back,
        "low_interest_option": {
            "annual_rate": float(_clamp(low_rate, 0.0, 30.0)),
            "monthly_payment": low.get("monthly_payment", 0.0),
            "total_cost": low_cost,
        },
        "cash_back_option": {
            "annual_rate": float(_clamp(standard_rate, 0.0, 30.0)),
            "monthly_payment": standard.get("monthly_payment", 0.0),
            "total_cost": standard_cost,
            "adjusted_price": max(safe_price - safe_cash_back, 0.0),
        },
        "recommended": recommendation,
        "estimated_savings": round(max(savings, 0.0), 2),
    }


def loan_calculator(price: float, down_payment: float, annual_rate: float, term_months: int) -> tuple[float, float]:
    """Compute monthly payment and total out-of-pocket loan cost.

    Returns (monthly_payment, total_cost).
    """
    p = _d(price)
    down = _d(down_payment)
    apr = _d(annual_rate)
    n = int(term_months or 0)

    if n <= 0:
        return 0.0, _money(max(p, Decimal("0")))

    principal = max(p - down, Decimal("0"))
    if principal == 0:
        return 0.0, _money(down)

    if apr <= 0:
        monthly = principal / Decimal(n)
        total = monthly * Decimal(n) + down
        return _money(monthly), _money(total)

    r = apr / Decimal("1200")
    one_plus_r_pow_n = (Decimal("1") + r) ** Decimal(n)
    denominator = one_plus_r_pow_n - Decimal("1")
    if denominator == 0:
        monthly = principal / Decimal(n)
    else:
        monthly = principal * (r * one_plus_r_pow_n) / denominator

    total = monthly * Decimal(n) + down
    return _money(monthly), _money(total)


def lease_calculator(
    msrp: float,
    residual_percent: float,
    money_factor: float,
    term_months: int,
    down_payment: float = 0,
) -> dict[str, Any]:
    """Compute standard lease cost components.

    Formula:
    monthly = depreciation_charge + interest_charge
    depreciation_charge = (cap_cost - residual_value) / term
    interest_charge = (cap_cost + residual_value) * money_factor
    """
    m = _d(msrp)
    residual_pct = _d(residual_percent)
    mf = _d(money_factor)
    term = int(term_months or 0)
    down = _d(down_payment)

    if term <= 0:
        return {
            "monthly_payment": 0.0,
            "total_lease_cost": _money(down),
            "cap_cost": _money(max(m - down, Decimal("0"))),
            "residual_value": 0.0,
            "depreciation_charge": 0.0,
            "interest_charge": 0.0,
            "term_months": term,
            "status": "error",
            "message": "term_months must be > 0",
        }

    if residual_pct < 0 or residual_pct > 100:
        return {
            "monthly_payment": 0.0,
            "total_lease_cost": _money(down),
            "cap_cost": _money(max(m - down, Decimal("0"))),
            "residual_value": 0.0,
            "depreciation_charge": 0.0,
            "interest_charge": 0.0,
            "term_months": term,
            "status": "error",
            "message": "residual_percent must be between 0 and 100",
        }

    cap_cost = max(m - down, Decimal("0"))
    residual_value = m * (residual_pct / Decimal("100"))
    depreciation_charge = (cap_cost - residual_value) / Decimal(term)
    interest_charge = (cap_cost + residual_value) * max(mf, Decimal("0"))
    monthly_payment = depreciation_charge + interest_charge
    total_lease_cost = monthly_payment * Decimal(term) + down

    return {
        "monthly_payment": _money(monthly_payment),
        "total_lease_cost": _money(total_lease_cost),
        "cap_cost": _money(cap_cost),
        "residual_value": _money(residual_value),
        "depreciation_charge": _money(depreciation_charge),
        "interest_charge": _money(interest_charge),
        "term_months": term,
        "status": "ok",
    }


def lease_vs_buy(
    price: float,
    residual_percent: float,
    money_factor: float,
    loan_rate: float,
    term_months: int,
    lease_down: float = 0,
    buy_down: float | None = None,
) -> dict[str, Any]:
    """Compare lease and buy economics over a common term."""
    buy_down_value = lease_down if buy_down is None else buy_down
    lease = lease_calculator(price, residual_percent, money_factor, term_months, lease_down)
    buy_monthly, buy_total = loan_calculator(price, buy_down_value, loan_rate, term_months)

    residual_value = _d(price) * (_d(residual_percent) / Decimal("100"))
    net_buy_cost = _d(buy_total) - residual_value
    lease_total = _d(lease.get("total_lease_cost", 0))
    diff = net_buy_cost - lease_total

    if diff > 0:
        recommendation = f"Lease: Save ${_money(diff):,.0f} over {term_months} months"
    elif diff < 0:
        recommendation = f"Buy: Save ${_money(-diff):,.0f} over {term_months} months"
    else:
        recommendation = "Lease and buy are cost-equivalent in this scenario"

    return {
        "lease": lease,
        "buy": {
            "monthly_payment": buy_monthly,
            "total_loan_cost": buy_total,
            "residual_value": _money(residual_value),
            "net_cost": _money(net_buy_cost),
            "down_payment": _money(_d(buy_down_value)),
        },
        "total_comparison": {
            "lease_total": _money(lease_total),
            "buy_net_total": _money(net_buy_cost),
            "difference": _money(diff),
        },
        "recommendation": recommendation,
    }


def trade_in_equity(amount_owed: float, market_value: float) -> dict[str, Any]:
    """Compute positive/negative equity for a trade-in."""
    owed = _d(amount_owed)
    value = _d(market_value)
    equity = value - owed

    if equity > 0:
        status = "positive"
        recommendation = f"You have ${_money(equity):,.0f} in positive equity."
    elif equity < 0:
        status = "negative"
        recommendation = f"You are ${_money(-equity):,.0f} underwater on the current loan."
    else:
        status = "neutral"
        recommendation = "You are exactly break-even on this trade-in."

    return {
        "market_value": _money(value),
        "amount_owed": _money(owed),
        "equity": _money(equity),
        "negative": equity < 0,
        "status": status,
        "recommendation": recommendation,
    }


def profit_projection(cost: float, sale_price: float, commission_rate: float, holdback_percent: float = 0) -> dict[str, Any]:
    """Project gross/net deal profitability using Decimal precision."""
    c = _d(cost)
    sale = _d(sale_price)
    comm = _d(commission_rate) / Decimal("100")
    holdback = _d(holdback_percent) / Decimal("100")

    gross = sale - c
    holdback_amount = sale * holdback
    commission = gross * comm
    net = gross - holdback_amount - commission

    return {
        "gross_profit": _money(gross),
        "holdback_amount": _money(holdback_amount),
        "commission": _money(commission),
        "net_profit": _money(net),
    }


def break_even_miles(
    ev_price: float,
    gas_price: float,
    ev_mpge: float,
    gas_mpg: float,
    gas_cost_per_gallon: float,
    electric_cost_per_kwh: float,
) -> dict[str, Any]:
    """Estimate EV break-even mileage against a gas vehicle.

    Returns status=error when operating-cost delta is zero/negative or MPG values invalid.
    """
    ev = _d(ev_price)
    gas = _d(gas_price)
    ev_eff = _d(ev_mpge)
    gas_eff = _d(gas_mpg)
    gas_cost = _d(gas_cost_per_gallon)
    elec_cost = _d(electric_cost_per_kwh)

    if ev_eff <= 0 or gas_eff <= 0:
        return {
            "status": "error",
            "message": "ev_mpge and gas_mpg must be > 0",
            "price_difference": _money(ev - gas),
            "cost_per_mile_ev": 0.0,
            "cost_per_mile_gas": 0.0,
            "cost_difference_per_mile": 0.0,
            "break_even_miles": 0,
            "break_even_years": 0.0,
            "recommendation": "Invalid efficiency inputs.",
        }

    gas_per_mile = gas_cost / gas_eff
    ev_per_mile = (elec_cost * Decimal("33.7")) / ev_eff
    delta = gas_per_mile - ev_per_mile
    price_gap = ev - gas

    if delta <= 0:
        return {
            "status": "error",
            "message": "Gas operating cost is not higher than EV in this scenario",
            "price_difference": _money(price_gap),
            "cost_per_mile_ev": _money(ev_per_mile),
            "cost_per_mile_gas": _money(gas_per_mile),
            "cost_difference_per_mile": _money(delta),
            "break_even_miles": 0,
            "break_even_years": 0.0,
            "recommendation": "No finite break-even point with current inputs.",
        }

    miles = int((price_gap / delta).to_integral_value(rounding=ROUND_HALF_UP)) if price_gap > 0 else 0
    years = Decimal(miles) / Decimal("12000") if miles > 0 else Decimal("0")

    return {
        "status": "ok",
        "price_difference": _money(price_gap),
        "cost_per_mile_ev": _money(ev_per_mile),
        "cost_per_mile_gas": _money(gas_per_mile),
        "cost_difference_per_mile": _money(delta),
        "break_even_miles": max(miles, 0),
        "break_even_years": _money(years),
        "recommendation": f"Break-even at {max(miles, 0):,} miles (~{_money(years)} years at 12k miles/year).",
    }


def amortization_schedule(price: float, down_payment: float, annual_rate: float, term_months: int, max_rows: int = 60) -> list[dict[str, Any]]:
    """Build amortization rows for charting and customer explanations."""
    principal = max(_d(price) - _d(down_payment), Decimal("0"))
    n = int(term_months or 0)
    if n <= 0 or principal == 0:
        return []

    monthly_payment = _d(loan_calculator(price, down_payment, annual_rate, term_months)[0])
    r = _d(annual_rate) / Decimal("1200")
    balance = principal
    rows: list[dict[str, Any]] = []

    for month in range(1, min(n, max_rows) + 1):
        interest = balance * r if r > 0 else Decimal("0")
        principal_paid = monthly_payment - interest
        if principal_paid > balance:
            principal_paid = balance
        balance = max(balance - principal_paid, Decimal("0"))

        rows.append(
            {
                "month": month,
                "payment": _money(monthly_payment),
                "principal": _money(principal_paid),
                "interest": _money(interest),
                "remaining_balance": _money(balance),
            }
        )

        if balance == 0:
            break

    return rows
