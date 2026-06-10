from __future__ import annotations

import os
from uuid import uuid4

import pandas as pd
import requests
import streamlit as st


def _post_json(api_url: str, path: str, payload: dict, timeout: int = 45):
    return requests.post(f"{api_url}{path}", json=payload, timeout=timeout)


def _feedback_payload(question: str, answer: str, question_type: str, source: str, context: dict, interaction_id: str | None = None) -> dict:
    return {
        "interaction_id": interaction_id or uuid4().hex,
        "rating": 0,
        "question": question,
        "answer": answer,
        "question_type": question_type,
        "source": source,
        "context": context,
    }


def _submit_feedback(api_url: str, payload: dict, rating: int, key_prefix: str):
    rating_payload = dict(payload)
    rating_payload["rating"] = rating
    resp = _post_json(api_url, "/api/feedback", rating_payload)
    if resp.ok:
        st.success("Feedback saved.", icon="👍" if rating > 0 else "👎")
        st.session_state[f"{key_prefix}_rating"] = rating
    else:
        st.error(resp.text)


def _render_feedback_controls(api_url: str, state_key: str, key_prefix: str):
    payload = st.session_state.get(state_key)
    if not payload:
        return
    st.caption("Was this answer useful?")
    up_col, down_col = st.columns(2)
    with up_col:
        if st.button("Thumbs Up", key=f"{key_prefix}_up"):
            _submit_feedback(api_url, payload, 1, key_prefix)
    with down_col:
        if st.button("Thumbs Down", key=f"{key_prefix}_down"):
            _submit_feedback(api_url, payload, -1, key_prefix)


def _render_inventory_panel(api_url: str):
    st.subheader("Inventory Intelligence")
    col1, col2 = st.columns([2, 1])
    with col1:
        lookup_key = st.text_input("Stock Number or VIN", value="", key="sc_lookup_key")
    with col2:
        max_similar = st.number_input("Similar vehicles", min_value=1, max_value=10, value=3, step=1, key="sc_max_similar")

    action1, action2 = st.columns(2)
    with action1:
        if st.button("Lookup Vehicle", key="sc_lookup_btn", type="primary"):
            if not lookup_key.strip():
                st.warning("Enter a stock number or VIN.")
            else:
                try:
                    resp = _post_json(api_url, "/api/dealership/vehicle-intel", {"stock_number_or_vin": lookup_key.strip()})
                    if resp.ok:
                        payload = resp.json()
                        if payload.get("status") != "ok":
                            st.warning(payload.get("message", "Vehicle not found."))
                        else:
                            st.json(payload.get("vehicle", {}))
                            if payload.get("carfax_summary"):
                                st.info(payload["carfax_summary"].get("summary", "Carfax parsed."))
                    else:
                        st.error(resp.text)
                except Exception as exc:
                    st.error(f"Vehicle lookup failed: {exc}")

    with action2:
        if st.button("Find Similar", key="sc_similar_btn"):
            if not lookup_key.strip():
                st.warning("Enter a stock number first.")
            else:
                try:
                    resp = _post_json(
                        api_url,
                        "/api/dealership/similar-vehicles",
                        {"stock_number": lookup_key.strip(), "max_results": int(max_similar)},
                    )
                    if resp.ok:
                        items = resp.json().get("items", [])
                        st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)
                    else:
                        st.error(resp.text)
                except Exception as exc:
                    st.error(f"Similar vehicles lookup failed: {exc}")

    st.caption("Carfax PDF Upload")
    uploaded_carfax = st.file_uploader("Upload Carfax PDF", type=["pdf"], key="sc_carfax_upload")
    if st.button("Parse Carfax", key="sc_carfax_parse_btn"):
        if uploaded_carfax is None:
            st.warning("Upload a Carfax PDF first.")
        else:
            try:
                files = {
                    "file": (uploaded_carfax.name, uploaded_carfax.getvalue(), "application/pdf"),
                }
                resp = requests.post(f"{api_url}/api/dealership/carfax/upload", files=files, timeout=60)
                if resp.ok:
                    payload = resp.json()
                    st.success("Carfax parsed successfully.")
                    st.json(
                        {
                            "vin": payload.get("vin"),
                            "year": payload.get("year"),
                            "make": payload.get("make"),
                            "model": payload.get("model"),
                            "accident_count": payload.get("accident_count"),
                            "owner_count": payload.get("owner_count"),
                            "last_service_date": payload.get("last_service_date"),
                            "last_odometer_reading": payload.get("last_odometer_reading"),
                            "title_issues": payload.get("title_issues", []),
                        }
                    )
                    if payload.get("service_records"):
                        st.caption("Service records")
                        st.dataframe(pd.DataFrame(payload.get("service_records", [])), use_container_width=True, hide_index=True)
                else:
                    st.error(resp.text)
            except Exception as exc:
                st.error(f"Carfax upload failed: {exc}")


