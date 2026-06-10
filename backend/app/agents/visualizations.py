"""
Persuasive Visualization Module for Imperial Cars.

Generates compelling charts for:
- Monthly payment scenarios (loan terms, interest rates)
- Vehicle depreciation curves (historical market data)
- Fuel cost savings (old vs new vehicle)
- Vehicle comparison (radar/spider charts)
- Trade-in equity visualization

All charts exported as PNG bytes for display in Telegram, Streamlit, or web.
"""

import io
import base64
import logging
from typing import Optional, List, Dict, Any

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


logger = logging.getLogger(__name__)


def _fig_to_base64_png(fig) -> str:
    """Convert Plotly figure to base64-encoded PNG bytes."""
    try:
        import kaleido
        png_bytes = fig.to_image(format="png", width=800, height=600)
        return base64.b64encode(png_bytes).decode("utf-8")
    except Exception as exc:
        # Fallback: generate a small PNG status card so callers still receive displayable bytes.
        logger.warning("chart_export_failed", extra={"error": str(exc)})
        try:
            from PIL import Image, ImageDraw

            img = Image.new("RGB", (800, 200), color=(245, 245, 245))
            draw = ImageDraw.Draw(img)
            draw.text((20, 20), "Chart preview unavailable.", fill=(40, 40, 40))
            draw.text((20, 60), "Install/verify Kaleido runtime for high-fidelity export.", fill=(90, 90, 90))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception:
            return ""


def monthly_payment_chart(price: float, down: float, rate: float, term: int) -> str:
    """
    Create a chart showing monthly payment vs. term length.

    Args:
        price: Vehicle price
        down: Down payment amount
        rate: Annual interest rate (%)
        term: Loan term (months)

    Returns:
        Base64-encoded PNG bytes
    """
    from backend.app.agents.math_tools import loan_calculator

    # Calculate payments for different term lengths
    terms = [24, 36, 48, 60, 72]
    payments = []

    for t in terms:
        monthly, _ = loan_calculator(price, down, rate, t)
        payments.append({"months": t, "payment": monthly, "rate": rate})

    fig = px.bar(
        payments,
        x="months",
        y="payment",
        title=f"Monthly Payment by Term Length (${price:,.0f}, ${down:,.0f} down, {rate}% APR)",
        labels={"months": "Loan Term (months)", "payment": "Monthly Payment ($)"},
        color_discrete_sequence=["#1f77b4"],
    )

    fig.add_hline(y=payments[-1]["payment"], line_dash="dash", line_color="red", annotation_text="60-month standard")

    return _fig_to_base64_png(fig)


def depreciation_curve(make: str, model: str, years: int = 5) -> str:
    """
    Create a depreciation curve using market price history.

    Args:
        make: Vehicle make
        model: Vehicle model
        years: Number of years to project

    Returns:
        Base64-encoded PNG bytes
    """
    from backend.app.database import get_db_session, Car, MarketPrice
    from datetime import date, timedelta

    db = get_db_session()
    try:
        # Find car and get pricing history
        car = db.query(Car).filter(Car.make.ilike(make), Car.model.ilike(model)).first()
        if not car:
            # Return dummy chart if car not found
            return "Car not found in database"

        prices = db.query(MarketPrice).filter(MarketPrice.car_id == car.id).order_by(MarketPrice.date).all()

        if not prices:
            return "No pricing history available"

        price_data = [
            {"date": p.date, "price": p.price, "depreciation_pct": (p.price / car.msrp * 100) if car.msrp else 100}
            for p in prices
        ]

        fig = px.line(
            price_data,
            x="date",
            y="depreciation_pct",
            title=f"{car.year} {make} {model} - Value Retention",
            labels={"date": "Date", "depreciation_pct": "Value Retention (%)"},
        )

        fig.update_yaxes(range=[0, 100])
        return _fig_to_base64_png(fig)

    finally:
        db.close()


