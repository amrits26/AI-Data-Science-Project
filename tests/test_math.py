"""Comprehensive tests for dealership financial math utilities."""

from backend.app.agents.math_tools import (
    amortization_schedule,
    break_even_miles,
    lease_calculator,
    lease_vs_buy,
    loan_calculator,
    profit_projection,
    trade_in_equity,
)


def test_loan_calculator_basic_positive():
    monthly, total = loan_calculator(30000, 5000, 6.9, 60)
    assert monthly > 0
    assert total > 30000


def test_loan_calculator_zero_apr():
    monthly, total = loan_calculator(24000, 4000, 0, 40)
    assert monthly == 500.0
    assert total == 24000.0


def test_loan_calculator_zero_term_graceful():
    monthly, total = loan_calculator(24000, 4000, 5, 0)
    assert monthly == 0.0
    assert total == 24000.0


def test_loan_calculator_full_down_payment():
    monthly, total = loan_calculator(12000, 12000, 7, 48)
    assert monthly == 0.0
    assert total == 12000.0


def test_loan_calculator_high_rate_increases_payment():
    low, _ = loan_calculator(30000, 5000, 4, 60)
    high, _ = loan_calculator(30000, 5000, 12, 60)
    assert high > low


def test_lease_calculator_basic():
    result = lease_calculator(38000, 58, 0.0023, 36, 2500)
    assert result["status"] == "ok"
    assert result["monthly_payment"] > 0


def test_lease_calculator_invalid_term():
    result = lease_calculator(38000, 58, 0.0023, 0, 2500)
    assert result["status"] == "error"


def test_lease_calculator_down_payment_reduces_cap_cost():
    no_down = lease_calculator(40000, 60, 0.0022, 36, 0)
    with_down = lease_calculator(40000, 60, 0.0022, 36, 4000)
    assert with_down["cap_cost"] < no_down["cap_cost"]


def test_lease_vs_buy_returns_expected_keys():
    result = lease_vs_buy(35000, 60, 0.0024, 6.5, 36, 1000, 2000)
    assert "lease" in result
    assert "buy" in result
    assert "recommendation" in result


def test_lease_vs_buy_difference_numeric():
    result = lease_vs_buy(35000, 60, 0.0024, 6.5, 36, 1000, 2000)
    assert isinstance(result["total_comparison"]["difference"], float)


def test_trade_in_equity_positive():
    result = trade_in_equity(9000, 16000)
    assert result["status"] == "positive"
    assert result["equity"] == 7000.0


def test_trade_in_equity_negative():
    result = trade_in_equity(22000, 16000)
    assert result["status"] == "negative"
    assert result["equity"] == -6000.0
    assert result["negative"] is True


def test_trade_in_equity_neutral():
    result = trade_in_equity(16000, 16000)
    assert result["status"] == "neutral"
    assert result["equity"] == 0.0


def test_profit_projection_positive_margin():
    result = profit_projection(24000, 30000, 10, 2)
    assert result["gross_profit"] == 6000.0
    assert result["net_profit"] > 0


def test_profit_projection_negative_margin():
    result = profit_projection(32000, 30000, 10, 2)
    assert result["gross_profit"] == -2000.0


def test_break_even_miles_happy_path():
    result = break_even_miles(45000, 33000, 105, 28, 3.8, 0.14)
    assert result["status"] == "ok"
    assert result["break_even_miles"] >= 0


def test_break_even_miles_zero_efficiency_error():
    result = break_even_miles(45000, 33000, 0, 28, 3.8, 0.14)
    assert result["status"] == "error"


def test_break_even_miles_unfavorable_delta_error():
    result = break_even_miles(35000, 33000, 80, 80, 2.0, 0.3)
    assert result["status"] == "error"


def test_break_even_recommendation_text_present():
    result = break_even_miles(45000, 33000, 105, 28, 3.8, 0.14)
    assert isinstance(result["recommendation"], str)
    assert len(result["recommendation"]) > 0


def test_amortization_schedule_has_rows():
    rows = amortization_schedule(30000, 5000, 6.9, 60, 12)
    assert len(rows) == 12


def test_amortization_schedule_monotonic_balance():
    rows = amortization_schedule(30000, 5000, 6.9, 60, 24)
    balances = [r["remaining_balance"] for r in rows]
    assert all(balances[i] >= balances[i + 1] for i in range(len(balances) - 1))


def test_amortization_schedule_zero_term():
    rows = amortization_schedule(30000, 5000, 6.9, 0, 24)
    assert rows == []


def test_amortization_schedule_zero_principal():
    rows = amortization_schedule(30000, 30000, 6.9, 24, 24)
    assert rows == []


def test_loan_and_schedule_consistency():
    monthly, _ = loan_calculator(30000, 5000, 6.9, 60)
    rows = amortization_schedule(30000, 5000, 6.9, 60, 1)
    assert rows[0]["payment"] == monthly