def _render_finance_panel(api_url: str):
    st.subheader("Finance Ladder")
    c1, c2, c3 = st.columns(3)
    with c1:
        vehicle_price = st.number_input("Vehicle Price", min_value=1000.0, value=28995.0, step=500.0, key="sc_price")
        down_payment = st.number_input("Down Payment", min_value=0.0, value=3000.0, step=250.0, key="sc_down")
        credit_tier = st.selectbox("Credit Tier", ["A", "B", "C", "D"], index=1, key="sc_credit")
    with c2:
        term_months = st.select_slider("Term", [24, 36, 48, 60, 72, 84], value=60, key="sc_term")
        tax_rate = st.number_input("Tax Rate", min_value=0.0, max_value=0.2, value=0.0625, step=0.0025, format="%.4f", key="sc_tax")
        state = st.selectbox(
            "State",
            ["MA", "CA", "TX", "FL", "NY", "VA", "MI", "MD", "HI", "DC"],
            index=0,
            key="sc_state",
        )
        fees = st.number_input("Fees", min_value=0.0, value=495.0, step=25.0, key="sc_fees")
    with c3:
        trade_in_value = st.number_input("Trade Value", min_value=0.0, value=0.0, step=500.0, key="sc_trade")
        trade_payoff = st.number_input("Trade Payoff", min_value=0.0, value=0.0, step=500.0, key="sc_payoff")
        include_taxes_in_loan = st.checkbox("Roll Taxes Into Loan", value=True, key="sc_include_tax")

    if st.button("Generate Payment Ladder", key="sc_ladder_btn", type="primary"):
        payload = {
            "vehicle_price": vehicle_price,
            "down_payment": down_payment,
            "credit_tier": credit_tier,
            "term_months": int(term_months),
            "tax_rate": tax_rate,
            "fees": fees,
            "trade_in_value": trade_in_value,
            "trade_payoff": trade_payoff,
            "include_taxes_in_loan": include_taxes_in_loan,
            "state": state,
        }
        try:
            resp = _post_json(api_url, "/api/dealership/finance-ladder", payload)
            if resp.ok:
                result = resp.json()
                if result.get("status") != "ok":
                    st.error(result.get("message", "Finance ladder failed."))
                else:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("APR", f"{result.get('apr', 0)}%")
                    m2.metric("Monthly", f"${result.get('monthly_payment', 0):,.2f}")
                    m3.metric("Amount Financed", f"${result.get('amount_financed', 0):,.2f}")
                    st.caption(
                        f"State tax rule: {'trade-in reduces taxable amount' if result.get('state_reduces_trade_tax') else 'no trade-in tax credit'}"
                    )
                    st.dataframe(pd.DataFrame(result.get("down_payment_ladder", [])), use_container_width=True, hide_index=True)
                    with st.expander("Amortization (Monthly)", expanded=False):
                        st.dataframe(pd.DataFrame(result.get("amortization_monthly", [])), use_container_width=True, hide_index=True)
                    st.caption("Objection handlers")
                    st.json(result.get("objection_handlers", {}))
            else:
                st.error(resp.text)
        except Exception as exc:
            st.error(f"Finance ladder request failed: {exc}")


def _render_negotiation_panel(api_url: str):
    st.subheader("Negotiation Coach")
    customer_message = st.text_area(
        "Customer message",
        value="Can you get my payment lower?",
        height=100,
        key="sc_neg_message",
    )
    if st.button("Generate Response", key="sc_neg_btn"):
        try:
            resp = _post_json(api_url, "/api/dealership/negotiation-assist", {"message": customer_message})
            if resp.ok:
                result = resp.json()
                st.info(f"Intent: {result.get('intent', 'general')}")
                st.success(result.get("response", ""))
                if result.get("talk_track"):
                    st.caption("Suggested talk track")
                    st.write(result.get("talk_track"))
                if result.get("cross_sell_alternatives"):
                    st.caption("Cross-sell alternatives")
                    st.dataframe(pd.DataFrame(result.get("cross_sell_alternatives", [])), use_container_width=True, hide_index=True)
                st.session_state["sc_neg_feedback"] = _feedback_payload(
                    question=customer_message,
                    answer=result.get("talk_track") or result.get("response", ""),
                    question_type="negotiation",
                    source="sales_copilot_negotiation",
                    context={"intent": result.get("intent", "general"), "scenario": result.get("scenario", "")},
                )
            else:
                st.error(resp.text)
        except Exception as exc:
            st.error(f"Negotiation assistant failed: {exc}")
    _render_feedback_controls(api_url, "sc_neg_feedback", "sc_neg_feedback")


