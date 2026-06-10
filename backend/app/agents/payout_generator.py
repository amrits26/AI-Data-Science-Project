"""Simple deal-payout summary for managers and sales teams."""

from __future__ import annotations

from typing import Any


def generate_sales_payout(
    front_gross: float,
    back_gross: float,
    pack_fee: float,
    commission_rate: float,
    unit_bonus: float = 0.0,
    csi_bonus: float = 0.0,
) -> dict[str, Any]:
    fg = float(front_gross)
    bg = float(back_gross)
    pack = float(pack_fee)
    rate = float(commission_rate)

    total_gross = fg + bg
    net_commissionable = max(total_gross - pack, 0.0)
    commission = max(net_commissionable * (rate / 100.0), 0.0)
    payout = commission + float(unit_bonus) + float(csi_bonus)

    return {
        "status": "ok",
        "front_gross": round(fg, 2),
        "back_gross": round(bg, 2),
        "total_gross": round(total_gross, 2),
        "pack_fee": round(pack, 2),
        "net_commissionable": round(net_commissionable, 2),
        "commission_rate": round(rate, 2),
        "commission": round(commission, 2),
        "unit_bonus": round(float(unit_bonus), 2),
        "csi_bonus": round(float(csi_bonus), 2),
        "payout_total": round(payout, 2),
    }
