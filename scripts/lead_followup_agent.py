import os
import sys
# Ensure project root is in sys.path for backend imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging
from datetime import datetime, timedelta
from sqlalchemy import and_
from backend.app.database.db import get_db_session
from backend.app.database.models import Lead, Followup, Car

# --- Logging setup ---
LOG_PATH = os.path.join("data", "logs", "lead_followup.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

def get_recent_unfollowed_leads(db, minutes=10):
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    return db.query(Lead).filter(
        Lead.created_at >= cutoff,
        Lead.followup_sent == False
    ).all()

def get_carfax_link(db, vehicle_interest):
    if not vehicle_interest:
        return None
    car = db.query(Car).filter(Car.model.ilike(f"%{vehicle_interest}%")).first()
    if car and getattr(car, "carfax_url", None):
        return car.carfax_url.strip()
    return None

def generate_followup_message(lead, carfax_url=None):
    """
    Calls DeepSeek API to generate a personalized follow-up message.
    """
    import openai
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return "[ERROR: DeepSeek API key not set]"
    client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    context = f"Lead info:\nName: {lead.name or ''}\nVehicle interest: {lead.vehicle_interest or ''}\nTrade-in: {lead.trade_in or ''}\nConversation: {lead.conversation_context or ''}"
    if carfax_url:
        context += f"\nCarfax: {carfax_url}"
    prompt = f"You are a dealership sales assistant. Write a warm, personalized follow-up message for a new lead. Mention the vehicle, reference any trade-in, and include the Carfax link if available.\n{context}"
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": "You are a helpful automotive sales assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"DeepSeek API error: {e}")
        return f"[ERROR: DeepSeek API error: {e}]."

def main():
    db = get_db_session()
    try:
        leads = get_recent_unfollowed_leads(db)
        if not leads:
            logging.info("No new leads found for follow-up.")
            return
        for lead in leads:
            carfax_url = get_carfax_link(db, lead.vehicle_interest)
            msg = generate_followup_message(lead, carfax_url)
            followup = Followup(
                lead_id=lead.id,
                message=msg,
                channel="chat",
                status="pending",
                created_at=datetime.utcnow()
            )
            db.add(followup)
            lead.followup_sent = True
            db.commit()
            logging.info(f"Follow-up created for lead {lead.id} ({lead.name or lead.email or lead.phone}): {msg}")
    except Exception as e:
        logging.error(f"Error in follow-up agent: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