def _render_payout_panel(api_url: str):
    st.subheader("Payout Calculator")
    a, b, c = st.columns(3)
    with a:
        front_gross = st.number_input("Front Gross", value=2500.0, step=100.0, key="sc_fg")
        back_gross = st.number_input("Back Gross", value=1200.0, step=100.0, key="sc_bg")
    with b:
        pack_fee = st.number_input("Pack Fee", value=300.0, step=25.0, key="sc_pack")
        commission_rate = st.slider("Commission %", min_value=0, max_value=50, value=25, step=1, key="sc_rate")
    with c:
        unit_bonus = st.number_input("Unit Bonus", value=0.0, step=25.0, key="sc_unit")
        csi_bonus = st.number_input("CSI Bonus", value=0.0, step=25.0, key="sc_csi")

    if st.button("Compute Payout", key="sc_payout_btn"):
        payload = {
            "front_gross": front_gross,
            "back_gross": back_gross,
            "pack_fee": pack_fee,
            "commission_rate": float(commission_rate),
            "unit_bonus": unit_bonus,
            "csi_bonus": csi_bonus,
        }
        try:
            resp = _post_json(api_url, "/api/dealership/payout", payload)
            if resp.ok:
                result = resp.json()
                st.metric("Total Payout", f"${result.get('payout_total', 0):,.2f}")
                st.json(result)
            else:
                st.error(resp.text)
        except Exception as exc:
            st.error(f"Payout request failed: {exc}")


def _render_knowledge_panel(api_url: str):
    st.subheader("Knowledge Base (Optional RAG)")
    st.caption("Drop PDF/TXT docs in knowledge_base/books, then ingest and query here.")

    x_admin_secret = os.getenv("ADMIN_API_SECRET", "").strip()
    headers = {"x-admin-secret": x_admin_secret} if x_admin_secret else {}

    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("Ingest Knowledge Base", key="sc_ingest_btn"):
            try:
                resp = requests.post(f"{api_url}/api/knowledge/ingest", headers=headers, timeout=120)
                if resp.ok:
                    st.success("Knowledge base ingested.")
                    st.json(resp.json())
                else:
                    st.error(resp.text)
            except Exception as exc:
                st.error(f"Ingest failed: {exc}")

    with c2:
        question = st.text_input("Question", value="What are our financing policy highlights?", key="sc_question")
        top_k = st.slider("Top K", min_value=1, max_value=10, value=4, key="sc_topk")
        if st.button("Ask Knowledge Base", key="sc_ask_btn"):
            try:
                resp = _post_json(api_url, "/api/knowledge/query", {"question": question, "top_k": top_k}, timeout=90)
                if resp.ok:
                    result = resp.json()
                    st.write(result.get("answer", ""))
                    with st.expander("Contexts", expanded=False):
                        st.json(result.get("contexts", []))
                    st.session_state["sc_kb_feedback"] = _feedback_payload(
                        question=question,
                        answer=result.get("answer", ""),
                        question_type="knowledge_base",
                        source="sales_copilot_knowledge",
                        context={"top_k": top_k, "context_count": len(result.get("contexts", []))},
                    )
                else:
                    st.error(resp.text)
            except Exception as exc:
                st.error(f"Knowledge query failed: {exc}")
    _render_feedback_controls(api_url, "sc_kb_feedback", "sc_kb_feedback")


