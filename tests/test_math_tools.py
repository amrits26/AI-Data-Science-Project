import pytest
from backend.app.agents import math_tools

def test_auto_loan_payment_basic():
    result = math_tools.auto_loan_payment(
        price=20000,
        down=2000,
        trade_in=0,
        owed_on_trade=0,
        rate=5.0,
        term=60,
        sales_tax_rate=0.08,
        fees=500,
        include_taxes_in_loan=True,
        state="CA"
    )
    assert isinstance(result, dict)
    assert result["monthly_payment"] > 0

def test_loan_calculator():
    principal, total = math_tools.loan_calculator(15000, 1500, 0.04, 48)
    assert principal > 0
    assert total > principal

def test_lease_calculator():
    result = math_tools.lease_calculator(
        msrp=30000,
        residual_percent=60.0,
        money_factor=0.002,
        term_months=36,
        down_payment=2000
    )
    assert isinstance(result, dict)
    assert result["monthly_payment"] > 0

def test_trade_in_equity():
    result = math_tools.trade_in_equity(amount_owed=10000, market_value=12000)
    assert result["equity"] == 2000
    assert result["status"] == "positive"

def test_profit_projection():
    result = math_tools.profit_projection(cost=15000, sale_price=18000, commission_rate=5.0)
    assert result["gross_profit"] > 0
    assert result["commission"] > 0
