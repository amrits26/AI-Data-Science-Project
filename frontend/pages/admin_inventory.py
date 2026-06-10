from __future__ import annotations

import os
from datetime import datetime

import requests
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _headers(admin_secret: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    if admin_secret.strip():
        headers["x-admin-secret"] = admin_secret.strip()
    return headers


def _fmt_timestamp(value: str | None) -> str:
    if not value:
        return "N/A"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %I:%M %p")
    except Exception:
        return value


def render() -> None:
    st.title("Inventory Accuracy Admin")
    st.caption("Monitor near-live inventory cache and trigger manual refresh.")

    api_url = st.text_input("API URL", value=API_BASE_URL)
    admin_secret = st.text_input("Admin Secret", value=os.getenv("ADMIN_API_SECRET", ""), type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Refresh Status", type="primary"):
            try:
                resp = requests.get(
                    f"{api_url}/api/inventory/admin/status",
                    headers=_headers(admin_secret),
                    timeout=30,
                )
                if not resp.ok:
                    st.error(resp.text)
                else:
                    data = resp.json()
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Last Scrape", _fmt_timestamp(data.get("last_scrape")))
                    m2.metric("Available Vehicles", int(data.get("available_count") or 0))
                    m3.metric("Sold in Last 24h", int(data.get("sold_last_24h") or 0))
                    st.json(data)
            except Exception as exc:
                st.error(f"Status check failed: {exc}")

    with col2:
        if st.button("Run Manual Scrape"):
            try:
                resp = requests.post(
                    f"{api_url}/api/inventory/scrape-now",
                    headers=_headers(admin_secret),
                    timeout=300,
                )
                if not resp.ok:
                    st.error(resp.text)
                else:
                    data = resp.json()
                    st.success("Scrape completed")
                    st.json(data)
            except Exception as exc:
                st.error(f"Manual scrape failed: {exc}")

    st.subheader("Quick VIN/Stock Availability Check")
    vin = st.text_input("VIN")
    stock_number = st.text_input("Stock Number")
    force_live = st.checkbox("Force live website check", value=False)
    if st.button("Check Availability"):
        if not vin.strip() and not stock_number.strip():
            st.warning("Enter VIN or stock number.")
        else:
            try:
                params = {
                    "vin": vin.strip() or None,
                    "stock_number": stock_number.strip() or None,
                    "force_live": str(force_live).lower(),
                }
                resp = requests.get(f"{api_url}/api/inventory/check-availability", params=params, timeout=45)
                if not resp.ok:
                    st.error(resp.text)
                else:
                    st.json(resp.json())
            except Exception as exc:
                st.error(f"Availability check failed: {exc}")


if __name__ == "__main__":
    render()
