SKILL_NAME = "paperwork_generator"
SKILL_DESCRIPTION = "Starts or updates paperwork sessions for deals, credit apps, or service tickets."
SKILL_PRIORITY = 80
SKILL_TRIGGERS = [
    "start deal", "start buyer order", "start credit app", "start service ticket", "generate", "approve", "archive", "update", "change"
]
SKILL_EMBEDDING = None


from backend.app.deal_session import store as deal_session_store

def execute(query: str, context: dict, session_id: str) -> dict:
    # Migrate handle_paperwork_intent logic
    import re
    active_sessions = getattr(execute, "_active_sessions", {})
    if not hasattr(execute, "_active_sessions"):
        execute._active_sessions = active_sessions
    msg = query.lower()
    if "start deal" in msg:
        session = deal_session_store.create_session("deal_jacket")
        active_sessions[session_id] = session.session_id
        return {
            "answer": f"[Deal mode started: session {session.session_id}. Please provide customer and vehicle details.]",
            "question_type": "paperwork",
            "source": "paperwork_generator",
        }
    elif "start credit app" in msg:
        session = deal_session_store.create_session("credit_application")
        active_sessions[session_id] = session.session_id
        return {
            "answer": f"[Credit application started: session {session.session_id}. Please provide applicant details.]",
            "question_type": "paperwork",
            "source": "paperwork_generator",
        }
    elif "start service ticket" in msg:
        session = deal_session_store.create_session("service_ticket")
        active_sessions[session_id] = session.session_id
        return {
            "answer": f"[Service ticket started: session {session.session_id}. Please provide customer, vehicle, and service details.]",
            "question_type": "paperwork",
            "source": "paperwork_generator",
        }
    session_id_active = active_sessions.get(session_id)
    if not session_id_active:
        return {
            "answer": "[No active paperwork session. Say 'start deal', 'start credit app', or 'start service ticket' to begin.]",
            "question_type": "paperwork",
            "source": "paperwork_generator",
        }
    session = deal_session_store.get_session(session_id_active)
    if not session:
        return {
            "answer": "[Session expired or not found. Please start a new paperwork session.]",
            "question_type": "paperwork",
            "source": "paperwork_generator",
        }
    updates = {}
    if "customer is" in msg:
        name = query.split("customer is",1)[-1].strip().split(".")[0]
        updates["customer"] = {"name": name}
    if "vehicle is" in msg:
        vehicle = query.split("vehicle is",1)[-1].strip().split(".")[0]
        updates["vehicle"] = {"desc": vehicle}
    if "trade is" in msg:
        trade = query.split("trade is",1)[-1].strip().split(".")[0]
        updates["trade_in"] = {"desc": trade}
    if "price is" in msg:
        try:
            price = float(re.findall(r"price is\s*\$?(\d+[\d,]*)", msg)[0].replace(",", ""))
            updates["selling_price"] = price
        except Exception:
            pass
    if updates:
        deal_session_store.update_session(session_id_active, updates)
        session = deal_session_store.get_session(session_id_active)
    required_fields = {
        "deal_jacket": ["customer", "vehicle", "selling_price"],
        "credit_application": ["customer"],
        "service_ticket": ["customer", "vehicle", "fields"],
    }
    missing = []
    for field in required_fields.get(session.form_type, []):
        val = getattr(session, field, None)
        if not val or (isinstance(val, dict) and not any(val.values())):
            missing.append(field)
    if not missing:
        if session.form_type == "deal_jacket":
            deal_data = {
                "customer_name": session.customer.get("name", ""),
                "vehicle": session.vehicle.get("desc", ""),
                "sale_price": session.selling_price or 0,
            }
            pdf_path = generate_deal_jacket_pdf(deal_data)
            json_path = save_document_json("deal_jacket", deal_data)
            session.status = "complete"
            deal_session_store.update_session(session_id_active, {"status": "complete"})
            return {
                "answer": f"[Deal jacket complete. PDF: {pdf_path}\nJSON: {json_path}]",
                "question_type": "paperwork",
                "source": "paperwork_generator",
            }
        elif session.form_type == "credit_application":
            applicant_data = session.customer
            pdf_path = generate_credit_application_pdf(applicant_data)
            json_path = save_document_json("credit_application", applicant_data)
            session.status = "complete"
            deal_session_store.update_session(session_id_active, {"status": "complete"})
            return {
                "answer": f"[Credit application complete. PDF: {pdf_path}\nJSON: {json_path}]",
                "question_type": "paperwork",
                "source": "paperwork_generator",
            }
        elif session.form_type == "service_ticket":
            service_data = {**session.fields, **session.customer, **session.vehicle}
            pdf_path = generate_service_ticket_pdf(service_data)
            json_path = save_document_json("service_ticket", service_data)
            session.status = "complete"
            deal_session_store.update_session(session_id_active, {"status": "complete"})
            return {
                "answer": f"[Service ticket complete. PDF: {pdf_path}\nJSON: {json_path}]",
                "question_type": "paperwork",
                "source": "paperwork_generator",
            }
    return {
        "answer": f"[Session {session.session_id} in progress. Please provide: {', '.join(missing)}]",
        "question_type": "paperwork",
        "source": "paperwork_generator",
    }