def _render_ai_training_panel(api_url: str):
    st.subheader("AI Training")
    x_admin_secret = os.getenv("ADMIN_API_SECRET", "").strip()
    headers = {"x-admin-secret": x_admin_secret} if x_admin_secret else {}

    action1, action2 = st.columns(2)
    with action1:
        if st.button("Re-run Knowledge Ingest", key="sc_training_ingest"):
            try:
                resp = requests.post(f"{api_url}/api/knowledge/ingest", headers=headers, timeout=120)
                if resp.ok:
                    st.success("Knowledge ingest completed.")
                    st.json(resp.json())
                else:
                    st.error(resp.text)
            except Exception as exc:
                st.error(f"Knowledge ingest failed: {exc}")
    with action2:
        if st.button("Recalibrate Finance", key="sc_training_calibrate"):
            try:
                resp = requests.post(f"{api_url}/api/training/calibrate-finance", headers=headers, timeout=120)
                if resp.ok:
                    st.success("Finance calibration completed.")
                    st.json(resp.json())
                else:
                    st.error(resp.text)
            except Exception as exc:
                st.error(f"Finance calibration failed: {exc}")

    try:
        report_resp = requests.get(f"{api_url}/api/training/report", timeout=60)
        if not report_resp.ok:
            st.error(report_resp.text)
            return
        report = report_resp.json()
    except Exception as exc:
        st.error(f"Training report failed: {exc}")
        return

    feedback = report.get("feedback", {})
    credit = report.get("credit_tiers", {})
    kb = report.get("knowledge_base", {})

    m1, m2, m3 = st.columns(3)
    m1.metric("Feedback Today", feedback.get("feedback_today", 0))
    m2.metric("Low-Rated Answers", len(feedback.get("top_low_rated", [])))
    m3.metric("Knowledge Chunks", kb.get("chunks", 0))

    st.caption("Latest calibrated credit tier rates")
    st.json(credit.get("tier_rates", {}))

    st.caption("Knowledge base status")
    st.json({
        "status": kb.get("status"),
        "files": kb.get("files", []),
        "chunks": kb.get("chunks", 0),
        "metadata_path": kb.get("metadata_path"),
    })

    st.caption("Top low-rated answers")
    low_rated = feedback.get("top_low_rated", [])
    if low_rated:
        st.dataframe(pd.DataFrame(low_rated), use_container_width=True, hide_index=True)
    else:
        st.info("No low-rated answers recorded yet.")

    st.caption("Improvement suggestions")
    suggestions = feedback.get("suggestions", [])
    if suggestions:
        st.dataframe(pd.DataFrame(suggestions), use_container_width=True, hide_index=True)
    else:
        st.info("No suggestions yet. Add feedback entries to start training the loop.")


def _render_intent_router(api_url: str):
    st.subheader("Intent Router")
    user_text = st.text_input("Type customer text", value="Can you lower my monthly payment?", key="sc_intent_text")

    if st.button("Route Intent", key="sc_intent_btn"):
        lower = (user_text or "").lower()
        if any(k in lower for k in ["payment", "apr", "rate", "down"]):
            st.info("Routed to: Finance Ladder")
            st.caption("Use the Finance Ladder panel above for structured payment options.")
        elif any(k in lower for k in ["trade", "my car", "appraisal"]):
            st.info("Routed to: Trade/Appraisal")
            st.caption("Use Dealership Tools or dedicated appraisal endpoint.")
        else:
            try:
                resp = _post_json(api_url, "/api/dealership/negotiation-assist", {"message": user_text})
                if resp.ok:
                    payload = resp.json()
                    st.info(f"Routed to: Negotiation ({payload.get('intent', 'general')})")
                    st.success(payload.get("response", ""))
                else:
                    st.error(resp.text)
            except Exception as exc:
                st.error(f"Intent routing failed: {exc}")


def render_sales_copilot(api_url: str):
    st.markdown('<p class="section-header">🧠 Sales Copilot</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="section-sub">Inventory intel, finance ladders, negotiation scripts, payout math, and optional knowledge RAG.</p>',
        unsafe_allow_html=True,
    )

    inv_tab, fin_tab, neg_tab, payout_tab, kb_tab, intent_tab, training_tab = st.tabs(
        [
            "Inventory",
            "Finance",
            "Negotiation",
            "Payout",
            "Knowledge",
            "Intent Router",
            "AI Training",
        ]
    )

    with inv_tab:
        _render_inventory_panel(api_url)
    with fin_tab:
        _render_finance_panel(api_url)
    with neg_tab:
        _render_negotiation_panel(api_url)
    with payout_tab:
        _render_payout_panel(api_url)
    with kb_tab:
        _render_knowledge_panel(api_url)
    with intent_tab:
        _render_intent_router(api_url)
    with training_tab:
        _render_ai_training_panel(api_url)