def savings_vs_keeping_old(old_mpg: float, new_mpg: float, miles_per_year: int, gas_price: float = 3.50) -> str:
    """
    Create a fuel savings comparison chart (old car vs new).

    Args:
        old_mpg: Old vehicle's highway MPG
        new_mpg: New vehicle's highway MPG
        miles_per_year: Annual miles driven
        gas_price: Current gas price per gallon

    Returns:
        Base64-encoded PNG bytes
    """
    years = list(range(1, 6))
    old_cost = []
    new_cost = []

    for year in years:
        total_miles = miles_per_year * year
        old_fuel_cost = (total_miles / old_mpg) * gas_price
        new_fuel_cost = (total_miles / new_mpg) * gas_price
        old_cost.append(old_fuel_cost)
        new_cost.append(new_fuel_cost)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=years, y=old_cost, name=f"Old Car ({old_mpg} MPG)", marker_color="lightcoral"))
    fig.add_trace(go.Bar(x=years, y=new_cost, name=f"New Car ({new_mpg} MPG)", marker_color="lightgreen"))

    fig.update_layout(
        title=f"5-Year Fuel Cost Comparison (${miles_per_year:,} miles/year @ ${gas_price:.2f}/gal)",
        xaxis_title="Years",
        yaxis_title="Cumulative Fuel Cost ($)",
        barmode="group",
    )

    total_savings = sum(old_cost) - sum(new_cost)
    fig.add_annotation(
        text=f"Total 5-year savings: ${total_savings:,.0f}",
        x=2.5,
        y=max(max(old_cost), max(new_cost)) * 0.9,
        showarrow=True,
        bgcolor="yellow",
        font=dict(size=12),
    )

    return _fig_to_base64_png(fig)


def comparison_radar(cars: List[Dict[str, Any]], metrics: List[str] = None) -> str:
    """
    Create a radar (spider) chart comparing multiple vehicles.

    Args:
        cars: List of car dicts with "name" and metric keys
        metrics: List of metrics to compare (e.g., ["horsepower", "mpg", "price", "safety_rating"])

    Returns:
        Base64-encoded PNG bytes
    """
    if not metrics:
        metrics = ["horsepower", "mpg_highway", "price_index", "safety_rating"]

    if len(cars) > 3:
        cars = cars[:3]  # Limit to 3 cars for clarity

    # Normalize values to 0-100 scale
    data_normalized = {}
    for metric in metrics:
        values = [c.get(metric, 0) for c in cars]
        max_val = max(values) if values else 1
        for i, car in enumerate(cars):
            if i not in data_normalized:
                data_normalized[i] = {}
            data_normalized[i][metric] = (car.get(metric, 0) / max_val * 100) if max_val else 0

    fig = go.Figure()

    for i, car in enumerate(cars):
        values = [data_normalized[i].get(m, 0) for m in metrics]
        fig.add_trace(
            go.Scatterpolar(r=values, theta=metrics, fill="toself", name=car.get("name", f"Car {i+1}"))
        )

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="Vehicle Comparison (Normalized to 100)",
        height=600,
    )

    return _fig_to_base64_png(fig)


def trade_in_boost(trade_value: float, owed: float, discount: float = 0) -> str:
    """
    Create a trade-in equity visualization.

    Args:
        trade_value: Estimated market value of trade-in
        owed: Amount still owed on existing loan
        discount: Discount applied by dealer (%)

    Returns:
        Base64-encoded PNG bytes
    """
    adjusted_value = trade_value * (1 - discount / 100)
    equity = adjusted_value - owed

    fig = go.Figure()

    # Waterfall chart
    fig.add_trace(
        go.Waterfall(
            x=["Market Value", "Loan Payoff", "Equity"],
            y=[trade_value, -owed, equity],
            measure=["absolute", "absolute", "relative"],
            connector={"line": {"color": "rgba(63, 63, 63, 0.6)"}},
        )
    )

    fig.update_layout(
        title="Your Trade-In Equity",
        yaxis_title="Amount ($)",
        height=400,
    )

    if equity > 0:
        fig.add_annotation(
            text=f"✓ You have ${equity:,.0f} positive equity!",
            x=2,
            y=equity,
            showarrow=True,
            bgcolor="lightgreen",
            font=dict(size=14, color="darkgreen"),
        )
    else:
        fig.add_annotation(
            text=f"⚠ You're ${abs(equity):,.0f} underwater",
            x=2,
            y=equity,
            showarrow=True,
            bgcolor="lightcoral",
            font=dict(size=14, color="darkred"),
        )

    return _fig_to_base64_png(fig)


def interest_vs_principal(price: float, down: float, rate: float, term: int) -> str:
    """
    Create a pie chart showing interest vs principal paid.

    Args:
        price: Vehicle price
        down: Down payment
        rate: Annual interest rate (%)
        term: Loan term (months)

    Returns:
        Base64-encoded PNG bytes
    """
    from backend.app.agents.math_tools import loan_calculator

    _, total_cost = loan_calculator(price, down, rate, term)
    principal = price - down
    total_interest = total_cost - price

    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Principal", "Interest"],
                values=[principal, total_interest],
                hole=0.3,
                marker_colors=["#1f77b4", "#ff7f0e"],
            )
        ]
    )

    fig.update_layout(
        title=f"Loan Composition: ${principal:,.0f} principal + ${total_interest:,.0f} interest over {term} months",
        height=400,
    )

    return _fig_to_base64_png(fig)
